"""
NZB Info device handler.
Manages polling of all configured NZB applications.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import ssl
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import certifi
from ucapi_framework import PollingDevice

from uc_intg_nzbinfo.config import NZBInfoConfig

_LOG = logging.getLogger(__name__)


class AppStatus:
    def __init__(self, app_name: str):
        self.app_name = app_name
        self.is_online = False
        self.title = app_name.title()
        self.primary_info = "Offline"
        self.secondary_info = "Not connected"
        self.last_updated = time.time()
        self.raw_data: dict[str, Any] = {}


class NZBInfoDevice(PollingDevice):

    def __init__(self, device_config: NZBInfoConfig, **kwargs):
        super().__init__(device_config, poll_interval=15, **kwargs)
        self._device_config = device_config
        self._session: aiohttp.ClientSession | None = None
        self._app_statuses: dict[str, AppStatus] = {}
        self._device_reachable = False
        self.current_source = "System Overview"

    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str:
        first_app = next(iter(self._device_config.enabled_apps), None)
        if first_app:
            cfg = self._device_config.get_app_config(first_app)
            return cfg.get("host", "unknown")
        return "not-configured"

    @property
    def log_id(self) -> str:
        return "NZBInfo"

    @property
    def device_reachable(self) -> bool:
        return self._device_reachable

    @property
    def enabled_apps(self) -> list[str]:
        return self._device_config.enabled_apps

    def get_app_status(self, app_name: str) -> AppStatus | None:
        return self._app_statuses.get(app_name)

    def get_all_statuses(self) -> dict[str, AppStatus]:
        return self._app_statuses.copy()

    def get_online_count(self) -> int:
        return sum(1 for s in self._app_statuses.values() if s.is_online)

    def get_total_count(self) -> int:
        return len(self._app_statuses)

    async def establish_connection(self) -> aiohttp.ClientSession:
        _LOG.info("[%s] Connecting to %d apps", self.log_id, len(self._device_config.enabled_apps))
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        timeout = aiohttp.ClientTimeout(total=10)
        self._session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        for app_name in self._device_config.enabled_apps:
            self._app_statuses[app_name] = AppStatus(app_name)

        await self.poll_device()
        _LOG.info("[%s] Initial poll: %d/%d online", self.log_id, self.get_online_count(), self.get_total_count())
        return self._session

    async def disconnect(self) -> None:
        await super().disconnect()
        if self._session:
            await self._session.close()
            self._session = None
        self._device_reachable = False
        _LOG.info("[%s] Disconnected", self.log_id)

    async def poll_device(self) -> None:
        if not self._session:
            return
        tasks = [self._update_app_status(app) for app in self._device_config.enabled_apps]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._device_reachable = any(s.is_online for s in self._app_statuses.values())
        self.push_update()

    def _get_auth_headers(self, app_name: str) -> dict[str, str]:
        headers = {}
        api_key = self._device_config.get_app_api_key(app_name)
        if api_key:
            if app_name == "bazarr":
                headers["X-API-KEY"] = api_key
            elif app_name in ["sonarr", "radarr", "lidarr", "readarr", "overseerr"]:
                headers["X-Api-Key"] = api_key
        return headers

    def _smart_truncate(self, text: str, max_length: int = 35) -> str:
        if len(text) <= max_length:
            return text
        if "." in text:
            name, ext = text.rsplit(".", 1)
            if len(ext) <= 4:
                available = max_length - len(ext) - 4
                if available > 10:
                    return f"{name[:available]}...{ext}"
        return f"{text[:max_length - 3]}..."

    def _format_recent_files(self, files: list[str]) -> str:
        if not files:
            return "No recent activity"
        recent = [self._smart_truncate(f, 30) for f in files[:2]]
        return f"Recent: {' | '.join(recent)}"

    def _format_upcoming_date(self, date_str: str) -> str:
        try:
            if "T" in date_str:
                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                date_obj = datetime.fromisoformat(date_str)
            now = datetime.now(date_obj.tzinfo) if date_obj.tzinfo else datetime.now()
            days_diff = (date_obj.date() - now.date()).days
            if days_diff == 0:
                return "Today"
            elif days_diff == 1:
                return "Tomorrow"
            elif days_diff < 7:
                return f"{days_diff}d"
            return date_obj.strftime("%b %d")
        except Exception:
            return "Unknown"

    def _clean_file_path(self, file_path: str) -> str:
        if not file_path:
            return "Unknown"
        clean = file_path
        if "/" in clean:
            clean = clean.split("/")[-1]
        elif "\\" in clean:
            clean = clean.split("\\")[-1]
        return clean

    async def _update_app_status(self, app_name: str) -> bool:
        try:
            status = self._app_statuses.get(app_name)
            if not status:
                return False
            cfg = self._device_config.get_app_config(app_name)
            if not cfg or "host" not in cfg:
                status.is_online = False
                status.primary_info = "Not configured"
                status.secondary_info = "Missing configuration"
                return False
            if app_name == "sabnzbd":
                return await self._update_sabnzbd(status)
            elif app_name == "nzbget":
                return await self._update_nzbget(status)
            elif app_name in ["sonarr", "radarr", "lidarr", "readarr"]:
                return await self._update_media_manager(status)
            elif app_name == "bazarr":
                return await self._update_bazarr(status)
            elif app_name == "overseerr":
                return await self._update_overseerr(status)
            return False
        except Exception as e:
            _LOG.error("[%s] Failed to update %s: %s", self.log_id, app_name, e)
            if app_name in self._app_statuses:
                self._app_statuses[app_name].is_online = False
                self._app_statuses[app_name].primary_info = "Connection Error"
                self._app_statuses[app_name].secondary_info = str(e)[:50]
            return False

    async def _update_sabnzbd(self, status: AppStatus) -> bool:
        base_url = self._device_config.get_app_url(status.app_name)
        api_key = self._device_config.get_app_api_key(status.app_name)
        queue_url = f"{base_url}/api?mode=queue&apikey={api_key}&output=json"
        history_url = f"{base_url}/api?mode=history&apikey={api_key}&output=json&limit=2"
        try:
            async with self._session.get(queue_url) as response:
                if response.status != 200:
                    status.is_online = False
                    status.primary_info = f"API Error (HTTP {response.status})"
                    return False
                queue_data = await response.json()
                queue = queue_data.get("queue", {})
                active_jobs = queue.get("slots", [])
                speed = queue.get("speed", "0 B/s")
                status.is_online = True
                status.title = "SABnzbd"
                if active_jobs:
                    filename = self._smart_truncate(active_jobs[0].get("filename", "Unknown"), 20)
                    status.primary_info = f"Downloading: {filename} @ {speed}"
                else:
                    status.primary_info = "Queue idle"
            try:
                async with self._session.get(history_url) as hist_resp:
                    if hist_resp.status == 200:
                        hist_data = await hist_resp.json()
                        slots = hist_data.get("history", {}).get("slots", [])
                        recent = [s.get("name", "Unknown") for s in slots]
                        status.secondary_info = self._format_recent_files(recent)
                    else:
                        status.secondary_info = "No recent activity"
            except Exception:
                status.secondary_info = "No recent activity"
            status.raw_data = {"queue_count": len(active_jobs), "speed": speed}
            status.last_updated = time.time()
            return True
        except Exception as e:
            _LOG.error("[%s] SABnzbd update failed: %s", self.log_id, e)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(e)[:50]
            return False

    async def _update_nzbget(self, status: AppStatus) -> bool:
        base_url = self._device_config.get_app_url(status.app_name)
        try:
            payload = {"method": "status", "params": [], "id": 1}
            async with self._session.post(f"{base_url}/jsonrpc", json=payload) as response:
                if response.status != 200:
                    status.is_online = False
                    status.primary_info = f"API Error (HTTP {response.status})"
                    return False
                data = await response.json()
                result = data.get("result", {})
                download_rate = result.get("DownloadRate", 0)
                remaining_mb = result.get("RemainingSizeMB", 0)
                status.is_online = True
                status.title = "NZBget"
                if download_rate > 0:
                    speed_mb = download_rate / 1024 / 1024
                    eta = ""
                    if remaining_mb > 0 and speed_mb > 0:
                        eta_min = remaining_mb / speed_mb / 60
                        if eta_min < 60:
                            eta = f" ({eta_min:.0f}m)"
                        else:
                            eta = f" ({int(eta_min // 60)}h{int(eta_min % 60):02d}m)"
                    status.primary_info = f"Downloading @ {speed_mb:.1f} MB/s{eta}"
                else:
                    status.primary_info = "Queue idle"
            try:
                hist_payload = {"method": "history", "params": [], "id": 2}
                async with self._session.post(f"{base_url}/jsonrpc", json=hist_payload) as hist_resp:
                    if hist_resp.status == 200:
                        hist_data = await hist_resp.json()
                        history = hist_data.get("result", [])
                        recent = [item.get("Name", "Unknown") for item in history[:2]]
                        status.secondary_info = self._format_recent_files(recent)
                    else:
                        status.secondary_info = "No recent activity"
            except Exception:
                status.secondary_info = "No recent activity"
            status.raw_data = {"download_rate": download_rate, "remaining_mb": remaining_mb}
            status.last_updated = time.time()
            return True
        except Exception as e:
            _LOG.error("[%s] NZBget update failed: %s", self.log_id, e)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(e)[:50]
            return False

    async def _update_media_manager(self, status: AppStatus) -> bool:
        base_url = self._device_config.get_app_url(status.app_name)
        headers = self._get_auth_headers(status.app_name)
        api_version = "v3" if status.app_name in ["sonarr", "radarr"] else "v1"
        try:
            status.is_online = True
            status.title = status.app_name.title()
            await self._get_upcoming_content(status, base_url, api_version, headers)
            await self._get_recent_activity(status, base_url, api_version, headers)
            status.last_updated = time.time()
            return True
        except Exception as e:
            _LOG.error("[%s] %s update failed: %s", self.log_id, status.app_name, e)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(e)[:50]
            return False

    async def _get_upcoming_content(self, status: AppStatus, base_url: str, api_version: str, headers: dict):
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        calendar_url = f"{base_url}/api/{api_version}/calendar?start={today}&end={next_week}&includeEpisode=true&includeSeries=true"
        try:
            async with self._session.get(calendar_url, headers=headers) as response:
                if response.status != 200:
                    status.primary_info = "Calendar unavailable"
                    return
                calendar_data = await response.json()
                if not isinstance(calendar_data, list) or not calendar_data:
                    status.primary_info = "No upcoming releases"
                    return
                upcoming = None
                for item in calendar_data:
                    if item.get("monitored", False) and not item.get("hasFile", False):
                        upcoming = item
                        break
                if not upcoming:
                    status.primary_info = "No upcoming releases"
                    return
                if status.app_name == "sonarr":
                    series = upcoming.get("series", {})
                    series_title = series.get("title") or upcoming.get("seriesTitle") or "Unknown"
                    season = upcoming.get("seasonNumber", 0)
                    episode = upcoming.get("episodeNumber", 0)
                    air_date = self._format_upcoming_date(upcoming.get("airDate", ""))
                    title = self._smart_truncate(f"{series_title} S{season:02d}E{episode:02d}", 25)
                    status.primary_info = f"Next: {title} ({air_date})"
                elif status.app_name == "radarr":
                    movie_title = upcoming.get("title", "Unknown")
                    year = upcoming.get("year", "")
                    release_date = self._format_upcoming_date(upcoming.get("inCinemas", ""))
                    title = self._smart_truncate(f"{movie_title} ({year})", 25)
                    status.primary_info = f"Next: {title} ({release_date})"
                elif status.app_name == "lidarr":
                    artist = upcoming.get("artist", {}).get("artistName", "Unknown")
                    album = upcoming.get("title", "Unknown")
                    release_date = self._format_upcoming_date(upcoming.get("releaseDate", ""))
                    title = self._smart_truncate(f"{artist} - {album}", 25)
                    status.primary_info = f"Next: {title} ({release_date})"
                elif status.app_name == "readarr":
                    author = upcoming.get("author", {}).get("authorName", "Unknown")
                    book = upcoming.get("title", "Unknown")
                    release_date = self._format_upcoming_date(upcoming.get("releaseDate", ""))
                    title = self._smart_truncate(f"{author} - {book}", 25)
                    status.primary_info = f"Next: {title} ({release_date})"
        except Exception as e:
            _LOG.debug("[%s] Calendar fetch failed for %s: %s", self.log_id, status.app_name, e)
            status.primary_info = "No upcoming data"

    async def _get_recent_activity(self, status: AppStatus, base_url: str, api_version: str, headers: dict):
        history_url = f"{base_url}/api/{api_version}/history?pageSize=2"
        try:
            async with self._session.get(history_url, headers=headers) as response:
                if response.status != 200:
                    status.secondary_info = "History unavailable"
                    return
                hist_data = await response.json()
                records = []
                if isinstance(hist_data, dict) and "records" in hist_data:
                    records = hist_data.get("records", [])
                if records:
                    recent = []
                    for record in records[:2]:
                        source = record.get("sourceTitle", "Unknown")
                        if source and source != "Unknown":
                            recent.append(self._clean_file_path(source))
                    status.secondary_info = self._format_recent_files(recent)
                else:
                    status.secondary_info = "No recent activity"
        except Exception as e:
            _LOG.debug("[%s] History fetch failed for %s: %s", self.log_id, status.app_name, e)
            status.secondary_info = "No recent activity"

    async def _update_bazarr(self, status: AppStatus) -> bool:
        base_url = self._device_config.get_app_url(status.app_name)
        headers = self._get_auth_headers(status.app_name)
        status.is_online = True
        status.title = "Bazarr"
        try:
            async with self._session.get(f"{base_url}/api/system/status", headers=headers) as response:
                if response.status != 200:
                    status.is_online = False
                    status.primary_info = f"Connection Error (HTTP {response.status})"
                    return False
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    status.primary_info = "Authentication Error"
                    status.secondary_info = "Check API key"
                    return False
        except Exception as e:
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(e)[:50]
            return False

        recent_downloads = []
        try:
            async with self._session.get(f"{base_url}/api/episodes/history?length=3", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    for item in data.get("data", []):
                        series = item.get("seriesTitle", "Unknown")
                        lang = item.get("language", "")
                        recent_downloads.append(f"{series} ({lang})" if lang else series)
        except Exception:
            pass

        if len(recent_downloads) < 2:
            try:
                async with self._session.get(f"{base_url}/api/movies/history?length=3", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        for item in data.get("data", []):
                            movie = item.get("title", "Unknown")
                            lang = item.get("language", "")
                            recent_downloads.append(f"{movie} ({lang})" if lang else movie)
                            if len(recent_downloads) >= 2:
                                break
            except Exception:
                pass

        status.primary_info = "Subtitle downloads active" if recent_downloads else "Subtitle manager idle"
        status.secondary_info = self._format_recent_files(recent_downloads) if recent_downloads else "No recent downloads"
        status.last_updated = time.time()
        return True

    async def _update_overseerr(self, status: AppStatus) -> bool:
        base_url = self._device_config.get_app_url(status.app_name)
        headers = self._get_auth_headers(status.app_name)
        try:
            async with self._session.get(f"{base_url}/api/v1/request?take=5&sort=added", headers=headers) as response:
                if response.status != 200:
                    status.is_online = False
                    status.primary_info = f"API Error (HTTP {response.status})"
                    return False
                data = await response.json()
                status.is_online = True
                status.title = "Overseerr"
                all_requests = data.get("results", [])
                pending = [r for r in all_requests if r.get("status") == 1]
                status.primary_info = f"{len(pending)} pending requests" if pending else "No pending requests"
                if all_requests:
                    recent = []
                    for req in all_requests[:2]:
                        media = req.get("media", {})
                        if req.get("type") == "movie":
                            recent.append(f"{media.get('title', 'Unknown')} ({media.get('releaseDate', '')[:4]})")
                        else:
                            recent.append(media.get("name", "Unknown"))
                    status.secondary_info = self._format_recent_files(recent)
                else:
                    status.secondary_info = "No recent requests"
                status.raw_data = {"pending_count": len(pending)}
                status.last_updated = time.time()
                return True
        except Exception as e:
            _LOG.error("[%s] Overseerr update failed: %s", self.log_id, e)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(e)[:50]
            return False

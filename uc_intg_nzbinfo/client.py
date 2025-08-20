"""
NZB Info Applications HTTP client with optimized 2-row display for all applications.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import aiohttp
import certifi

from uc_intg_nzbinfo.config import NZBInfoConfig

_LOG = logging.getLogger(__name__)


class AppStatus:
    """Container for application status data."""

    def __init__(self, app_name: str):
        """Initialize status container."""
        self.app_name = app_name
        self.is_online = False
        self.title = app_name.title()
        self.primary_info = "Offline"
        self.secondary_info = "Not connected"
        self.last_updated = time.time()
        self.raw_data = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "app_name": self.app_name,
            "is_online": self.is_online,
            "title": self.title,
            "primary_info": self.primary_info,
            "secondary_info": self.secondary_info,
            "last_updated": self.last_updated,
            "raw_data": self.raw_data
        }


class NZBInfoClient:
    """HTTP client for NZB Info applications with 2-row display optimization."""

    def __init__(self, config: NZBInfoConfig):
        """Initialize NZB Info client."""
        self._config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._app_statuses: Dict[str, AppStatus] = {}
        self._is_connected = False

    async def connect(self) -> bool:
        """Connect to enabled applications."""
        try:
            if self._session is None:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                timeout = aiohttp.ClientTimeout(total=10)
                self._session = aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector
                )

            for app_name in self._config.get_enabled_apps():
                self._app_statuses[app_name] = AppStatus(app_name)

            success_count = 0
            for app_name in self._config.get_enabled_apps():
                if await self._test_app_connection(app_name):
                    success_count += 1

            self._is_connected = success_count > 0
            _LOG.info("Connected to %d/%d NZB Info applications", 
                      success_count, len(self._config.get_enabled_apps()))
            return self._is_connected

        except Exception as ex:
            _LOG.error("Failed to connect to NZB Info applications: %s", ex)
            self._is_connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from applications."""
        if self._session:
            await self._session.close()
            self._session = None
        self._is_connected = False
        _LOG.info("Disconnected from NZB Info applications")

    async def _test_app_connection(self, app_name: str) -> bool:
        """Test connection to specific application."""
        try:
            app_config = self._config.get_app_config(app_name)
            if not app_config or "host" not in app_config:
                return False

            url = self._get_health_check_url(app_name)
            if not url:
                return False

            headers = self._get_auth_headers(app_name)
            
            async with self._session.get(url, headers=headers) as response:
                if response.status in [200, 401]:
                    self._app_statuses[app_name].is_online = True
                    return True
                    
        except Exception as ex:
            _LOG.debug("Connection test failed for %s: %s", app_name, ex)
            
        self._app_statuses[app_name].is_online = False
        return False

    def _get_health_check_url(self, app_name: str) -> str:
        """Get health check URL for application."""
        base_url = self._config.get_app_url(app_name)
        if not base_url:
            return ""

        health_endpoints = {
            "sabnzbd": "/api?mode=version",
            "nzbget": "/jsonrpc",
            "sonarr": "/api/v3/system/status", 
            "radarr": "/api/v3/system/status",
            "lidarr": "/api/v1/system/status",
            "readarr": "/api/v1/system/status",
            "bazarr": "/api/system/status",
            "overseerr": "/api/v1/status"
        }

        endpoint = health_endpoints.get(app_name, "/")
        url = f"{base_url}{endpoint}"
        
        if app_name == "sabnzbd":
            api_key = self._config.get_app_api_key(app_name)
            if api_key:
                separator = "&" if "?" in url else "?"
                url += f"{separator}apikey={api_key}"
        
        return url

    def _get_auth_headers(self, app_name: str) -> Dict[str, str]:
        """Get authentication headers for application."""
        headers = {}
        api_key = self._config.get_app_api_key(app_name)
        
        if api_key:
            if app_name == "bazarr":
                headers["X-API-KEY"] = api_key
            elif app_name in ["sonarr", "radarr", "lidarr", "readarr", "overseerr"]:
                headers["X-Api-Key"] = api_key
        
        return headers

    def _clean_file_path(self, file_path: str) -> str:
        """Extract clean filename from full path."""
        if not file_path:
            return "Unknown"
        
        path_prefixes_to_remove = [
            "/tvshows/", "/movies/", "/downloads/", "/media/",
            "\\\\tvshows\\\\", "\\\\movies\\\\", "\\\\downloads\\\\", "\\\\media\\\\",
            "C:\\\\", "D:\\\\", "/home/", "/mnt/"
        ]
        
        clean_path = file_path
        for prefix in path_prefixes_to_remove:
            if clean_path.lower().startswith(prefix.lower()):
                clean_path = clean_path[len(prefix):]
                break
        
        if '/' in clean_path:
            clean_path = clean_path.split('/')[-1]
        elif '\\\\' in clean_path:
            clean_path = clean_path.split('\\\\')[-1]
        
        return clean_path

    def _smart_truncate(self, text: str, max_length: int = 35) -> str:
        """Smart truncate filename keeping important parts."""
        if len(text) <= max_length:
            return text
        
        if '.' in text:
            name, ext = text.rsplit('.', 1)
            if len(ext) <= 4:
                available = max_length - len(ext) - 4
                if available > 10:
                    return f"{name[:available]}...{ext}"
        
        return f"{text[:max_length-3]}..."

    def _format_recent_files(self, files: List[str]) -> str:
        """Format up to 2 recent files with smart truncation and path cleaning."""
        if not files:
            return "No recent activity"
        
        recent_files = []
        for file in files[:2]:
            cleaned_file = self._clean_file_path(file)
            truncated = self._smart_truncate(cleaned_file, 30)
            recent_files.append(truncated)
        
        return f"Recent: {' | '.join(recent_files)}"

    def _calculate_eta(self, size_left: str, speed: str) -> str:
        """Calculate ETA from size left and speed."""
        try:
            if not size_left or size_left == "0 B":
                return ""
            
            if not speed or speed == "0" or "0 B/s" in speed:
                return ""
            
            size_parts = size_left.split()
            speed_parts = speed.split()
            
            if len(size_parts) != 2 or len(speed_parts) != 2:
                return ""
            
            size_value = float(size_parts[0])
            size_unit = size_parts[1].upper()
            speed_value = float(speed_parts[0])
            speed_unit = speed_parts[1].upper().replace("/S", "")
            
            size_mb = size_value
            if size_unit.startswith("GB"):
                size_mb = size_value * 1024
            elif size_unit.startswith("KB"):
                size_mb = size_value / 1024
            
            speed_mb = speed_value
            if speed_unit.startswith("GB"):
                speed_mb = speed_value * 1024
            elif speed_unit.startswith("KB"):
                speed_mb = speed_value / 1024
            
            if speed_mb <= 0:
                return ""
            
            eta_minutes = size_mb / speed_mb / 60
            
            if eta_minutes < 1:
                return " (<1m)"
            elif eta_minutes < 60:
                return f" ({eta_minutes:.0f}m)"
            else:
                hours = int(eta_minutes // 60)
                minutes = int(eta_minutes % 60)
                return f" ({hours}h{minutes:02d}m)"
                
        except Exception:
            return ""

    def _format_upcoming_date(self, date_str: str) -> str:
        """Format upcoming date for display."""
        try:
            if 'T' in date_str:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
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
            else:
                return date_obj.strftime("%b %d")
                
        except Exception:
            return "Unknown"

    async def update_all_statuses(self) -> bool:
        """Update status for all enabled applications."""
        if not self._session:
            return False

        success_count = 0
        tasks = []
        
        for app_name in self._config.get_enabled_apps():
            task = asyncio.create_task(self._update_app_status(app_name))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, bool) and result:
                success_count += 1
            elif isinstance(result, Exception):
                _LOG.error("Error updating app status: %s", result)

        return success_count > 0

    async def _update_app_status(self, app_name: str) -> bool:
        """Update status for specific application."""
        try:
            status = self._app_statuses.get(app_name)
            if not status:
                return False

            app_config = self._config.get_app_config(app_name)
            if not app_config or "host" not in app_config:
                status.is_online = False
                status.primary_info = "Not configured"
                status.secondary_info = "Missing configuration"
                return False

            if app_name == "sabnzbd":
                return await self._update_sabnzbd_2row(status)
            elif app_name == "nzbget":
                return await self._update_nzbget_2row(status)
            elif app_name in ["sonarr", "radarr", "lidarr", "readarr"]:
                return await self._update_media_manager_2row(status)
            elif app_name == "bazarr":
                return await self._update_bazarr_2row(status)
            elif app_name == "overseerr":
                return await self._update_overseerr_2row(status)

        except Exception as ex:
            _LOG.error("Failed to update %s status: %s", app_name, ex)
            if app_name in self._app_statuses:
                self._app_statuses[app_name].is_online = False
                self._app_statuses[app_name].primary_info = "Connection Error"
                self._app_statuses[app_name].secondary_info = str(ex)[:50]
            return False

    async def _update_sabnzbd_2row(self, status: AppStatus) -> bool:
        """2-row SABnzbd: Row1=Active download+speed+ETA, Row2=Recent files."""
        base_url = self._config.get_app_url(status.app_name)
        api_key = self._config.get_app_api_key(status.app_name)
        
        queue_url = f"{base_url}/api?mode=queue&apikey={api_key}&output=json"
        history_url = f"{base_url}/api?mode=history&apikey={api_key}&output=json&limit=2"
        
        try:
            async with self._session.get(queue_url) as response:
                if response.status == 200:
                    queue_data = await response.json()
                    queue = queue_data.get("queue", {})
                    
                    active_jobs = queue.get("slots", [])
                    speed = queue.get("speed", "0 B/s")
                    size_left = queue.get("sizeleft", "0 B")
                    
                    status.is_online = True
                    status.title = "SABnzbd"
                    
                    if active_jobs:
                        current_job = active_jobs[0]
                        filename = current_job.get("filename", "Unknown")
                        
                        display_name = self._smart_truncate(filename, 20)
                        eta = self._calculate_eta(size_left, speed)
                        
                        status.primary_info = f"Downloading: {display_name} @ {speed}{eta}"
                    else:
                        status.primary_info = "Queue idle"
                    
                    try:
                        async with self._session.get(history_url) as hist_response:
                            if hist_response.status == 200:
                                hist_data = await hist_response.json()
                                slots = hist_data.get("history", {}).get("slots", [])
                                
                                recent_files = [slot.get("name", "Unknown") for slot in slots]
                                status.secondary_info = self._format_recent_files(recent_files)
                            else:
                                status.secondary_info = "No recent activity"
                    except Exception:
                        status.secondary_info = "No recent activity"
                    
                    status.raw_data = {"queue_count": len(active_jobs), "speed": speed}
                    status.last_updated = time.time()
                    return True
                else:
                    status.is_online = False
                    status.primary_info = "API Error"
                    status.secondary_info = f"HTTP {response.status}"
                    
        except Exception as ex:
            _LOG.error("SABnzbd status update failed: %s", ex)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(ex)[:50]
            
        return False

    async def _update_nzbget_2row(self, status: AppStatus) -> bool:
        """2-row NZBget: Row1=Active download+speed, Row2=Recent files."""
        base_url = self._config.get_app_url(status.app_name)
        
        try:
            status_payload = {"method": "status", "params": [], "id": 1}
            async with self._session.post(f"{base_url}/jsonrpc", json=status_payload) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("result", {})
                    
                    download_rate = result.get("DownloadRate", 0)
                    remaining_size = result.get("RemainingSizeMB", 0)
                    
                    status.is_online = True
                    status.title = "NZBget"
                    
                    if download_rate > 0:
                        speed_mb = download_rate / 1024 / 1024
                        
                        if remaining_size > 0 and speed_mb > 0:
                            eta_minutes = remaining_size / speed_mb / 60
                            if eta_minutes < 60:
                                eta = f" ({eta_minutes:.0f}m)"
                            else:
                                hours = int(eta_minutes // 60)
                                minutes = int(eta_minutes % 60)
                                eta = f" ({hours}h{minutes:02d}m)"
                        else:
                            eta = ""
                        
                        status.primary_info = f"Downloading @ {speed_mb:.1f} MB/s{eta}"
                    else:
                        status.primary_info = "Queue idle"
                    
                    try:
                        history_payload = {"method": "history", "params": [], "id": 2}
                        async with self._session.post(f"{base_url}/jsonrpc", json=history_payload) as hist_response:
                            if hist_response.status == 200:
                                hist_data = await hist_response.json()
                                history = hist_data.get("result", [])
                                
                                recent_files = [item.get("Name", "Unknown") for item in history[:2]]
                                status.secondary_info = self._format_recent_files(recent_files)
                            else:
                                status.secondary_info = "No recent activity"
                    except Exception:
                        status.secondary_info = "No recent activity"
                    
                    status.raw_data = {"download_rate": download_rate, "remaining_mb": remaining_size}
                    status.last_updated = time.time()
                    return True
                else:
                    status.is_online = False
                    status.primary_info = "API Error"
                    status.secondary_info = f"HTTP {response.status}"
                    
        except Exception as ex:
            _LOG.error("NZBget status update failed: %s", ex)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(ex)[:50]
            
        return False

    async def _update_media_manager_2row(self, status: AppStatus) -> bool:
        """2-row media manager: Row1=Upcoming content, Row2=Recent files."""
        base_url = self._config.get_app_url(status.app_name)
        api_key = self._config.get_app_api_key(status.app_name)
        
        api_version = "v3" if status.app_name in ["sonarr", "radarr"] else "v1"
        headers = {"X-Api-Key": api_key}
        
        try:
            status.is_online = True
            status.title = status.app_name.title()
            
            await self._get_upcoming_content(status, base_url, api_version, headers)
            await self._get_recent_activity(status, base_url, api_version, headers)
            
            status.last_updated = time.time()
            return True
            
        except Exception as ex:
            _LOG.error("%s status update failed: %s", status.app_name, ex)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(ex)[:50]
            
        return False

    async def _get_upcoming_content(self, status: AppStatus, base_url: str, api_version: str, headers: Dict[str, str]):
        """Get upcoming content from calendar."""
        today = datetime.now().strftime("%Y-%m-%d")
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        calendar_url = f"{base_url}/api/{api_version}/calendar?start={today}&end={next_week}&includeEpisode=true&includeSeries=true"
        
        try:
            async with self._session.get(calendar_url, headers=headers) as response:
                if response.status == 200:
                    calendar_data = await response.json()
                    
                    if isinstance(calendar_data, list) and calendar_data:
                        upcoming = None
                        for item in calendar_data:
                            if item.get("monitored", False) and not item.get("hasFile", False):
                                upcoming = item
                                break
                        
                        if upcoming:
                            if status.app_name == "sonarr":
                                series = upcoming.get('series', {})
                                series_title = (series.get('title') or 
                                                series.get('seriesTitle') or 
                                                upcoming.get('seriesTitle') or
                                                upcoming.get('seriesName') or
                                                'Unknown Series')
                                
                                if series_title == 'Unknown Series' and 'episodeFile' in upcoming:
                                    file_path = upcoming.get('episodeFile', {}).get('path', '')
                                    if file_path:
                                        path_parts = file_path.split('/')
                                        if len(path_parts) >= 3:
                                            series_title = path_parts[-3]
                                
                                season = upcoming.get('seasonNumber', 0)
                                episode = upcoming.get('episodeNumber', 0)
                                air_date = self._format_upcoming_date(upcoming.get('airDate', ''))
                                
                                title = self._smart_truncate(f"{series_title} S{season:02d}E{episode:02d}", 25)
                                status.primary_info = f"Next: {title} ({air_date})"
                                
                            elif status.app_name == "radarr":
                                movie_title = upcoming.get('title', 'Unknown')
                                year = upcoming.get('year', '')
                                release_date = self._format_upcoming_date(upcoming.get('inCinemas', ''))
                                
                                title = self._smart_truncate(f"{movie_title} ({year})", 25)
                                status.primary_info = f"Next: {title} ({release_date})"
                                
                            elif status.app_name == "lidarr":
                                artist = upcoming.get('artist', {}).get('artistName', 'Unknown Artist')
                                album_title = upcoming.get('title', 'Unknown Album')
                                release_date = self._format_upcoming_date(upcoming.get('releaseDate', ''))
                                
                                title = self._smart_truncate(f"{artist} - {album_title}", 25)
                                status.primary_info = f"Next: {title} ({release_date})"
                                
                            elif status.app_name == "readarr":
                                author = upcoming.get('author', {}).get('authorName', 'Unknown Author')
                                book_title = upcoming.get('title', 'Unknown Book')
                                release_date = self._format_upcoming_date(upcoming.get('releaseDate', ''))
                                
                                title = self._smart_truncate(f"{author} - {book_title}", 25)
                                status.primary_info = f"Next: {title} ({release_date})"
                        else:
                            status.primary_info = "No upcoming releases"
                    else:
                        status.primary_info = "No upcoming releases"
                else:
                    status.primary_info = "Calendar unavailable"
        except Exception as e:
            _LOG.debug(f"Calendar fetch failed for {status.app_name}: {e}")
            status.primary_info = "No upcoming data"

    async def _get_recent_activity(self, status: AppStatus, base_url: str, api_version: str, headers: Dict[str, str]):
        """Get recent activity from history."""
        history_url = f"{base_url}/api/{api_version}/history?pageSize=2"
        try:
            async with self._session.get(history_url, headers=headers) as response:
                if response.status == 200:
                    hist_data = await response.json()
                    
                    records = []
                    if isinstance(hist_data, dict) and "records" in hist_data:
                        records = hist_data.get("records", [])
                    
                    if records:
                        recent_files = []
                        for record in records[:2]:
                            source = record.get('sourceTitle', 'Unknown')
                            if source and source != 'Unknown':
                                cleaned_source = self._clean_file_path(source)
                                recent_files.append(cleaned_source)
                        
                        status.secondary_info = self._format_recent_files(recent_files)
                    else:
                        status.secondary_info = "No recent activity"
                else:
                    status.secondary_info = "History unavailable"
        except Exception as e:
            _LOG.debug(f"History fetch failed for {status.app_name}: {e}")
            status.secondary_info = "No recent activity"

    async def _update_bazarr_2row(self, status: AppStatus) -> bool:
        """2-row Bazarr: Row1=Subtitle activity, Row2=Recent downloads."""
        base_url = self._config.get_app_url(status.app_name)
        api_key = self._config.get_app_api_key(status.app_name)
        
        headers = {"X-API-KEY": api_key}
        
        status.is_online = True
        status.title = "Bazarr"
        
        try:
            test_url = f"{base_url}/api/system/status"
            async with self._session.get(test_url, headers=headers) as response:
                if response.status != 200:
                    status.is_online = False
                    status.primary_info = "Connection Error"
                    status.secondary_info = f"HTTP {response.status}"
                    return False
                    
                content_type = response.headers.get('content-type', '')
                if 'text/html' in content_type:
                    status.primary_info = "Authentication Error"
                    status.secondary_info = "Check API key configuration"
                    return False
        except Exception as e:
            status.is_online = False
            status.primary_info = "Connection Error" 
            status.secondary_info = str(e)[:50]
            return False
        
        recent_downloads = []
        
        try:
            episodes_url = f"{base_url}/api/episodes/history?length=3"
            async with self._session.get(episodes_url, headers=headers) as response:
                if response.status == 200:
                    episodes_data = await response.json()
                    episodes_list = episodes_data.get("data", [])
                    
                    for item in episodes_list:
                        series_title = item.get("seriesTitle", "Unknown")
                        language = item.get("language", "")
                        if language:
                            file_info = f"{series_title} ({language})"
                        else:
                            file_info = series_title
                        recent_downloads.append(file_info)
        except Exception as e:
            _LOG.debug(f"Bazarr episodes history failed: {e}")
        
        if len(recent_downloads) < 2:
            try:
                movies_url = f"{base_url}/api/movies/history?length=3"
                async with self._session.get(movies_url, headers=headers) as response:
                    if response.status == 200:
                        movies_data = await response.json()
                        movies_list = movies_data.get("data", [])
                        
                        for item in movies_list:
                            movie_title = item.get("title", "Unknown")
                            language = item.get("language", "")
                            if language:
                                file_info = f"{movie_title} ({language})"
                            else:
                                file_info = movie_title
                            recent_downloads.append(file_info)
                            
                            if len(recent_downloads) >= 2:
                                break
            except Exception as e:
                _LOG.debug(f"Bazarr movies history failed: {e}")
        
        if recent_downloads:
            status.primary_info = "Subtitle downloads active"
        else:
            status.primary_info = "Subtitle manager idle"
        
        status.secondary_info = self._format_recent_files(recent_downloads) if recent_downloads else "No recent downloads"
        
        status.raw_data = {"recent_count": len(recent_downloads)}
        status.last_updated = time.time()
        return True

    async def _update_overseerr_2row(self, status: AppStatus) -> bool:
        """2-row Overseerr: Row1=Pending requests, Row2=Recent requests."""
        base_url = self._config.get_app_url(status.app_name)
        api_key = self._config.get_app_api_key(status.app_name)
        
        headers = {"X-API-Key": api_key}
        requests_url = f"{base_url}/api/v1/request?take=5&sort=added"
        
        try:
            async with self._session.get(requests_url, headers=headers) as response:
                if response.status == 200:
                    requests_data = await response.json()
                    
                    status.is_online = True
                    status.title = "Overseerr"
                    
                    all_requests = requests_data.get("results", [])
                    pending_requests = [r for r in all_requests if r.get("status") == 1]
                    
                    if pending_requests:
                        status.primary_info = f"{len(pending_requests)} pending requests"
                    else:
                        status.primary_info = "No pending requests"
                    
                    if all_requests:
                        recent_files = []
                        for request in all_requests[:2]:
                            if request.get("type") == "movie":
                                media = request.get('media', {})
                                title = f"{media.get('title', 'Unknown')} ({media.get('releaseDate', '')[:4]})"
                            else:
                                title = request.get('media', {}).get('name', 'Unknown')
                            recent_files.append(title)
                        
                        status.secondary_info = self._format_recent_files(recent_files)
                    else:
                        status.secondary_info = "No recent requests"
                    
                    status.raw_data = {"pending_count": len(pending_requests)}
                    status.last_updated = time.time()
                    return True
                else:
                    status.is_online = False
                    status.primary_info = "API Error"
                    status.secondary_info = f"HTTP {response.status}"
                    
        except Exception as ex:
            _LOG.error("Overseerr status update failed: %s", ex)
            status.is_online = False
            status.primary_info = "Connection Error"
            status.secondary_info = str(ex)[:50]
            
        return False

    def get_app_status(self, app_name: str) -> Optional[AppStatus]:
        """Get status for specific application."""
        return self._app_statuses.get(app_name)

    def get_all_statuses(self) -> Dict[str, AppStatus]:
        """Get all application statuses."""
        return self._app_statuses.copy()

    @property
    def is_connected(self) -> bool:
        """Check if connected to any applications."""
        return self._is_connected

    @property
    def enabled_apps(self) -> List[str]:
        """Get list of enabled applications."""
        return self._config.get_enabled_apps()
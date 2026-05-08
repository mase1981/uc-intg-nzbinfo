"""
Configuration for NZB Info Manager integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from dataclasses import dataclass, field

APP_DEFAULTS = {
    "sabnzbd": {"port": 8080},
    "nzbget": {"port": 6789},
    "sonarr": {"port": 8989},
    "radarr": {"port": 7878},
    "lidarr": {"port": 8686},
    "readarr": {"port": 8787},
    "bazarr": {"port": 6767},
    "overseerr": {"port": 5055},
}

APP_DISPLAY = {
    "sabnzbd": {"name": "SABnzbd", "icon": "sabnzbd.png"},
    "nzbget": {"name": "NZBget", "icon": "nzbget.png"},
    "sonarr": {"name": "Sonarr", "icon": "sonarr.png"},
    "radarr": {"name": "Radarr", "icon": "radarr.png"},
    "lidarr": {"name": "Lidarr", "icon": "lidarr.png"},
    "readarr": {"name": "Readarr", "icon": "readarr.png"},
    "bazarr": {"name": "Bazarr", "icon": "bazarr.png"},
    "overseerr": {"name": "Overseerr", "icon": "overseerr.png"},
}


@dataclass
class NZBInfoConfig:
    identifier: str = "nzbinfo"
    name: str = "NZB Info Manager"
    enabled_apps: list[str] = field(default_factory=list)
    applications: dict = field(default_factory=dict)

    def get_app_config(self, app_name: str) -> dict:
        return self.applications.get(app_name, {})

    def get_app_url(self, app_name: str) -> str:
        cfg = self.get_app_config(app_name)
        if not cfg or "host" not in cfg:
            return ""
        protocol = "https" if cfg.get("ssl", False) else "http"
        host = cfg["host"]
        port = cfg.get("port", APP_DEFAULTS.get(app_name, {}).get("port", 80))
        url_base = cfg.get("url_base", "").strip("/")
        url = f"{protocol}://{host}:{port}"
        if url_base:
            url += f"/{url_base}"
        return url

    def get_app_api_key(self, app_name: str) -> str:
        return self.get_app_config(app_name).get("api_key", "")

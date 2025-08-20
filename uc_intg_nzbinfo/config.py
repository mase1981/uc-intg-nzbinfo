"""
Configuration management for NZB Info Manager Integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import json
import logging
import os
from typing import Any, Dict, List

_LOG = logging.getLogger(__name__)


class NZBInfoConfig:
    """Configuration manager for NZB Info integration."""

    APP_DEFAULTS = {
        "sabnzbd": {"port": 8080, "ssl": False, "url_base": ""},
        "nzbget": {"port": 6789, "ssl": False, "url_base": ""},
        "sonarr": {"port": 8989, "ssl": False, "url_base": ""},
        "radarr": {"port": 7878, "ssl": False, "url_base": ""},
        "lidarr": {"port": 8686, "ssl": False, "url_base": ""},
        "readarr": {"port": 8787, "ssl": False, "url_base": ""},
        "bazarr": {"port": 6767, "ssl": False, "url_base": ""},
        "overseerr": {"port": 5055, "ssl": False, "url_base": ""}
    }

    def __init__(self, config_dir: str = None):
        """Initialize configuration manager."""
        if config_dir is None:
            config_dir = (
                os.getenv("UC_CONFIG_HOME") or 
                os.getenv("HOME") or 
                "./"
            )
        
        self._config_dir = config_dir
        self._config_file = os.path.join(config_dir, "config.json")
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as file:
                    self._config = json.load(file)
                    _LOG.info("Configuration loaded from %s", self._config_file)
            else:
                _LOG.info("No configuration file found, using defaults")
                self._config = self._default_config()
        except Exception as ex:
            _LOG.error("Failed to load configuration: %s", ex)
            self._config = self._default_config()

    def save_config(self) -> bool:
        """Save configuration to file."""
        try:
            os.makedirs(self._config_dir, exist_ok=True)
            
            test_file = os.path.join(self._config_dir, ".write_test")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except (OSError, IOError) as e:
                _LOG.error("Config directory not writable (%s): %s", self._config_dir, e)
                return False
            
            with open(self._config_file, "w", encoding="utf-8") as file:
                json.dump(self._config, file, indent=2)
            _LOG.info("Configuration saved to %s", self._config_file)
            return True
        except Exception as ex:
            _LOG.error("Failed to save configuration to %s: %s", self._config_file, ex)
            return False

    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "enabled_apps": [],
            "applications": {}
        }

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        self._config.update(new_config)

    def get_enabled_apps(self) -> List[str]:
        """Get list of enabled applications."""
        return self._config.get("enabled_apps", [])

    def set_enabled_apps(self, apps: List[str]) -> None:
        """Set enabled applications list."""
        self._config["enabled_apps"] = apps

    def get_app_config(self, app_name: str) -> Dict[str, Any]:
        """Get configuration for specific application."""
        return self._config.get("applications", {}).get(app_name, {})

    def set_app_config(self, app_name: str, config: Dict[str, Any]) -> None:
        """Set configuration for specific application."""
        if "applications" not in self._config:
            self._config["applications"] = {}
        
        app_config = self.APP_DEFAULTS.get(app_name, {}).copy()
        app_config.update(config)
        self._config["applications"][app_name] = app_config

    def get_app_url(self, app_name: str) -> str:
        """Get full URL for application."""
        app_config = self.get_app_config(app_name)
        if not app_config or "host" not in app_config:
            return ""
        
        protocol = "https" if app_config.get("ssl", False) else "http"
        host = app_config["host"]
        port = app_config.get("port", self.APP_DEFAULTS.get(app_name, {}).get("port", 80))
        url_base = app_config.get("url_base", "").strip("/")
        
        url = f"{protocol}://{host}:{port}"
        if url_base:
            url += f"/{url_base}"
        
        return url

    def get_app_api_key(self, app_name: str) -> str:
        """Get API key for application."""
        app_config = self.get_app_config(app_name)
        return app_config.get("api_key", "")

    def is_app_enabled(self, app_name: str) -> bool:
        """Check if application is enabled."""
        return app_name in self.get_enabled_apps()

    def get_all_enabled_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all enabled applications."""
        enabled_configs = {}
        for app_name in self.get_enabled_apps():
            config = self.get_app_config(app_name)
            if config and "host" in config and "api_key" in config:
                enabled_configs[app_name] = config
        return enabled_configs

    @property
    def config_file_path(self) -> str:
        """Get configuration file path."""
        return self._config_file


Config = NZBInfoConfig
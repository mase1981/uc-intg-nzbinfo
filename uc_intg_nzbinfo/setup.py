"""
Setup flow for NZB Info Manager Integration.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import ssl
from typing import Any, Dict, List

import aiohttp
import certifi
from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    IntegrationSetupError,
    RequestUserConfirmation,
    SetupAction,
    SetupComplete,
    SetupError,
    UserConfirmationResponse,
)

from uc_intg_nzbinfo.config import NZBInfoConfig

_LOG = logging.getLogger(__name__)


class NZBInfoSetup:
    """Setup flow handler for NZB Info integration."""

    APP_INFO = {
        "sabnzbd": {"name": "SABnzbd", "port": 8080, "description": "Usenet Downloader"},
        "nzbget": {"name": "NZBget", "port": 6789, "description": "Usenet Downloader"},
        "sonarr": {"name": "Sonarr", "port": 8989, "description": "TV Series Manager"},
        "radarr": {"name": "Radarr", "port": 7878, "description": "Movie Manager"},
        "lidarr": {"name": "Lidarr", "port": 8686, "description": "Music Manager"},
        "readarr": {"name": "Readarr", "port": 8787, "description": "Book Manager"},
        "bazarr": {"name": "Bazarr", "port": 6767, "description": "Subtitle Manager"},
        "overseerr": {"name": "Overseerr", "port": 5055, "description": "Request Manager"}
    }

    def __init__(self, config: NZBInfoConfig, api):
        """Initialize setup handler."""
        self._config = config
        self._api = api

    async def handle_setup(self, msg_data: Any) -> SetupAction:
        """Handle setup request."""
        try:
            if isinstance(msg_data, DriverSetupRequest):
                return await self._handle_driver_setup_request(msg_data)
            elif isinstance(msg_data, UserConfirmationResponse):
                return await self._handle_user_confirmation_response(msg_data)
            elif isinstance(msg_data, AbortDriverSetup):
                _LOG.info("Setup aborted by user or system.")
                return SetupError(msg_data.error)
            else:
                _LOG.error("Unknown setup message type: %s", type(msg_data))
                return SetupError(IntegrationSetupError.OTHER)

        except Exception as ex:
            _LOG.error("An unexpected error occurred during setup: %s", ex, exc_info=True)
            return SetupError(IntegrationSetupError.OTHER)

    def _parse_host_port_ssl(self, host_port: str, default_port: int) -> Dict[str, Any]:
        """Parse host:port string and detect SSL."""
        use_ssl = False
        clean_host_port = host_port.strip()

        if clean_host_port.startswith("https://"):
            use_ssl = True
            clean_host_port = clean_host_port[8:]
        elif clean_host_port.startswith("http://"):
            use_ssl = False
            clean_host_port = clean_host_port[7:]

        if ":" in clean_host_port:
            host, port_str = clean_host_port.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = default_port
        else:
            host = clean_host_port
            port = default_port

        return {
            "host": host.strip(),
            "port": port,
            "ssl": use_ssl
        }

    async def _handle_driver_setup_request(self, request: DriverSetupRequest) -> SetupAction:
        """Handle initial driver setup request."""
        _LOG.info("Starting NZB Info Manager setup (reconfigure: %s)", request.reconfigure)

        enabled_apps = []
        app_configs = {}

        _LOG.info(f"Raw setup_data received: {request.setup_data}")

        for app_name in self.APP_INFO.keys():
            enabled_key = f"{app_name}_enabled"
            host_key = f"{app_name}_host"
            api_key = f"{app_name}_api"

            is_enabled = request.setup_data.get(enabled_key, "false")
            if is_enabled == "true" or is_enabled is True:
                host_port = request.setup_data.get(host_key, "")
                api_value = request.setup_data.get(api_key, "")

                if host_port.strip():
                    enabled_apps.append(app_name)

                    parsed = self._parse_host_port_ssl(host_port, self.APP_INFO[app_name]["port"])

                    app_configs[app_name] = {
                        "host": parsed["host"],
                        "port": parsed["port"],
                        "api_key": api_value.strip(),
                        "ssl": parsed["ssl"],
                        "url_base": ""
                    }

                    protocol = "https" if parsed["ssl"] else "http"
                    _LOG.info(f"Configured {app_name}: {protocol}://{parsed['host']}:{parsed['port']} with API key: {'***' if api_value else 'empty'}")

        if not enabled_apps:
            _LOG.error("No applications configured properly")
            return SetupError(IntegrationSetupError.OTHER)

        connection_results = {}
        for app_name in enabled_apps:
            config = app_configs[app_name]
            test_result = await self._test_app_connection(app_name, config)
            connection_results[app_name] = test_result
            _LOG.info(f"Connection test for {app_name}: {test_result}")

        return await self._show_setup_summary(enabled_apps, app_configs, connection_results)

    async def _handle_user_confirmation_response(self, response: UserConfirmationResponse) -> SetupAction:
        """Handle user confirmation response."""
        if response.confirm:
            return await self._save_configuration()
        else:
            return AbortDriverSetup(IntegrationSetupError.OTHER)

    async def _test_app_connection(self, app_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection to application with proper SSL handling."""
        try:
            protocol = "https" if config.get("ssl", False) else "http"
            host = config.get("host", "")
            port = config.get("port", self.APP_INFO[app_name]["port"])
            url_base = config.get("url_base", "").strip("/")

            base_url = f"{protocol}://{host}:{port}"
            if url_base:
                base_url += f"/{url_base}"

            test_endpoints = {
                "sabnzbd": "/api?mode=version",
                "nzbget": "/jsonrpc",
                "sonarr": "/api/v3/system/status",
                "radarr": "/api/v3/system/status",
                "lidarr": "/api/v1/system/status",
                "readarr": "/api/v1/system/status",
                "bazarr": "/api/system/status",
                "overseerr": "/api/v1/status"
            }

            endpoint = test_endpoints.get(app_name, "/")
            test_url = f"{base_url}{endpoint}"

            headers = {}
            api_key = config.get("api_key", "")

            if api_key:
                if app_name == "sabnzbd":
                    separator = "&" if "?" in test_url else "?"
                    test_url += f"{separator}apikey={api_key}"
                elif app_name == "bazarr":
                    headers["X-API-KEY"] = api_key
                elif app_name in ["sonarr", "radarr", "lidarr", "readarr", "overseerr"]:
                    headers["X-Api-Key"] = api_key

            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            ) as session:
                _LOG.debug(f"Testing {app_name} at {test_url}")

                if app_name == "nzbget":
                    payload = {"method": "version", "params": [], "id": 1}
                    async with session.post(test_url, json=payload, headers=headers) as response:
                        _LOG.debug(f"{app_name} response: HTTP {response.status}")
                        if response.status in [200, 401]:
                            return {"success": True, "status": response.status}
                        else:
                            return {"success": False, "error": f"HTTP {response.status}"}
                else:
                    async with session.get(test_url, headers=headers) as response:
                        _LOG.debug(f"{app_name} response: HTTP {response.status}")
                        if response.status in [200, 401]:
                            return {"success": True, "status": response.status}
                        else:
                            return {"success": False, "error": f"HTTP {response.status}"}

        except aiohttp.ClientConnectorError as e:
            error_msg = f"Connection refused at {host}:{port}"
            _LOG.debug(f"{app_name} connection error: {e}")
            return {"success": False, "error": error_msg}
        except asyncio.TimeoutError:
            error_msg = f"Connection timeout to {host}:{port}"
            _LOG.debug(f"{app_name} timeout error")
            return {"success": False, "error": error_msg}
        except Exception as ex:
            error_msg = f"Connection error: {str(ex)[:50]}"
            _LOG.debug(f"{app_name} general error: {ex}")
            return {"success": False, "error": error_msg}

    async def _show_setup_summary(self, enabled_apps: List[str], app_configs: Dict[str, Dict[str, Any]], connection_results: Dict[str, Dict[str, Any]]) -> RequestUserConfirmation:
        """Show setup summary for user confirmation."""
        self._enabled_apps = enabled_apps
        self._app_configs = app_configs

        summary_lines = ["🎬 NZB Info Manager Setup Summary\\n"]

        for app_name in enabled_apps:
            app_info = self.APP_INFO[app_name]
            config = app_configs[app_name]
            result = connection_results[app_name]

            protocol = "https" if config.get("ssl", False) else "http"
            host = config.get("host", "N/A")
            port = config.get("port", app_info["port"])

            if result["success"]:
                summary_lines.append(f"✅ {app_info['name']}: {protocol}://{host}:{port} - Connected")
            else:
                error = result.get("error", "Unknown error")
                summary_lines.append(f"⚠️ {app_info['name']}: {protocol}://{host}:{port} - {error}")

        summary_lines.extend([
            "",
            "📝 Configuration will be saved and entities created.",
            "⚠️ Apps with connection issues will still be configured - you can fix them later."
        ])

        return RequestUserConfirmation(
            title={"en": "Confirm NZB Info Setup"},
            header={"en": "Setup Complete!"},
            footer={"en": "\\n".join(summary_lines)}
        )

    async def _save_configuration(self) -> SetupAction:
        """Save configuration and complete setup."""
        try:
            self._config.set_enabled_apps(self._enabled_apps)

            for app_name, config in self._app_configs.items():
                self._config.set_app_config(app_name, config)

            if not self._config.save_config():
                _LOG.error("Failed to save configuration")
                return SetupError(IntegrationSetupError.OTHER)

            _LOG.info(f"Configuration saved successfully for {len(self._enabled_apps)} applications")
            return SetupComplete()

        except Exception as ex:
            _LOG.error("Failed to save configuration: %s", ex)
            return SetupError(IntegrationSetupError.OTHER)
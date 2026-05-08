"""
NZB Info Manager setup flow.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import asyncio
import logging
import ssl
from typing import Any

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

from uc_intg_nzbinfo.config import APP_DEFAULTS, APP_DISPLAY, NZBInfoConfig

_LOG = logging.getLogger(__name__)


class NZBInfoSetupFlow:

    def __init__(self, driver):
        self._driver = driver
        self._pending_config: NZBInfoConfig | None = None

    async def handle_setup(self, msg: Any) -> SetupAction:
        try:
            if isinstance(msg, DriverSetupRequest):
                return await self._handle_setup_request(msg)
            elif isinstance(msg, UserConfirmationResponse):
                return await self._handle_confirmation(msg)
            elif isinstance(msg, AbortDriverSetup):
                _LOG.info("Setup aborted by user")
                return SetupError(IntegrationSetupError.OTHER)
            _LOG.error("Unknown setup message: %s", type(msg).__name__)
            return SetupError(IntegrationSetupError.OTHER)
        except Exception as e:
            _LOG.error("Setup error: %s", e, exc_info=True)
            return SetupError(IntegrationSetupError.OTHER)

    async def _handle_setup_request(self, request: DriverSetupRequest) -> SetupAction:
        _LOG.info("Processing NZB Info setup (reconfigure: %s)", request.reconfigure)
        enabled_apps = []
        app_configs: dict[str, dict] = {}

        for app_name in APP_DISPLAY.keys():
            enabled_key = f"{app_name}_enabled"
            host_key = f"{app_name}_host"
            api_key_field = f"{app_name}_api"

            is_enabled = request.setup_data.get(enabled_key, "false")
            if is_enabled in ("true", True):
                host_port = request.setup_data.get(host_key, "").strip()
                api_value = request.setup_data.get(api_key_field, "").strip()

                if host_port:
                    enabled_apps.append(app_name)
                    parsed = self._parse_host_port_ssl(host_port, APP_DEFAULTS.get(app_name, {}).get("port", 80))
                    app_configs[app_name] = {
                        "host": parsed["host"],
                        "port": parsed["port"],
                        "api_key": api_value,
                        "ssl": parsed["ssl"],
                        "url_base": "",
                    }

        if not enabled_apps:
            _LOG.error("No applications configured")
            return SetupError(IntegrationSetupError.OTHER)

        connection_results = {}
        for app_name in enabled_apps:
            result = await self._test_connection(app_name, app_configs[app_name])
            connection_results[app_name] = result
            _LOG.info("Connection test %s: %s", app_name, "OK" if result["success"] else result.get("error"))

        self._pending_config = NZBInfoConfig(
            identifier="nzbinfo",
            name="NZB Info Manager",
            enabled_apps=enabled_apps,
            applications=app_configs,
        )

        return self._build_confirmation(enabled_apps, app_configs, connection_results)

    async def _handle_confirmation(self, response: UserConfirmationResponse) -> SetupAction:
        if not response.confirm or not self._pending_config:
            self._pending_config = None
            return AbortDriverSetup(IntegrationSetupError.OTHER)

        try:
            for existing in list(self._driver.config_manager.all()):
                self._driver.config_manager.remove(existing.identifier)
            self._driver.config_manager.add_or_update(self._pending_config)
            _LOG.info("Configuration saved for %d apps", len(self._pending_config.enabled_apps))
            self._pending_config = None
            return SetupComplete()
        except Exception as e:
            _LOG.error("Failed to save configuration: %s", e)
            self._pending_config = None
            return SetupError(IntegrationSetupError.OTHER)

    def _parse_host_port_ssl(self, host_port: str, default_port: int) -> dict:
        use_ssl = False
        clean = host_port.strip()
        if clean.startswith("https://"):
            use_ssl = True
            clean = clean[8:]
        elif clean.startswith("http://"):
            clean = clean[7:]
        if ":" in clean:
            host, port_str = clean.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = default_port
        else:
            host = clean
            port = default_port
        return {"host": host.strip(), "port": port, "ssl": use_ssl}

    async def _test_connection(self, app_name: str, config: dict) -> dict:
        try:
            protocol = "https" if config.get("ssl", False) else "http"
            host = config["host"]
            port = config["port"]
            base_url = f"{protocol}://{host}:{port}"

            endpoints = {
                "sabnzbd": "/api?mode=version",
                "nzbget": "/jsonrpc",
                "sonarr": "/api/v3/system/status",
                "radarr": "/api/v3/system/status",
                "lidarr": "/api/v1/system/status",
                "readarr": "/api/v1/system/status",
                "bazarr": "/api/system/status",
                "overseerr": "/api/v1/status",
            }
            test_url = f"{base_url}{endpoints.get(app_name, '/')}"
            headers = {}
            api_key = config.get("api_key", "")

            if api_key:
                if app_name == "sabnzbd":
                    sep = "&" if "?" in test_url else "?"
                    test_url += f"{sep}apikey={api_key}"
                elif app_name == "bazarr":
                    headers["X-API-KEY"] = api_key
                elif app_name in ["sonarr", "radarr", "lidarr", "readarr", "overseerr"]:
                    headers["X-Api-Key"] = api_key

            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            timeout = aiohttp.ClientTimeout(total=15)

            async with aiohttp.ClientSession(
                timeout=timeout, connector=aiohttp.TCPConnector(ssl=ssl_ctx)
            ) as session:
                if app_name == "nzbget":
                    payload = {"method": "version", "params": [], "id": 1}
                    async with session.post(test_url, json=payload, headers=headers) as resp:
                        if resp.status in [200, 401]:
                            return {"success": True}
                        return {"success": False, "error": f"HTTP {resp.status}"}
                else:
                    async with session.get(test_url, headers=headers) as resp:
                        if resp.status in [200, 401]:
                            return {"success": True}
                        return {"success": False, "error": f"HTTP {resp.status}"}

        except aiohttp.ClientConnectorError:
            return {"success": False, "error": f"Connection refused at {host}:{port}"}
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Timeout to {host}:{port}"}
        except Exception as e:
            return {"success": False, "error": str(e)[:50]}

    def _build_confirmation(self, enabled_apps: list, app_configs: dict, results: dict) -> RequestUserConfirmation:
        lines = ["NZB Info Manager Setup Summary\n"]
        for app_name in enabled_apps:
            display = APP_DISPLAY.get(app_name, {}).get("name", app_name.title())
            cfg = app_configs[app_name]
            protocol = "https" if cfg.get("ssl") else "http"
            result = results[app_name]
            status = "Connected" if result["success"] else result.get("error", "Failed")
            icon = "OK" if result["success"] else "WARN"
            lines.append(f"[{icon}] {display}: {protocol}://{cfg['host']}:{cfg['port']} - {status}")

        lines.extend([
            "",
            "Configuration will be saved and entities created.",
            "Apps with connection issues will still be configured.",
        ])
        return RequestUserConfirmation(
            title={"en": "Confirm NZB Info Setup"},
            header={"en": "Setup Complete!"},
            footer={"en": "\n".join(lines)},
        )

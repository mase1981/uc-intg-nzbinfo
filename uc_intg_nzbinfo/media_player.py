"""
NZB Info media player entity.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import base64
import logging
import os
from typing import Any

from ucapi import StatusCodes, media_player
from ucapi_framework import MediaPlayerEntity

from uc_intg_nzbinfo.config import APP_DISPLAY, NZBInfoConfig
from uc_intg_nzbinfo.device import NZBInfoDevice

_LOG = logging.getLogger(__name__)

FEATURES = [
    media_player.Features.ON_OFF,
    media_player.Features.SELECT_SOURCE,
]


class NZBInfoMediaPlayer(MediaPlayerEntity):

    def __init__(self, device_config: NZBInfoConfig, device: NZBInfoDevice):
        self._device = device
        self._config = device_config
        self._icon_cache: dict[str, str] = {}

        self._source_list = ["System Overview"]
        for app in device_config.enabled_apps:
            self._source_list.append(APP_DISPLAY.get(app, {}).get("name", app.title()))

        entity_id = f"media_player.{device_config.identifier}"
        super().__init__(
            entity_id,
            device_config.name,
            FEATURES,
            {
                media_player.Attributes.STATE: media_player.States.STANDBY,
                media_player.Attributes.SOURCE: "",
                media_player.Attributes.SOURCE_LIST: [],
                media_player.Attributes.MEDIA_TITLE: "",
                media_player.Attributes.MEDIA_ARTIST: "",
                media_player.Attributes.MEDIA_IMAGE_URL: "",
            },
            device_class=media_player.DeviceClasses.RECEIVER,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.device_reachable:
            self.update({
                media_player.Attributes.STATE: media_player.States.OFF,
                media_player.Attributes.SOURCE_LIST: self._source_list,
                media_player.Attributes.SOURCE: "",
                media_player.Attributes.MEDIA_TITLE: "Connection Error",
                media_player.Attributes.MEDIA_ARTIST: "Unable to reach applications",
                media_player.Attributes.MEDIA_IMAGE_URL: self._get_icon_base64("system_overview.png"),
            })
            return

        attrs: dict[str, Any] = {
            media_player.Attributes.STATE: media_player.States.ON,
            media_player.Attributes.SOURCE_LIST: self._source_list,
            media_player.Attributes.SOURCE: self._device.current_source,
        }

        if self._device.current_source == "System Overview":
            self._build_overview(attrs)
        else:
            self._build_app_display(self._device.current_source, attrs)

        self.update(attrs)

    def _build_overview(self, attrs: dict) -> None:
        statuses = self._device.get_all_statuses()
        online = self._device.get_online_count()
        total = self._device.get_total_count()

        priority_info = "All applications monitored"
        for app_name in ["sabnzbd", "nzbget", "sonarr", "radarr", "lidarr", "readarr"]:
            if app_name in statuses:
                status = statuses[app_name]
                if status.is_online and "downloading" in status.primary_info.lower():
                    priority_info = f"{status.title}: {status.primary_info}"
                    break

        attrs[media_player.Attributes.MEDIA_TITLE] = f"NZB Info Manager ({online}/{total} online)"
        attrs[media_player.Attributes.MEDIA_ARTIST] = priority_info
        attrs[media_player.Attributes.MEDIA_IMAGE_URL] = self._get_icon_base64("system_overview.png")

    def _build_app_display(self, source: str, attrs: dict) -> None:
        app_name = self._get_app_name_from_source(source)
        if not app_name:
            attrs[media_player.Attributes.MEDIA_TITLE] = "Application not found"
            attrs[media_player.Attributes.MEDIA_ARTIST] = "Check configuration"
            attrs[media_player.Attributes.MEDIA_IMAGE_URL] = self._get_source_image(source)
            return

        status = self._device.get_app_status(app_name)
        if not status:
            attrs[media_player.Attributes.MEDIA_TITLE] = "Status unavailable"
            attrs[media_player.Attributes.MEDIA_ARTIST] = "Application not configured"
            attrs[media_player.Attributes.MEDIA_IMAGE_URL] = self._get_source_image(source)
            return

        if not status.is_online:
            attrs[media_player.Attributes.MEDIA_TITLE] = "Connection Error"
            attrs[media_player.Attributes.MEDIA_ARTIST] = f"Check {status.title} configuration"
        else:
            attrs[media_player.Attributes.MEDIA_TITLE] = status.primary_info
            attrs[media_player.Attributes.MEDIA_ARTIST] = status.secondary_info

        attrs[media_player.Attributes.MEDIA_IMAGE_URL] = self._get_source_image(source)

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        _LOG.debug("Media player command: %s params=%s", cmd_id, params)

        if cmd_id == media_player.Commands.OFF:
            self.update({media_player.Attributes.STATE: media_player.States.STANDBY})
            return StatusCodes.OK

        elif cmd_id == media_player.Commands.ON:
            self.update({media_player.Attributes.STATE: media_player.States.ON})
            return StatusCodes.OK

        elif cmd_id == media_player.Commands.SELECT_SOURCE:
            source = params.get("source") if params else None
            if source:
                self._device.current_source = source
                _LOG.info("Switched view to: %s", source)
                await self._device.poll_device()
            return StatusCodes.OK

        _LOG.debug("Ignoring unsupported command: %s", cmd_id)
        return StatusCodes.OK

    def _get_app_name_from_source(self, source: str) -> str:
        for app_name, info in APP_DISPLAY.items():
            if info["name"] == source:
                return app_name
        return ""

    def _get_source_image(self, source: str) -> str:
        if source == "System Overview":
            return self._get_icon_base64("system_overview.png")
        for app_name, info in APP_DISPLAY.items():
            if info["name"] == source:
                return self._get_icon_base64(info["icon"])
        return self._get_icon_base64("system_overview.png")

    def _get_icon_base64(self, icon_filename: str) -> str:
        if icon_filename in self._icon_cache:
            return self._icon_cache[icon_filename]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "icons", icon_filename)

        if not os.path.exists(icon_path):
            fallback = os.path.join(script_dir, "icons", "system_overview.png")
            if os.path.exists(fallback):
                icon_path = fallback
            else:
                return ""

        try:
            with open(icon_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
                result = f"data:image/png;base64,{data}"
                self._icon_cache[icon_filename] = result
                return result
        except Exception as e:
            _LOG.error("Failed to read icon %s: %s", icon_path, e)
            return ""

"""
NZB Info Manager Media Player Entity with optimized 2-row display.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""
import asyncio
import base64
import logging
import os
from typing import Callable

from ucapi import IntegrationAPI, MediaPlayer, StatusCodes, entity
from ucapi.media_player import Attributes, Commands, Features, States

from uc_intg_nzbinfo.client import NZBInfoClient
from uc_intg_nzbinfo.config import NZBInfoConfig

_LOG = logging.getLogger(__name__)

class NZBInfoPlayer(MediaPlayer):
    """A MediaPlayer entity representing NZB Info applications status with 2-row display."""

    APP_DISPLAY = {
        "sabnzbd": {"name": "SABnzbd", "icon": "sabnzbd.png"},
        "nzbget": {"name": "NZBget", "icon": "nzbget.png"},
        "sonarr": {"name": "Sonarr", "icon": "sonarr.png"},
        "radarr": {"name": "Radarr", "icon": "radarr.png"},
        "lidarr": {"name": "Lidarr", "icon": "lidarr.png"},
        "readarr": {"name": "Readarr", "icon": "readarr.png"},
        "bazarr": {"name": "Bazarr", "icon": "bazarr.png"},
        "overseerr": {"name": "Overseerr", "icon": "overseerr.png"}
    }

    def __init__(self, client: NZBInfoClient, config: NZBInfoConfig, api: IntegrationAPI):
        self._client = client
        self._config = config
        self._api = api
        self._icon_cache = {}
        
        features = [
            Features.ON_OFF,
            Features.SELECT_SOURCE,
        ]

        source_list = []
        enabled_apps = self._config.get_enabled_apps()
        
        if enabled_apps:
            source_list.append("System Overview")
        
        for app_name in enabled_apps:
            app_info = self.APP_DISPLAY.get(app_name, {"name": app_name.title()})
            source_list.append(app_info["name"])

        if not source_list:
            source_list = ["No Applications Configured"]

        super().__init__(
            identifier="nzb_info_monitor",
            name="NZB Info Manager",
            features=features,
            attributes={
                Attributes.STATE: States.ON,
                Attributes.SOURCE_LIST: source_list,
                Attributes.SOURCE: source_list[0] if source_list else "Overview",
                Attributes.MEDIA_TITLE: "Initializing...",
                Attributes.MEDIA_ARTIST: "Starting up...",
                Attributes.MEDIA_ALBUM: "Please wait...",
                Attributes.MEDIA_IMAGE_URL: self._get_icon_base64("system_overview.png"),
            },
            cmd_handler=self.handle_command
        )

    def _get_icon_base64(self, icon_filename: str) -> str:
        """Get the base64 encoded icon data."""
        if icon_filename in self._icon_cache:
            return self._icon_cache[icon_filename]

        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_dir = os.path.join(script_dir, "icons")
        icon_path = os.path.join(icon_dir, icon_filename)
        
        fallback_icons = ["system_overview.png", "sabnzbd.png"]

        if not os.path.exists(icon_path):
            _LOG.warning(f"Icon not found: {icon_filename}")
            for fallback in fallback_icons:
                icon_path = os.path.join(icon_dir, fallback)
                if os.path.exists(icon_path):
                    _LOG.info(f"Using fallback icon: {fallback}")
                    break
            else:
                _LOG.error("No fallback icons found in uc_intg_nzbinfo/icons/ directory")
                return ""

        try:
            with open(icon_path, 'rb') as f:
                icon_data = f.read()
                base64_data = base64.b64encode(icon_data).decode('utf-8')
                data_url = f"data:image/png;base64,{base64_data}"
                self._icon_cache[icon_filename] = data_url
                return data_url
        except Exception as e:
            _LOG.error(f"Failed to read icon {icon_path}: {e}")
            return ""

    def _get_source_image(self, source: str) -> str:
        """Get the proper base64 image data for a given source."""
        if source == "System Overview":
            return self._get_icon_base64("system_overview.png")
        
        for app_name, app_info in self.APP_DISPLAY.items():
            if app_info["name"] == source:
                return self._get_icon_base64(app_info["icon"])
        
        return self._get_icon_base64("system_overview.png")

    def _get_app_name_from_source(self, source: str) -> str:
        """Get internal app name from display source name."""
        for app_name, app_info in self.APP_DISPLAY.items():
            if app_info["name"] == source:
                return app_name
        return ""

    async def handle_command(self, entity_arg: entity.Entity, cmd_id: str, params: dict | None) -> StatusCodes:
        """Handle commands for the media player entity."""
        _LOG.debug(f"NZBInfoPlayer received command: {cmd_id}")
        
        if cmd_id == Commands.OFF:
            self.attributes[Attributes.STATE] = States.STANDBY
        elif cmd_id == Commands.ON:
            self.attributes[Attributes.STATE] = States.ON
        elif cmd_id == Commands.SELECT_SOURCE:
            source = params.get("source")
            if source:
                self.attributes[Attributes.SOURCE] = source
                self.attributes[Attributes.MEDIA_IMAGE_URL] = self._get_source_image(source)
                _LOG.info(f"Switched monitoring view to: {source}")
                
                await self._force_state_update()
                
        elif cmd_id in [Commands.PLAY_PAUSE, Commands.SHUFFLE, Commands.REPEAT, Commands.STOP, 
                       Commands.NEXT, Commands.PREVIOUS, Commands.VOLUME, Commands.VOLUME_UP, 
                       Commands.VOLUME_DOWN, Commands.MUTE_TOGGLE]:
            _LOG.debug(f"Ignoring unsupported media command '{cmd_id}' to prevent UI error.")
            return StatusCodes.OK
        else:
            _LOG.warning(f"Unhandled command: {cmd_id}")
            return StatusCodes.NOT_IMPLEMENTED
        
        await self.push_update()
        return StatusCodes.OK

    async def _force_state_update(self):
        """Force an immediate state update after source change."""
        try:
            await self._client.update_all_statuses()
            
            current_source = self.attributes.get(Attributes.SOURCE, "System Overview")
            
            fresh_attrs = {
                Attributes.STATE: States.ON,
                Attributes.SOURCE_LIST: self.attributes[Attributes.SOURCE_LIST],
                Attributes.SOURCE: current_source,
            }
            
            if current_source == "System Overview":
                await self._update_overview_display(fresh_attrs)
            else:
                await self._update_app_display_2row(current_source, fresh_attrs)
            
            self.attributes.update(fresh_attrs)
            
            if self._api.configured_entities.contains(self.id):
                self._api.configured_entities.update_attributes(self.id, fresh_attrs)
                
        except Exception as e:
            _LOG.error(f"Error in force state update: {e}")

    async def run_monitoring(self):
        """Periodically fetch data and update the entity."""
        while True:
            try:
                await self.push_update()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                _LOG.info("Monitoring task cancelled")
                break
            except Exception as e:
                _LOG.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def push_update(self):
        """Fetches the latest data and pushes it to the API."""
        if not self._api.configured_entities.contains(self.id):
            return

        if not await self._client.update_all_statuses():
            error_attrs = {
                Attributes.STATE: States.OFF,
                Attributes.MEDIA_TITLE: "Connection Error", 
                Attributes.MEDIA_ARTIST: "Unable to reach applications",
                Attributes.MEDIA_ALBUM: "Check configuration",
                Attributes.MEDIA_IMAGE_URL: self._get_icon_base64("system_overview.png")
            }
            self.attributes.update(error_attrs)
            self._api.configured_entities.update_attributes(self.id, error_attrs)
            return

        current_source = self.attributes.get(Attributes.SOURCE, "System Overview")
        
        attrs_to_update = {
            Attributes.STATE: States.ON,
            Attributes.SOURCE_LIST: self.attributes[Attributes.SOURCE_LIST],
            Attributes.SOURCE: current_source,
        }
        
        if current_source == "System Overview":
            await self._update_overview_display(attrs_to_update)
        else:
            await self._update_app_display_2row(current_source, attrs_to_update)
        
        self.attributes.update(attrs_to_update)
        self._api.configured_entities.update_attributes(self.id, attrs_to_update)
        
        _LOG.debug(f"Pushed display update for source: {current_source}")

    async def _update_overview_display(self, attrs_to_update: dict):
        """Update display for system overview."""
        statuses = self._client.get_all_statuses()
        
        if not statuses:
            attrs_to_update.update({
                Attributes.MEDIA_TITLE: "No Applications",
                Attributes.MEDIA_ARTIST: "No apps configured",
                Attributes.MEDIA_ALBUM: "Add apps in setup",
                Attributes.MEDIA_IMAGE_URL: self._get_icon_base64("system_overview.png")
            })
            return
        
        online_count = sum(1 for status in statuses.values() if status.is_online)
        total_count = len(statuses)
        
        priority_info = "All applications monitored"
        for app_name in ["sabnzbd", "nzbget", "sonarr", "radarr", "lidarr", "readarr"]:
            if app_name in statuses:
                status = statuses[app_name]
                if status.is_online and "downloading" in status.primary_info.lower():
                    priority_info = f"{status.title}: {status.primary_info}"
                    break
                elif status.is_online and "queue" in status.primary_info.lower() and "idle" not in status.primary_info.lower():
                    priority_info = f"{status.title}: {status.primary_info}"
                    break
        
        attrs_to_update.update({
            Attributes.MEDIA_TITLE: f"NZB Info Manager ({online_count}/{total_count} online)",
            Attributes.MEDIA_ARTIST: priority_info,
            Attributes.MEDIA_ALBUM: f"Last updated: {self._format_time_ago()}",
            Attributes.MEDIA_IMAGE_URL: self._get_icon_base64("system_overview.png")
        })

    async def _update_app_display_2row(self, source: str, attrs_to_update: dict):
        """Update display for specific application with 2-row format."""
        app_name = self._get_app_name_from_source(source)
        if not app_name:
            attrs_to_update.update({
                Attributes.MEDIA_TITLE: "Application not found",
                Attributes.MEDIA_ARTIST: "Check configuration", 
                Attributes.MEDIA_ALBUM: "",
                Attributes.MEDIA_IMAGE_URL: self._get_source_image(source)
            })
            return
        
        status = self._client.get_app_status(app_name)
        if not status:
            attrs_to_update.update({
                Attributes.MEDIA_TITLE: "Status unavailable",
                Attributes.MEDIA_ARTIST: "Application not configured",
                Attributes.MEDIA_ALBUM: "",
                Attributes.MEDIA_IMAGE_URL: self._get_source_image(source)
            })
            return
        
        if not status.is_online:
            row1_value = "Connection Error"
            row2_value = f"Check {status.title} configuration"
        else:
            row1_value = status.primary_info
            row2_value = status.secondary_info
        
        attrs_to_update.update({
            Attributes.MEDIA_TITLE: row1_value,
            Attributes.MEDIA_ARTIST: row2_value,
            Attributes.MEDIA_ALBUM: "",
            Attributes.MEDIA_IMAGE_URL: self._get_source_image(source)
        })

    def _format_time_ago(self) -> str:
        """Format time ago string."""
        import time
        
        now = time.time()
        diff = max(0, now - (now - 5))
        
        if diff < 60:
            return "just now"
        elif diff < 3600:
            minutes = int(diff / 60)
            return f"{minutes}m ago"
        else:
            hours = int(diff / 3600)
            return f"{hours}h ago"
"""
NZB Info Manager Integration Driver - REBOOT SURVIVAL FIXED.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""
import asyncio
import logging

import ucapi
from ucapi import AbortDriverSetup, DeviceStates, SetupAction, SetupComplete, SetupError
from ucapi.api_definitions import Events

from uc_intg_nzbinfo.media_player import NZBInfoPlayer
from uc_intg_nzbinfo.client import NZBInfoClient
from uc_intg_nzbinfo.config import NZBInfoConfig
from uc_intg_nzbinfo.setup import NZBInfoSetup

_LOG = logging.getLogger(__name__)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
API = ucapi.IntegrationAPI(loop)

# Global integration components
_config: NZBInfoConfig | None = None
_client: NZBInfoClient | None = None
_media_player: NZBInfoPlayer | None = None
_setup_manager: NZBInfoSetup | None = None
_monitoring_task: asyncio.Task | None = None


async def setup_handler(msg: SetupAction) -> SetupAction:
    """Handle integration setup flow and create entities."""
    global _config, _client, _media_player, _setup_manager

    if not _config:
        _config = NZBInfoConfig()
    if _setup_manager is None:
        _setup_manager = NZBInfoSetup(_config, API)

    action = await _setup_manager.handle_setup(msg)

    if isinstance(action, (SetupComplete, AbortDriverSetup, SetupError)):
        _setup_manager = None

    if isinstance(action, SetupComplete):
        _LOG.info("Setup confirmed. Initializing integration components...")
        await _initialize_integration()

    return action


async def _initialize_integration():
    """Initialize the integration components."""
    global _config, _client, _media_player

    _client = NZBInfoClient(_config)

    enabled_apps = _config.get_enabled_apps()
    if enabled_apps:
        _media_player = NZBInfoPlayer(_client, _config, API)
        API.available_entities.clear()
        API.available_entities.add(_media_player)
        _LOG.info("NZB Info Manager entity created and available.")
    else:
        _LOG.warning("No applications enabled, media player entity not created.")


@API.listens_to(Events.CONNECT)
async def on_connect() -> None:
    """Handle Remote Two connection with reboot survival."""
    global _config, _client, _media_player
    
    _LOG.info("Remote Two connected. Setting device state to CONNECTED.")
    await API.set_device_state(DeviceStates.CONNECTED)

    if not _config:
        _config = NZBInfoConfig()
    
    _config._load_config()
    enabled_apps = _config.get_enabled_apps()
    
    if enabled_apps and not API.available_entities.contains("nzb_info_monitor"):
        _LOG.info(f"Creating entities for {len(enabled_apps)} enabled apps after reboot")
        await _initialize_integration()
        
        if _client and await _client.connect():
            _LOG.info("Successfully connected to applications after reboot.")
        else:
            _LOG.warning("Failed to connect to some applications after reboot.")


@API.listens_to(Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]):
    """Handle entity subscriptions and start monitoring."""
    _LOG.info(f"Entities subscribed: {entity_ids}. Pushing initial state.")

    for entity_id in entity_ids:
        if _media_player and entity_id == _media_player.id:
            await _media_player.push_update()
            await start_monitoring_loop()


@API.listens_to(Events.DISCONNECT)
async def on_disconnect() -> None:
    """Handle Remote Two disconnection."""
    global _monitoring_task
    _LOG.info("Remote Two disconnected. Setting device state to DISCONNECTED.")
    await API.set_device_state(DeviceStates.DISCONNECTED)

    if _monitoring_task:
        _monitoring_task.cancel()
        _monitoring_task = None

    if _client and _client.is_connected:
        await _client.disconnect()


async def start_monitoring_loop():
    """Start the monitoring task if not already running."""
    global _monitoring_task
    if _monitoring_task is None or _monitoring_task.done():
        if _client and _media_player:
            _monitoring_task = asyncio.create_task(_media_player.run_monitoring())
            _LOG.info("NZB Info monitoring task started.")


async def main():
    """Main integration entry point."""
    logging.basicConfig(
        level=logging.DEBUG, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    _LOG.info(f"Starting NZB Info Manager Integration v{ucapi.__version__}")

    try:
        await API.init("driver.json", setup_handler)
        await API.set_device_state(DeviceStates.DISCONNECTED)

        _LOG.info("Driver initialized. Waiting for remote connection and setup.")
        await asyncio.Future()

    except asyncio.CancelledError:
        _LOG.info("Driver task cancelled.")
    finally:
        if _monitoring_task:
            _monitoring_task.cancel()
        if _client:
            await _client.disconnect()
        _LOG.info("NZB Info Manager Integration has stopped.")


if __name__ == "__main__":
    asyncio.run(main())
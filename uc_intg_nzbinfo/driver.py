"""
NZB Info Manager Integration Driver - FIXED PERSISTENCE FOR REMOTE REBOOT.

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

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

API = ucapi.IntegrationAPI(loop)
_config: NZBInfoConfig | None = None
_client: NZBInfoClient | None = None
_media_player: NZBInfoPlayer | None = None
_setup_manager: NZBInfoSetup | None = None
_monitoring_task: asyncio.Task | None = None


async def setup_handler(msg: SetupAction) -> SetupAction:
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


async def _load_existing_configuration():
    global _config, _client, _media_player

    _LOG.info("Attempting to load existing configuration...")

    if not _config:
        _config = NZBInfoConfig()
    else:
        _config._load_config()

    enabled_apps = _config.get_enabled_apps()
    _LOG.info(f"Found enabled apps in config: {enabled_apps}")

    if enabled_apps:
        _LOG.info(f"Found existing configuration with {len(enabled_apps)} enabled apps. Initializing...")

        await _initialize_integration()

        if _client:
            if await _client.connect():
                _LOG.info("Successfully connected to applications after config reload.")
                return True
            else:
                _LOG.warning("Failed to connect to applications, but entities created.")
                return True
        return True
    else:
        _LOG.info("No existing configuration found or no apps enabled.")
        return False


async def start_monitoring_loop():
    global _monitoring_task
    if _monitoring_task is None or _monitoring_task.done():
        if _client and _media_player:
            _monitoring_task = asyncio.create_task(_media_player.run_monitoring())
            _LOG.info("NZB Info monitoring task started.")


@API.listens_to(Events.CONNECT)
async def on_connect() -> None:
    _LOG.info("Remote Two connected. Setting device state to CONNECTED.")
    await API.set_device_state(DeviceStates.CONNECTED)

    config_loaded = await _load_existing_configuration()

    if config_loaded:
        _LOG.info("Successfully loaded existing configuration and created entities.")
        await API.set_device_state(DeviceStates.CONNECTED)
    else:
        _LOG.info("No existing configuration found. Setup required.")


@API.listens_to(Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]):
    _LOG.info(f"Entities subscribed: {entity_ids}. Pushing initial state.")

    for entity_id in entity_ids:
        if _media_player and entity_id == _media_player.id:
            await _media_player.push_update()
            await start_monitoring_loop()


@API.listens_to(Events.DISCONNECT)
async def on_disconnect() -> None:
    global _monitoring_task
    _LOG.info("Remote Two disconnected. Setting device state to DISCONNECTED.")
    await API.set_device_state(DeviceStates.DISCONNECTED)

    if _monitoring_task:
        _monitoring_task.cancel()
        _monitoring_task = None

    if _client and _client.is_connected:
        await _client.disconnect()


async def main():
    global _config
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
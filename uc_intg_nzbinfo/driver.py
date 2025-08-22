"""
NZB Info Manager Integration Driver.

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

api: ucapi.IntegrationAPI | None = None
_config: NZBInfoConfig | None = None
_client: NZBInfoClient | None = None
_media_player: NZBInfoPlayer | None = None
_setup_manager: NZBInfoSetup | None = None
_monitoring_task: asyncio.Task | None = None


async def setup_handler(msg: SetupAction) -> SetupAction:
    """Handle integration setup flow and create entities."""
    global _config, _setup_manager, _media_player, _client

    if not _config:
        _config = NZBInfoConfig()
    if _setup_manager is None:
        _setup_manager = NZBInfoSetup(_config, api)

    action = await _setup_manager.handle_setup(msg)

    if isinstance(action, (SetupComplete, AbortDriverSetup, SetupError)):
        _setup_manager = None

    if isinstance(action, SetupComplete):
        _LOG.info("Setup confirmed. Re-initializing integration components...")
        
        # After setup, the config has changed, so we need to reload it
        # and re-initialize everything, including creating a new media player instance.
        await _load_existing_configuration()

        if _media_player:
            await _media_player.push_update()
            await start_monitoring_loop()

    return action


async def _initialize_integration():
    """Initialize the integration's client and media player."""
    global _client, _media_player
    
    # This function now assumes _config and _media_player (the placeholder) already exist.
    # It just creates the client and links it.
    _client = NZBInfoClient(_config)
    
    # Update the existing media player with the new client and config.
    if _media_player:
        _media_player._client = _client
        _media_player._config = _config
        # Re-initialize source list based on new config
        enabled_apps = _config.get_enabled_apps()
        source_list = ["System Overview"] + [
            _media_player.APP_DISPLAY.get(app, {"name": app.title()})["name"] for app in enabled_apps
        ] if enabled_apps else ["No Applications Configured"]
        _media_player.attributes["source_list"] = source_list
        _media_player.attributes["source"] = source_list[0]

    _LOG.info("Integration components initialized.")


async def _load_existing_configuration() -> bool:
    """Load existing configuration from disk."""
    global _config
    _LOG.info("Attempting to load existing configuration from disk...")

    _config = NZBInfoConfig()
    enabled_apps = _config.get_enabled_apps()

    if enabled_apps:
        _LOG.info(f"Found existing configuration with {len(enabled_apps)} enabled apps.")
        await _initialize_integration()
        if _client:
            if await _client.connect():
                _LOG.info("Successfully connected to applications after config reload.")
            else:
                _LOG.warning("Failed to connect to applications, but entities were created.")
        return True
    else:
        _LOG.info("No existing configuration found or no apps enabled. Setup is required.")
        # Even with no config, we need to initialize to have a valid state
        await _initialize_integration()
        return False


async def start_monitoring_loop():
    """Start the monitoring task if not already running."""
    global _monitoring_task
    if _monitoring_task is None or _monitoring_task.done():
        if _client and _media_player:
            _monitoring_task = asyncio.create_task(_media_player.run_monitoring())
            _LOG.info("NZB Info monitoring task started.")


async def on_connect() -> None:
    """Handle Remote Two connection and restore state."""
    _LOG.info("Remote Two connected. Setting device state to CONNECTED.")
    await api.set_device_state(DeviceStates.CONNECTED)

    if await _load_existing_configuration():
        _LOG.info("Configuration loaded. Pushing initial state and starting monitoring.")
        if _media_player:
            await _media_player.push_update()
            await start_monitoring_loop()
    else:
        _LOG.info("Configuration not found. Pushing placeholder state.")
        if _media_player:
            await _media_player.push_update()


async def on_disconnect() -> None:
    """Handle Remote Two disconnection."""
    global _monitoring_task, _client
    _LOG.info("Remote Two disconnected. Setting device state to DISCONNECTED.")
    await api.set_device_state(DeviceStates.DISCONNECTED)

    if _monitoring_task:
        _monitoring_task.cancel()
        _monitoring_task = None
    if _client and _client.is_connected:
        await _client.disconnect()

    _client = None


async def main():
    """Main integration entry point."""
    global api, _config, _media_player
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    _LOG.info(f"Starting NZB Info Manager Integration v{ucapi.__version__}")

    try:
        loop = asyncio.get_running_loop()
        api = ucapi.IntegrationAPI(loop)

        # Create a placeholder configuration and media player entity immediately.
        # This resolves the race condition on initial connection.
        _config = NZBInfoConfig()
        _media_player = NZBInfoPlayer(None, _config, api)
        api.available_entities.add(_media_player)

        api.add_listener(Events.CONNECT, on_connect)
        api.add_listener(Events.DISCONNECT, on_disconnect)

        await api.init("driver.json", setup_handler)
        await api.set_device_state(DeviceStates.DISCONNECTED)

        _LOG.info("Driver initialized. Waiting for remote connection.")
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
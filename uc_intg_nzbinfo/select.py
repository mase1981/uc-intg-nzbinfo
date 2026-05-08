"""
NZB Info select entity for app switching.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from ucapi import StatusCodes, select
from ucapi_framework import SelectEntity

from uc_intg_nzbinfo.config import APP_DISPLAY, NZBInfoConfig
from uc_intg_nzbinfo.device import NZBInfoDevice

_LOG = logging.getLogger(__name__)


class NZBAppSelect(SelectEntity):

    def __init__(self, device_config: NZBInfoConfig, device: NZBInfoDevice):
        self._device = device
        self._options = ["System Overview"]
        for app in device_config.enabled_apps:
            self._options.append(APP_DISPLAY.get(app, {}).get("name", app.title()))

        entity_id = f"select.{device_config.identifier}.app"
        super().__init__(
            entity_id,
            f"{device_config.name} App Selector",
            {
                select.Attributes.STATE: select.States.UNKNOWN,
                select.Attributes.OPTIONS: [],
                select.Attributes.CURRENT_OPTION: "",
            },
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.device_reachable:
            self.update({
                select.Attributes.STATE: select.States.UNAVAILABLE,
                select.Attributes.OPTIONS: self._options,
                select.Attributes.CURRENT_OPTION: "",
            })
            return
        self.update({
            select.Attributes.STATE: select.States.ON,
            select.Attributes.OPTIONS: self._options,
            select.Attributes.CURRENT_OPTION: self._device.current_source,
        })

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict[str, Any] | None
    ) -> StatusCodes:
        match cmd_id:
            case select.Commands.SELECT_OPTION:
                option = params.get("option", "") if params else ""
                if option in self._options:
                    self._device.current_source = option
                    _LOG.info("App selector switched to: %s", option)
                    await self._device.poll_device()
                    return StatusCodes.OK
                return StatusCodes.BAD_REQUEST
            case select.Commands.SELECT_NEXT:
                idx = (self._options.index(self._device.current_source) + 1) % len(self._options)
                self._device.current_source = self._options[idx]
                _LOG.info("App selector next: %s", self._device.current_source)
                await self._device.poll_device()
                return StatusCodes.OK
            case select.Commands.SELECT_PREVIOUS:
                idx = (self._options.index(self._device.current_source) - 1) % len(self._options)
                self._device.current_source = self._options[idx]
                _LOG.info("App selector previous: %s", self._device.current_source)
                await self._device.poll_device()
                return StatusCodes.OK
            case _:
                return StatusCodes.NOT_IMPLEMENTED


def create_selects(config: NZBInfoConfig, device: NZBInfoDevice) -> list:
    return [NZBAppSelect(config, device)]

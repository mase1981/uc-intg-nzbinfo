"""
NZB Info sensor entities.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

import logging

from ucapi import sensor
from ucapi_framework import SensorEntity

from uc_intg_nzbinfo.config import APP_DISPLAY, NZBInfoConfig
from uc_intg_nzbinfo.device import NZBInfoDevice

_LOG = logging.getLogger(__name__)


class NZBAppSensor(SensorEntity):

    def __init__(self, device_config: NZBInfoConfig, device: NZBInfoDevice, app_name: str):
        self._device = device
        self._app_name = app_name
        display_name = APP_DISPLAY.get(app_name, {}).get("name", app_name.title())
        entity_id = f"sensor.{device_config.identifier}.{app_name}"
        super().__init__(
            entity_id,
            f"NZB {display_name}",
            [],
            {sensor.Attributes.STATE: sensor.States.UNKNOWN, sensor.Attributes.VALUE: ""},
            device_class=sensor.DeviceClasses.CUSTOM,
            options={sensor.Options.CUSTOM_UNIT: ""},
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.device_reachable:
            self.update({
                sensor.Attributes.STATE: sensor.States.UNAVAILABLE,
                sensor.Attributes.VALUE: "Offline",
            })
            return
        status = self._device.get_app_status(self._app_name)
        if not status or not status.is_online:
            self.update({
                sensor.Attributes.STATE: sensor.States.UNAVAILABLE,
                sensor.Attributes.VALUE: "Offline",
            })
            return
        self.update({
            sensor.Attributes.STATE: sensor.States.ON,
            sensor.Attributes.VALUE: status.primary_info,
        })


class NZBSystemSensor(SensorEntity):

    def __init__(self, device_config: NZBInfoConfig, device: NZBInfoDevice):
        self._device = device
        entity_id = f"sensor.{device_config.identifier}.system"
        super().__init__(
            entity_id,
            "NZB System Status",
            [],
            {sensor.Attributes.STATE: sensor.States.UNKNOWN, sensor.Attributes.VALUE: ""},
            device_class=sensor.DeviceClasses.CUSTOM,
            options={sensor.Options.CUSTOM_UNIT: ""},
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.device_reachable:
            self.update({
                sensor.Attributes.STATE: sensor.States.UNAVAILABLE,
                sensor.Attributes.VALUE: "All apps offline",
            })
            return
        online = self._device.get_online_count()
        total = self._device.get_total_count()
        self.update({
            sensor.Attributes.STATE: sensor.States.ON,
            sensor.Attributes.VALUE: f"{online}/{total} apps online",
        })


def create_sensors(config: NZBInfoConfig, device: NZBInfoDevice) -> list:
    sensors = []
    for app_name in config.enabled_apps:
        sensors.append(NZBAppSensor(config, device, app_name))
    sensors.append(NZBSystemSensor(config, device))
    return sensors

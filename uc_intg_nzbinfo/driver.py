"""
NZB Info Manager integration driver.

:copyright: (c) 2025 by Meir Miyara.
:license: MPL-2.0, see LICENSE for more details.
"""

from ucapi_framework import BaseIntegrationDriver

from uc_intg_nzbinfo.config import NZBInfoConfig
from uc_intg_nzbinfo.device import NZBInfoDevice
from uc_intg_nzbinfo.media_player import NZBInfoMediaPlayer
from uc_intg_nzbinfo.select import create_selects
from uc_intg_nzbinfo.sensor import create_sensors


class NZBInfoDriver(BaseIntegrationDriver[NZBInfoDevice, NZBInfoConfig]):

    def __init__(self):
        super().__init__(
            device_class=NZBInfoDevice,
            entity_classes=[
                NZBInfoMediaPlayer,
                lambda cfg, dev: create_sensors(cfg, dev),
                lambda cfg, dev: create_selects(cfg, dev),
            ],
            driver_id="uc_intg_nzbinfo",
        )

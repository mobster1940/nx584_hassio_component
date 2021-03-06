"""Support for NX584 alarm control panels."""
from datetime import timedelta
import logging
import json

from custom_components.nx584_custom.pynx584.nx584 import client
import requests
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

CONF_PARTITION = "partition"

DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Alarm"
DEFAULT_PORT = 5007
DEFAULT_PARTITION = 1
SERVICE_BYPASS_ZONE = "bypass_zone"
SERVICE_UNBYPASS_ZONE = "unbypass_zone"
ATTR_ZONE = "zone"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_PARTITION, default=DEFAULT_PARTITION): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the NX584 platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    partition = config.get(CONF_PARTITION)

    url = f"http://{host}:{port}"

    try:
        alarm_client = client.Client(url)
        await hass.async_add_executor_job(alarm_client.list_zones)
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error(
            "Unable to connect to %(host)s: %(reason)s", dict(host=url, reason=ex),
        )
        raise PlatformNotReady

    entity = NX584Alarm(name, alarm_client, url, partition)
    async_add_entities([entity])

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_BYPASS_ZONE, {vol.Required(ATTR_ZONE): cv.positive_int}, "alarm_bypass",
    )

    platform.async_register_entity_service(
        SERVICE_UNBYPASS_ZONE,
        {vol.Required(ATTR_ZONE): cv.positive_int},
        "alarm_unbypass",
    )


class NX584Alarm(alarm.AlarmControlPanelEntity):
    """Representation of a NX584-based alarm panel."""

    def __init__(self, name, alarm_client, url, partition):
        """Init the nx584 alarm panel."""
        self._name = name
        self._state = None
        self._alarm = alarm_client
        self._url = url
        self._part = partition

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return alarm.FORMAT_NUMBER

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def update(self):
        """Process new events from panel."""
        part = self._part
        try:
            partitions = self._alarm.list_partitions()
            for s in range(len(partitions)):
                if partitions[s]["number"] == self._part:
                    part = partitions[s]
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error(
                "Unable to connect to %(host)s: %(reason)s",
                dict(host=self._url, reason=ex),
            )
            self._state = None
        except IndexError:
            _LOGGER.error("NX584 reports no partitions")
            self._state = None

        
        if not part["armed"]:
            self._state = STATE_ALARM_DISARMED
        else:
            if 'Siren on' in part["condition_flags"]:
                self._state = STATE_ALARM_TRIGGERED
            elif 'Entryguard (stay mode)' in part["condition_flags"]:
                self._state = STATE_ALARM_ARMED_HOME
            else:
                self._state = STATE_ALARM_ARMED_AWAY

        

    def alarm_disarm(self, code=None, partition = 1):
        """Send disarm command."""
        self._alarm.disarm(code, self._part)

    def alarm_arm_home(self, code=None, partition = 1):
        """Send arm home command."""
        self._alarm.arm("stay", self._part)

    def alarm_arm_away(self, code=None, partition = 1):
        """Send arm away command."""
        self._alarm.arm("exit", self._part)

    def alarm_bypass(self, zone):
        """Send bypass command."""
        self._alarm.set_bypass(zone, True)

    def alarm_unbypass(self, zone):
        """Send bypass command."""
        self._alarm.set_bypass(zone, False)

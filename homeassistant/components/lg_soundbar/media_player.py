"""Support for LG soundbars."""
from __future__ import annotations

import temescal

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media_player from a config entry created in the integrations UI."""
    async_add_entities(
        [
            LGDevice(
                config_entry.data[CONF_HOST],
                config_entry.data[CONF_PORT],
                config_entry.unique_id,
            )
        ]
    )


class LGDevice(MediaPlayerEntity):
    """Representation of an LG soundbar device."""

    _attr_should_poll = False
    _attr_state = MediaPlayerState.ON
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )

    def __init__(self, host, port, unique_id):
        """Initialize the LG speakers."""
        self._host = host
        self._port = port
        self._attr_unique_id = unique_id

        self._volume = 0
        self._volume_min = 0
        self._volume_max = 0
        self._function = -1
        self._functions = []
        self._equaliser = -1
        self._equalisers = []
        self._mute = 0
        self._rear_volume = 0
        self._rear_volume_min = 0
        self._rear_volume_max = 0
        self._woofer_volume = 0
        self._woofer_volume_min = 0
        self._woofer_volume_max = 0
        self._bass = 0
        self._treble = 0
        self._device = None

    async def async_added_to_hass(self) -> None:
        """Register the callback after hass is ready for it."""
        await self.hass.async_add_executor_job(self._connect)

    def _connect(self) -> None:
        """Perform the actual devices setup."""
        self._device = temescal.temescal(
            self._host, port=self._port, callback=self.handle_event
        )
        self._device.get_product_info()
        self._device.get_mac_info()
        self.update()

    def get_value(self, data, key, default_value):
        """Get value from data object if key exists."""
        return data[key] if key in data else default_value

    def handle_eq_view_info_event(self, data):
        """Set values for EQ_VIEW_INFO event response."""
        self._bass = self.get_value(data, "i_bass", self._bass)
        self._treble = self.get_value(data, "i_treble", self._treble)
        self._equalisers = self.get_value(data, "ai_eq_list", self._equalisers)
        self._equaliser = self.get_value(data, "i_curr_eq", self._equaliser)

    def handle_spk_list_view_info_event(self, data):
        """Set values for SPK_LIST_VIEW_INFO event response."""
        self._volume = self.get_value(data, "i_vol", self._volume)
        self._volume_min = self.get_value(data, "i_vol_min", self._volume_min)
        self._volume_max = self.get_value(data, "i_vol_max", self._volume_max)
        self._function = self.get_value(data, "i_curr_func", self._function)
        if "b_powerstatus" in data:
            if data["b_power_status"]:
                self._attr_state = MediaPlayerState.ON
            else:
                self._attr_state = MediaPlayerState.OFF

    def handle_func_view_info_event(self, data):
        """Set values for FUNC_VIEW_INFO event response."""
        self._function = self.get_value(data, "i_curr_func", self._function)
        self._functions = self.get_value(data, "ai_func_list", self._functions)

    def handle_setting_view_info_event(self, data):
        """Set values for SETTING_VIEW_INFO event response."""
        self._rear_volume_min = self.get_value(
            data, "i_rear_min", self._rear_volume_min
        )
        self._rear_volume_max = self.get_value(
            data, "i_rear_max", self._rear_volume_max
        )
        self._rear_volume = self.get_value(data, "i_rear_level", self._rear_volume)
        self._woofer_volume_min = self.get_value(
            data, "i_woofer_min", self._woofer_volume_min
        )
        self._woofer_volume_max = self.get_value(
            data, "i_woofer_max", self._woofer_volume_max
        )
        self._woofer_volume = self.get_value(
            data, "i_woofer_level", self._woofer_volume
        )
        self._equaliser = self.get_value(data, "i_curr_eq", self._equaliser)
        self._attr_name = self.get_value(data, "s_user_name", self._attr_name)

    def handle_event(self, response):
        """Handle responses from the speakers."""
        data = response["data"]
        if response["msg"] == "EQ_VIEW_INFO":
            self.handle_eq_view_info_event(data)
        elif response["msg"] == "SPK_LIST_VIEW_INFO":
            self.handle_spk_list_view_info_event(data)
        elif response["msg"] == "FUNC_VIEW_INFO":
            self.handle_func_view_info_event(data)
        elif response["msg"] == "SETTING_VIEW_INFO":
            self.handle_setting_view_info_event(data)

        self.schedule_update_ha_state()

    def update(self) -> None:
        """Trigger updates from the device."""
        self._device.get_eq()
        self._device.get_info()
        self._device.get_func()
        self._device.get_settings()

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if self._volume_max != 0:
            return self._volume / self._volume_max
        return 0

    @property
    def is_volume_muted(self) -> bool | None:
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        if self._equaliser == -1 or self._equaliser >= len(temescal.equalisers):
            return None
        return temescal.equalisers[self._equaliser]

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return the available sound modes."""
        modes = []
        for equaliser in self._equalisers:
            if equaliser < len(temescal.equalisers):
                modes.append(temescal.equalisers[equaliser])
        return sorted(modes)

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if self._function == -1 or self._function >= len(temescal.functions):
            return None
        return temescal.functions[self._function]

    @property
    def source_list(self) -> list[str] | None:
        """List of available input sources."""
        sources = []
        for function in self._functions:
            if function < len(temescal.functions):
                sources.append(temescal.functions[function])
        return sorted(sources)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        volume = volume * self._volume_max
        self._device.set_volume(int(volume))

    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self._device.set_mute(mute)

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._device.set_func(temescal.functions.index(source))

    def select_sound_mode(self, sound_mode: str) -> None:
        """Set Sound Mode for Receiver.."""
        self._device.set_eq(temescal.equalisers.index(sound_mode))

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._set_power(True)

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._set_power(False)

    def _set_power(self, status) -> None:
        """Set the media player state."""
        self._device.send_packet(
            {"cmd": "set", "data": {"b_powerkey": status}, "msg": "SPK_LIST_VIEW_INFO"}
        )

"""Device model for Lawo MCX devices"""

import asyncio
import logging
from enum import IntEnum
from math import log10
from typing import Optional, Type, TypeVar

# Datamodels
import systemlink.datamodel.audiosystem as DAudioSystem
import systemlink.datamodel.base as DBase
import systemlink.datamodel.console as DConsole
import systemlink.datamodel.signal as DSignal
import systemlink.datamodel.system as DSystem
from systemlink.common.m_lookup import MNumberLookup as MNumber
from systemlink.common.mcx_com import MNNumber
from systemlink.common.systemlink_socket import ConnectionTimout
from systemlink.datamodel.channel import (Funktionseinheiten,
                                          FunktionseinheitType,
                                          FunktionseinheitTypes)
# Systemlink
from systemlink.systemlink import WAIT_FOR_RESPONSE_TIMEOUT, SystemLink

from ldf.models.base import (ClientConfig, HomeNativeDeviceSpec,
                             LawoHomeNativeDevice)
from ldf.models.uhd_core import LawoGroupableDevice

__all__ = ["LawoMCXDevice", "LawoMCXDeviceHelper"]

T = TypeVar("T", bound=DBase.BaseDataType)


class LawoMCXDeviceHelper:
    # pylint: disable=invalid-name
    # ---------------------------------------------------------------------------- #
    #                                  Conversions                                 #
    # ---------------------------------------------------------------------------- #

    # ------------------------------------ Hz ------------------------------------ #
    @staticmethod
    def to_lawo_Hz(Hz: int) -> int:
        """Convert Hz to Lawo Hz

        Lawo Hz is a logarithmic representation of Hz in the MCX database.
        """

        return round(1638.0 * log10(Hz))

    @staticmethod
    def from_lawo_Hz(lawo_Hz: int) -> int:
        """Convert Lawo Hz to Hz

        Lawo Hz is a logarithmic representation of Hz in the MCX database.
        """

        return round(10 ** (lawo_Hz / 1638.0))

    # ------------------------------------- Q ------------------------------------ #
    @staticmethod
    def to_lawo_Q(Q: float) -> int:
        return round(64.0 * Q)

    @staticmethod
    def from_lawo_Q(lawo_Q: int) -> float:
        return round(lawo_Q / 64.0)

    # ------------------------------------- s ------------------------------------ #
    @staticmethod
    def to_lawo_s(s: float) -> int:
        """Convert seconds to Lawo s

        Lawo s is a representation of seconds in the MCX database.
        """

        return round(48000.0 * s)

    @staticmethod
    def from_lawo_s(lawo_s: int) -> float:
        """Convert Lawo s to seconds

        Lawo s is a representation of seconds in the MCX database.
        """

        return round(lawo_s / 48000.0)

    # ------------------------------------ ms ------------------------------------ #
    @staticmethod
    def to_lawo_ms(ms: float) -> int:
        """Convert milliseconds to Lawo ms

        Lawo ms is a representation of milliseconds in the MCX database.
        """

        return round(48.0 * ms)

    @staticmethod
    def from_lawo_ms(lawo_ms: int) -> float:
        """Convert Lawo ms to milliseconds

        Lawo ms is a representation of milliseconds in the MCX database.
        """

        return round(lawo_ms / 48.0)

    # ------------------------------------ dB ------------------------------------ #
    @staticmethod
    def to_lawo_dB(dB: float) -> int:
        """Convert dB to Lawo dB

        Lawo dB is a representation of dB in the MCX database.
        """

        return round(32.0 * dB)

    @staticmethod
    def from_lawo_dB(lawo_dB: float) -> float:
        """Convert Lawo dB to dB

        Lawo dB is a representation of dB in the MCX database.
        """

        return round(lawo_dB / 32.0, 2)

    # ----------------------------------- ratio ---------------------------------- #
    @staticmethod
    def to_lawo_ratio(ratio: float) -> int:
        return round(2048.0 * log10(ratio))

    @staticmethod
    def from_lawo_ratio(lawo_ratio: int) -> float:
        return 10 ** (lawo_ratio / 2048.0)

    # ------------------------------------- m ------------------------------------ #
    @staticmethod
    def to_lawo_m(m: float) -> int:
        return round(8192 * log10(m))

    @staticmethod
    def from_lawo_m(lawo_m: int) -> float:
        return 10 ** (lawo_m / 8192.0)

    # --------------------------------------------------------------------------- #
    @staticmethod
    def create_fu_signal_string(fu_index: int) -> str:
        fu_type = FunktionseinheitType.get_fu_type(fu_index)
        fu_number = fu_index - FunktionseinheitType.get_fu_base_by_type(fu_type)

        return f"{fu_type.name} {fu_number}"


class LawoMCXDevice(LawoHomeNativeDevice, LawoGroupableDevice):

    _version: DSystem.SystemCsVersion
    _systemlink_connection: SystemLink
    _home_connection: bool
    _log: logging.Logger

    def __init__(
        self,
        client_cfg: ClientConfig | None = None,
        home_connection: bool = True
    ):
        """Create a new Lawo MCX device

        Args:
            nats_port (int, optional): Nats Port.
            home_connection (bool, optional): Create a Home Connection.
        """

        self._log = logging.getLogger(__name__)
        self._home_connection = home_connection

        if self._home_connection and client_cfg:
            super().__init__(client_cfg)
            self.spec = HomeNativeDeviceSpec(
                type_number="",
                model="mcx",
                flags={
                    "IsPhysical": True,
                    "IsStreamer": True,
                    "IsAudioConsole": True,
                    "CanBeGrouped": True,
                    "CreateDeleteSords": True,
                    "InternalRouting": True,
                    "GPIO": True,
                },
            )

    @property
    def version(self):
        """Get the version of the connected MCX device

        If no connection is established, None is returned.
        """

        return self._version

    async def _home_registered_active_interface_address(self) -> str:
        """Get the active interface address from Home"""
        if not self._home_connection:
            raise ValueError('Home connection is not enabled')

        interfaces = list(self.interfaces())
        if not interfaces:
            raise ConnectionTimout('No interfaces found from Home')

        address = interfaces[0].ip_address

        if address is None:
            raise ConnectionTimout('No active interface found from Home')

        return address

    async def connect(
        self, host_address: Optional[str] = None, host_port: Optional[int] = None, systemlink: bool = True
    ):
        """Connect to the MCX device systemlink

        Args:
            host_address (str, optional): Network address to MCX. Defaults to network interface detected by HOME.
            host_port (int, optional): Systemlink Port.
        """

        # -------------------------------- SYSTEMLINK -------------------------------- #

        if systemlink:
            await self.connect_systemlink(host_address, host_port)

    async def disconnect(self):
        # -------------------------------- SYSTEMLINK -------------------------------- #

        if self._systemlink_connection:
            await self._systemlink_connection.close()

    # ---------------------------------------------------------------------------- #
    #                                  SYSTEMLINK                                  #
    # ---------------------------------------------------------------------------- #

    async def connect_systemlink(self, host_address: Optional[str] = None, host_port: Optional[int] = None):
        """Connect to the MCX device systemlink

        Args:
            host_address (str, optional): Network address to MCX. Defaults to network interface detected by HOME.
            host_port (int, optional): Systemlink Port.
        """

        if host_address is None:
            if not self._home_connection:
                raise ValueError("You must set a Host Address when Home connection is turned off")
            host_address = await self._home_registered_active_interface_address()

        if not host_port:
            self._systemlink_connection = SystemLink(remote=host_address)
        else:
            self._systemlink_connection = SystemLink(remote=host_address, port=host_port)

        await asyncio.wait_for(self._systemlink_connection.connect(), timeout=5)
        self._version = await self.get_version()

    def mcx_event(self, m_number: MNumber | int, n_number: int, data) -> None:
        """Execute an mcx_event command"""
        self._systemlink_connection.mcx_event(m_number, n_number, data)

    async def mcx_get(self, m_number: MNumber | int, n_number: int, data_type: Type[T]) -> T:
        """Execute an mcx_get command and wait and return the result"""
        return await self._systemlink_connection.mcx_get(m_number, n_number, data_type)

    async def wait_for(
        self,
        m_number: MNumber | int,
        open_stream: bool = False,
        response_iterations: int = 1,
        response_timeout: float = WAIT_FOR_RESPONSE_TIMEOUT,
    ):
        """Wait for an event with the given M-Number"""
        await self._systemlink_connection.wait_for(
            m_number,
            open_stream=open_stream,
            response_iterations=response_iterations,
            response_timeout=response_timeout,
        )

    async def get_version(self) -> DSystem.SystemCsVersion:
        """Get the version of the connected MCX device"""
        return await self.mcx_get(MNumber.SYSTEM_CS_VERSION_INT, 0, data_type=DSystem.SystemCsVersion)

    def toggle_button_no_wait(self, m_number: MNumber | int, n_number: int):
        self._log.debug("Toggling (no wait) %s", MNNumber(m_number, n_number))
        self._systemlink_connection.mcx_event(m_number, n_number, DBase.MCX_STATE8(1))
        self._systemlink_connection.mcx_event(m_number, n_number, DBase.MCX_STATE8(0))

    async def toggle_button(self, m_number: MNumber | int, n_number: int, hold_time: float = 0.1):
        self._log.debug("Toggling %s", MNNumber(m_number, n_number))

        self._systemlink_connection.mcx_event(m_number, n_number, DBase.MCX_STATE8(1))

        await asyncio.sleep(hold_time)

        self._systemlink_connection.mcx_event(m_number, n_number, DBase.MCX_STATE8(0))

    async def get_lamp_state(self, m_number: MNumber | int, n_number: int) -> DConsole.LampState:
        """Retrieve the lamp state of a button."""
        lamp = await self.mcx_get(m_number, n_number, DConsole.Lamp)
        return lamp.state

    async def toggle_button_to(self, m_number: MNumber | int, n_number: int, state: DConsole.LampState):
        """Toggle a button to a specific state. (max 5 attempts)"""
        self._log.debug("Toggling %s to %s", MNNumber(m_number, n_number), state.name)
        # Get current LAMP state
        current_state = await self.get_lamp_state(m_number, n_number)

        # If current state is equal to the desired state, do nothing
        if current_state == state:
            return

        # Otherwise, toggle the button (max 5 times)
        attempts = 0

        while current_state != state:
            if attempts > 5:
                raise ValueError(f"Could not reach desired button state: {state}")
            await self.toggle_button(m_number, n_number)
            await asyncio.sleep(0.1)
            current_state = await self.get_lamp_state(m_number, n_number)
            self._log.debug("Current state: %s, Desired state: %s", current_state.name, state.name)
            attempts += 1

    async def toggle_button_from(self, m_number: MNumber | int, n_number: int, state: DConsole.LampState):
        """Toggle a button from a specific state. Only 1 attempt."""
        self._log.debug("Toggling %s from %s", MNNumber(m_number, n_number), state)
        # Get current LAMP state
        current_state = await self.get_lamp_state(m_number, n_number)

        # If current state is not equal to the desired state, do nothing
        if current_state != state:
            return

        # Otherwise, toggle the button
        await self.toggle_button(m_number, n_number)

        # Check if the state has changed
        current_state = await self.get_lamp_state(m_number, n_number)

        if current_state == state:
            raise ValueError(f"Could not toggle button state: {state}")

    async def set_button_state(self, m_number: MNumber | int, n_number: int, on: bool):
        if on:
            await self.set_button_on(m_number, n_number)
        else:
            await self.set_button_off(m_number, n_number)

    async def set_button_on(self, m_number: MNumber | int, n_number: int):
        """Set a button to ON state. (Every state except LAMP_BLACK)"""
        self._log.debug("Setting %s to ON", MNNumber(m_number, n_number))
        await self.toggle_button_from(m_number, n_number, DConsole.LampState.LAMP_BLACK)

    async def set_button_off(self, m_number: MNumber | int, n_number: int):
        """Set a button to OFF state. (toggle_button_to LAMP_BLACK - 5 attempts)"""
        await self.toggle_button_to(m_number, n_number, DConsole.LampState.LAMP_BLACK)

    async def set_and_check(
        self,
        m_number: MNumber | int,
        n_number: int,
        data: DBase.BaseDataType,
        message: str = "",
        retries: int = 1,
    ):
        self._log.debug("Setting %s - %s to %s", message, MNNumber(m_number, n_number), data)
        try:
            self.mcx_event(m_number, n_number, data)
            await asyncio.sleep(0)

            try:
                check = await self.mcx_get(m_number, n_number, type(data))
            except asyncio.TimeoutError as ex:
                if self._systemlink_connection.is_connected:
                    raise ValueError(f"Setting failed. No respond. {message} {MNNumber(m_number, n_number)}") from ex
                raise ex

            for check_d, data_d in zip(check.data, data.data):
                assert check_d.value == data_d.value, (
                    f"Setting failed - {message} - {MNNumber(m_number, n_number)}, "
                    f"expected: {data_d.value} got: {check_d.value}"
                )

        except Exception as ex:
            if retries > 0:
                await asyncio.sleep(0.1)
                return await self.set_and_check(m_number, n_number, data, message, retries - 1)
            raise ex

    async def set_and_check_not(
        self, m_number: MNumber | int, n_number: int, data: DBase.BaseDataType, message: str = ""
    ):
        self.mcx_event(m_number, n_number, data)
        await asyncio.sleep(0)
        check = await self.mcx_get(m_number, n_number, type(data))

        for check_d, data_d in zip(check.data, data.data):
            assert check_d.value != data_d.value, (
                f"Setting failed - {message} - {MNNumber(m_number, n_number)}, "
                f"expected: {data_d.value} got: {check_d.value}"
            )

    async def assert_MND(self, m_number: MNumber | int, n_number: int, data: DBase.BaseDataType, message: str = ""):
        check = await self.mcx_get(m_number, n_number, type(data))

        for check_d, data_d in zip(check.data, data.data):
            assert check_d.value == data_d.value, (
                f"Assertion MND failed - {message} - {MNNumber(m_number, n_number)}, "
                f"expected: {data_d.value} got: {check_d.value}"
            )

    async def assert_MND_not(self, m_number: MNumber | int, n_number: int, data: DBase.BaseDataType, message: str = ""):
        check = await self.mcx_get(m_number, n_number, type(data))

        if len(check.data) != len(data.data):
            assert True
            return

        for check_d, data_d in zip(check.data, data.data):
            if check_d.value != data_d.value:
                assert True
                return

        assert False, f"Assertion MND NOT failed - {message} - {MNNumber(m_number, n_number)}, {data} equals {check}"

    # ---------------------------------------------------------------------------- #
    #                                SYSTEM COMMANDS                               #
    # ---------------------------------------------------------------------------- #
    async def mcx_shutdown(self):
        self._systemlink_connection.mcx_event(MNumber.SYSTEM_SHUTDOWN, 0, DBase.BoolType(False))

    async def mcx_shutdown_cold(self):
        self._systemlink_connection.mcx_event(MNumber.SYSTEM_SHUTDOWN, 0, DBase.BoolType(True))

    # ---------------------------------------------------------------------------- #
    #                                  AUTOMATION                                  #
    # ---------------------------------------------------------------------------- #
    def mcx_set_automation(self, state: bool):
        self._log.debug("Setting Automation to %s", state)
        self.mcx_event(MNumber.AUTOMATION_GLOBAL_AUTOMATION_ON, 0, DBase.MCX_KEYS(state))

    # ---------------------------------------------------------------------------- #
    #                                SIGNAL CONNECT                                #
    # ---------------------------------------------------------------------------- #

    def mcx_connect(self, source: DSignal.UniqueSignalAddress, target: DSignal.UniqueSignalAddress):

        if not isinstance(source, DSignal.UniqueSignalAddress) or not isinstance(target, DSignal.UniqueSignalAddress):
            raise TypeError("Source and Target must be of type UniqueSignalAddress")

        self.mcx_event(MNumber.SIGNAL_TARGET_MAIN_SOURCE, target.address, source)

    def mcx_disconnect(self, target):
        if not isinstance(target, DSignal.UniqueSignalAddress):
            raise TypeError("Target must be of type UniqueSignalAddress")

        self.mcx_event(MNumber.SIGNAL_TARGET_MAIN_SOURCE, target.address, DBase.MNumberType(DBase.MNumber.INVALID_M))

    async def get_first_surround_signal(self, fu_index: int) -> int:
        """Return the first surround signal of the given fu_index.
        Conditions that must be checked:
        """

        # FU is Surround Master
        if self.is_signal_surround_master(fu_index):
            return (fu_index - Funktionseinheiten.FU_SURROUND_MASTER_BASE) * 8

        # When FU is not a surround bundle it is the closest smaller multiple of 8.
        fu_surr_format: DAudioSystem.SurroundFormat = await self.mcx_get(
            MNumber.EU_Modes_SurroundFormat, fu_index, DAudioSystem.SurroundFormat
        )
        if fu_surr_format.surround_format == DAudioSystem.SurroundFormats.SURROUND_FORMAT_NONE:
            # Check if the first signal is in a surround bundle otherwise the bundle of 8 is still used for a surround
            # bundle. For that case we need to return the first signal starting from the surround bundle.
            if fu_index != fu_index // 8 * 8:
                return await self.get_first_surround_signal(fu_index // 8 * 8)
            return fu_index // 8 * 8

        surround_bundle_idx = await self.mcx_get(MNumber.EU_Modes_SurroundBundleIndex, fu_index, DBase.MCX_STATE8)

        return fu_index - surround_bundle_idx.value

    async def is_signal_part_of_surround_bundle(self, fu_index: int) -> bool:
        """Check if given fu_index is part of an active surround bundle."""

        if self.is_signal_surround_master(fu_index):
            first_surr_signal = await self.get_first_surround_signal(fu_index)
            surr_format = await self.mcx_get(MNumber.EU_Modes_Surround, first_surr_signal, DAudioSystem.SurroundFormat)
            return surr_format.surround_format != DAudioSystem.SurroundFormats.SURROUND_FORMAT_NONE
        else:
            surr_format = await self.mcx_get(MNumber.EU_Modes_Surround, fu_index, DAudioSystem.SurroundFormat)
            return surr_format.surround_format != DAudioSystem.SurroundFormats.SURROUND_FORMAT_NONE

    def is_signal_surround_master(self, fu_index: int) -> bool:
        """Check if the given fu_index is part of the surround master

        Args:
            fu_index (int): The fu_index to check

        Returns:
            bool: true if the fu_index is part of the surround master
        """

        return Funktionseinheiten.FU_SURROUND_MASTER_BASE <= fu_index <= Funktionseinheiten.FU_SURROUND_MASTER_END

    async def get_surround_master(self, fu_index: int):
        if self.is_signal_surround_master(fu_index):
            self._log.debug("You requested the surround master of a surround master")
            return fu_index

        first_surr_signal = await self.get_first_surround_signal(fu_index)
        return Funktionseinheiten.FU_SURROUND_MASTER_BASE + (first_surr_signal // 8)

    def get_stereo_leg(self, fu_index: int, left: bool = True):
        if fu_index % 2 == 0:
            return fu_index if left else fu_index + 1
        else:
            return fu_index if not left else fu_index - 1

    def get_left_stereo_leg(self, fu_index: int):
        return self.get_stereo_leg(fu_index, left=True)

    def get_right_stereo_leg(self, fu_index: int):
        return self.get_stereo_leg(fu_index, left=False)

    # ---------------------------------------------------------------------------- #
    #                                    SIGNAL                                    #
    # ---------------------------------------------------------------------------- #
    async def check_signal_online(self, fu_index: int) -> bool:
        fu_type = FunktionseinheitType.get_fu_type(fu_index)
        usa: DSignal.UniqueSignalAddress
        sig_number = 0

        if fu_type == FunktionseinheitTypes.INP:
            sig_number = fu_index - Funktionseinheiten.FU_INPUT_BASE
            usa = DSignal.UniqueSignalAddress(DSignal.SignalType.DspInput, sig_number, 0)
        elif fu_type == FunktionseinheitTypes.GRP:
            sig_number = fu_index - Funktionseinheiten.FU_GROUP_BASE
            usa = DSignal.UniqueSignalAddress(DSignal.SignalType.DspGroupDirectOut, sig_number, 0)
        elif fu_type == FunktionseinheitTypes.SUM:
            sig_number = fu_index - Funktionseinheiten.FU_SUMM_BASE
            usa = DSignal.UniqueSignalAddress(DSignal.SignalType.DspSumDirectOut, sig_number, 0)
        elif fu_type == FunktionseinheitTypes.AUX:
            sig_number = fu_index - Funktionseinheiten.FU_AUX_BASE
            usa = DSignal.UniqueSignalAddress(DSignal.SignalType.DspAuxDirectOut, sig_number, 0)
        else:
            raise ValueError(f"Unknown fu_type {fu_type}")

        result: DBase.MCX_INT32 = await self.mcx_get(MNumber.SIGNAL_ONLINE, usa.address, data_type=DBase.MCX_INT32)

        if result.value == 0:
            return False

        return True

    def get_fu_signal_type(self, fu_index: int) -> FunktionseinheitTypes:
        if Funktionseinheiten.FU_INPUT_BASE <= fu_index < Funktionseinheiten.FU_INPUT_END:
            return FunktionseinheitTypes.INP
        elif Funktionseinheiten.FU_GROUP_BASE <= fu_index < Funktionseinheiten.FU_GROUP_END:
            return FunktionseinheitTypes.GRP
        elif Funktionseinheiten.FU_SUMM_BASE <= fu_index < Funktionseinheiten.FU_SUMM_END:
            return FunktionseinheitTypes.SUM
        elif Funktionseinheiten.FU_AUX_BASE <= fu_index < Funktionseinheiten.FU_AUX_END:
            return FunktionseinheitTypes.AUX
        else:
            raise ValueError(f"Unknown fu_index {fu_index}")

    def add_external_signal(
        self,
        usa: DSignal.UniqueSignalAddress,
        leg_count: int,
        responsibleBlockM: MNumber | int,
        portableBlockN: int,
        extraId: int,
        devId: str,
        signalId: str,
        flags: int,
        name: str,
        sig_format: DSignal.FormatType,
    ) -> DSignal.UniqueSignalAddress:
        """Add an external signal to the MCX database"""

        self._log.debug("Adding external signal.")
        defId_string = DBase.StringType(devId, DBase.StringTypeSize.STRING64)
        signalId_string = DBase.StringType(signalId, DBase.StringTypeSize.STRING64)
        name_string = DBase.StringType(name, DBase.StringTypeSize.STRING64)

        add_signal = DSignal.AddSignalCommand(
            identification=DSignal.Identification(
                leg_count=DBase.MCX_STATE32(leg_count),
                m=DBase.MNumberType(responsibleBlockM),
                n=DBase.NNumberType(portableBlockN),
                extra_id=DBase.MCX_STATE32(extraId),
                flags=DBase.MCX_STATE32(flags),
                address=DSignal.Networkaddress(defId_string, signalId_string),
            ),
            name=name_string,
            signal_format=sig_format,
        )

        self.mcx_event(MNumber.SIGNAL_COMMAND_ADD_AUDIO_SIGNAL, usa.address, add_signal)
        new_usa = DSignal.UniqueSignalAddress()
        new_usa.from_network_address(usa.signal_type, add_signal.identification.address)

        return usa

    def remove_external_signal(self, signal_type: DSignal.SignalType, dev_id: str, signal_id: str):
        """Remove an external signal from the MCX database"""

        self._log.debug("Removing external signal.")

        dev_id_string = DBase.StringType(dev_id, DBase.StringTypeSize.STRING64)
        signal_id_string = DBase.StringType(signal_id, DBase.StringTypeSize.STRING64)

        usa = DSignal.UniqueSignalAddress()
        usa.from_network_address(signal_type, DSignal.Networkaddress(dev_id_string, signal_id_string))

        self.mcx_event(MNumber.SIGNAL_COMMAND_REMOVE_SIGNAL, usa.address, None)

    # ------------------------------- Set signal m ------------------------------- #

    class SignalMeteringPickup(IntEnum):
        """Signal Metering Pickup"""

        INPUT = 2  # ST_INMIX_OUT
        PRE_FADER = 37  # ST_FADER_IN
        AFTER_FADER = 46  # ST_SUMBUS
        DIRECT_OUT = 41  # ST_DIROUT_OUT

    def set_signal_metering_pickup(self, fu_index: int, pickup: SignalMeteringPickup):
        self._log.debug(
            "Setting Signal Metering Pickup %s for %s",
            pickup.name,
            LawoMCXDeviceHelper.create_fu_signal_string(fu_index),
        )
        self.mcx_event(MNumber.EU_Mess_SigPos, fu_index, DBase.MCX_STATE8(pickup))

    async def get_signal_metering_pickup(self, fu_index: int) -> SignalMeteringPickup:
        pickup = await self.mcx_get(MNumber.EU_Mess_SigPos, fu_index, DBase.MCX_STATE8)
        return self.SignalMeteringPickup(pickup.value)

    async def get_signal_metering_main_level(self, fu_index: int) -> int:
        level = await self.mcx_get(MNumber.CHANNEL_METERING_MAINLEVEL, fu_index, DBase.MCX_LEVEL)
        return level.value

    async def get_signal_metering_input_level(self, fu_index: int) -> int:
        level = await self.mcx_get(MNumber.CHANNEL_METERING_INPUTLEVEL, fu_index, data_type=DBase.MCX_LEVEL)
        return level.value

    async def get_signal_metering_insert_level(self, fu_index: int) -> int:
        level = await self.mcx_get(MNumber.CHANNEL_METERING_INSERTLEVEL, fu_index, data_type=DBase.MCX_LEVEL)
        return level.value

    async def get_signal_metering_directout_level(self, fu_index: int) -> int:
        level = await self.mcx_get(MNumber.CHANNEL_METERING_DIROUTLEVEL, fu_index, data_type=DBase.MCX_LEVEL)
        return level.value

    # --------------------------------- EQUALIZER -------------------------------- #
    def set_eq_on(self, fu_index: int, on: bool):
        self._log.debug("Setting EQ On %s for %s", on, LawoMCXDeviceHelper.create_fu_signal_string(fu_index))
        self.mcx_event(MNumber.EU_EQU_Bypass, fu_index, DBase.MCX_SHORTKEYS(on))

    async def get_eq_on(self, fu_index: int) -> bool:
        on = await self.mcx_get(MNumber.EU_EQU_Bypass, fu_index, DBase.MCX_SHORTKEYS)
        return on.value == 1

    def set_eq_band_on(self, fu_index: int, band: int, on: bool):
        self._log.debug(
            "Setting EQ Band %d On %s for %s", band, on, LawoMCXDeviceHelper.create_fu_signal_string(fu_index)
        )
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_BandBypass
        elif band == 2:
            m_number = MNumber.EU_EQF2_BandBypass
        elif band == 3:
            m_number = MNumber.EU_EQF3_BandBypass
        elif band == 4:
            m_number = MNumber.EU_EQF4_BandBypass
        else:
            raise ValueError("Band must be between 1 and 4")

        self.mcx_event(m_number, fu_index, DBase.MCX_SHORTKEYS(on))

    async def get_eq_band_on(self, fu_index: int, band: int) -> bool:
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_BandBypass
        elif band == 2:
            m_number = MNumber.EU_EQF2_BandBypass
        elif band == 3:
            m_number = MNumber.EU_EQF3_BandBypass
        elif band == 4:
            m_number = MNumber.EU_EQF4_BandBypass
        else:
            raise ValueError("Band must be between 1 and 4")

        on = await self.mcx_get(m_number, fu_index, DBase.MCX_SHORTKEYS)
        return on.value == 1

    def set_eq_band_type(self, fu_index: int, band: int, band_type: DSignal.EQBandType):
        self._log.debug(
            "Setting EQ Band Type %s for %s", band_type.name, LawoMCXDeviceHelper.create_fu_signal_string(fu_index)
        )
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_BandType
        elif band == 2:
            m_number = MNumber.EU_EQF2_BandType
        elif band == 3:
            m_number = MNumber.EU_EQF3_BandType
        elif band == 4:
            m_number = MNumber.EU_EQF4_BandType
        else:
            raise ValueError("Band must be between 1 and 4")

        self.mcx_event(m_number, fu_index, DBase.MCX_SHORTKEYS(band_type.value))

    async def get_eq_band_type(self, fu_index: int, band: int) -> DSignal.EQBandType:
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_BandType
        elif band == 2:
            m_number = MNumber.EU_EQF2_BandType
        elif band == 3:
            m_number = MNumber.EU_EQF3_BandType
        elif band == 4:
            m_number = MNumber.EU_EQF4_BandType
        else:
            raise ValueError("Band must be between 1 and 4")

        band_type = await self.mcx_get(m_number, fu_index, DBase.MCX_SHORTKEYS)
        return DSignal.EQBandType(band_type.value)

    def set_eq_band_q(self, fu_index: int, band: int, q: DBase.MCX_QUAL):
        self._log.debug("Setting EQ Band Q %s for %s", q, LawoMCXDeviceHelper.create_fu_signal_string(fu_index))
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_Quality
        elif band == 2:
            m_number = MNumber.EU_EQF2_Quality
        elif band == 3:
            m_number = MNumber.EU_EQF3_Quality
        elif band == 4:
            m_number = MNumber.EU_EQF4_Quality
        else:
            raise ValueError("Band must be between 1 and 4")
        self.mcx_event(m_number, fu_index, q)

    async def get_eq_band_q(self, fu_index: int, band: int) -> DBase.MCX_QUAL:
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_Quality
        elif band == 2:
            m_number = MNumber.EU_EQF2_Quality
        elif band == 3:
            m_number = MNumber.EU_EQF3_Quality
        elif band == 4:
            m_number = MNumber.EU_EQF4_Quality
        else:
            raise ValueError("Band must be between 1 and 4")

        q = await self.mcx_get(m_number, fu_index, DBase.MCX_QUAL)
        return q

    def set_eq_band_freq(self, fu_index: int, band: int, frequency: DBase.MCX_FREQ):
        self._log.debug(
            "Setting EQ Band Frequency %s for %s", frequency, LawoMCXDeviceHelper.create_fu_signal_string(fu_index)
        )
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_Freq
        elif band == 2:
            m_number = MNumber.EU_EQF2_Freq
        elif band == 3:
            m_number = MNumber.EU_EQF3_Freq
        elif band == 4:
            m_number = MNumber.EU_EQF4_Freq
        else:
            raise ValueError("Band must be between 1 and 4")

        self.mcx_event(m_number, fu_index, frequency)

    async def get_eq_band_freq(self, fu_index: int, band: int) -> DBase.MCX_FREQ:
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_Freq
        elif band == 2:
            m_number = MNumber.EU_EQF2_Freq
        elif band == 3:
            m_number = MNumber.EU_EQF3_Freq
        elif band == 4:
            m_number = MNumber.EU_EQF4_Freq
        else:
            raise ValueError("Band must be between 1 and 4")

        frequency = await self.mcx_get(m_number, fu_index, DBase.MCX_FREQ)
        return frequency

    def set_eq_band_gain(self, fu_index: int, band: int, gain: DBase.MCX_LEVEL):
        self._log.debug(
            "Setting EQ Band Gain %s for %s", gain.value, LawoMCXDeviceHelper.create_fu_signal_string(fu_index)
        )
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_Level1
        elif band == 2:
            m_number = MNumber.EU_EQF2_Level1
        elif band == 3:
            m_number = MNumber.EU_EQF3_Level1
        elif band == 4:
            m_number = MNumber.EU_EQF4_Level1
        else:
            raise ValueError("Band must be between 1 and 4")

        self.mcx_event(m_number, fu_index, gain)

    async def get_eq_band_gain(self, fu_index: int, band: int) -> DBase.MCX_LEVEL:
        m_number: MNumber
        if band == 1:
            m_number = MNumber.EU_EQF1_Level1
        elif band == 2:
            m_number = MNumber.EU_EQF2_Level1
        elif band == 3:
            m_number = MNumber.EU_EQF3_Level1
        elif band == 4:
            m_number = MNumber.EU_EQF4_Level1
        else:
            raise ValueError("Band must be between 1 and 4")

        gain = await self.mcx_get(m_number, fu_index, DBase.MCX_LEVEL)
        return gain

    def set_eq_band(
        self,
        fu_index: int,
        band: int,
        band_type: Optional[DSignal.EQBandType] = None,
        q: Optional[int] = None,
        frequency: Optional[int] = None,
        gain: Optional[int] = None,
    ):

        if band_type is not None:
            self.set_eq_band_type(fu_index, band, band_type)
        if q is not None:
            self.set_eq_band_q(fu_index, band, DBase.MCX_QUAL(LawoMCXDeviceHelper.to_lawo_Q(q)))
        if frequency is not None:
            self.set_eq_band_freq(fu_index, band, DBase.MCX_FREQ(LawoMCXDeviceHelper.to_lawo_Hz(frequency)))
        if gain is not None:
            self.set_eq_band_gain(fu_index, band, DBase.MCX_LEVEL(gain))

    # ---------------------------------------------------------------------------- #
    #                                      AUX                                     #
    # ---------------------------------------------------------------------------- #
    def set_aux_gain(self, fu_index: int, dest_fu_index: int, gain_lawo_db: int):
        self._log.debug(
            "Setting Aux Gain %d dB for %s", gain_lawo_db, LawoMCXDeviceHelper.create_fu_signal_string(fu_index)
        )
        aux_index: int = (fu_index - FunktionseinheitType.get_fu_base(fu_index)) // 2
        next_aux_delta: int = MNumber.EU_Aux2_OnOffL - MNumber.EU_Aux1_OnOffL

        if fu_index % 2 == 0:
            aux_m_number = MNumber.EU_Aux1_LevelL
        else:
            aux_m_number = MNumber.EU_Aux1_LevelR
        self.mcx_event(aux_m_number + (aux_index * next_aux_delta), dest_fu_index, DBase.MCX_LEVEL(gain_lawo_db))

    async def get_aux_gain(self, fu_index: int, dest_fu_index: int) -> DBase.MCX_LEVEL:
        aux_index: int = (fu_index - FunktionseinheitType.get_fu_base(fu_index)) // 2
        next_aux_delta: int = MNumber.EU_Aux2_OnOffL - MNumber.EU_Aux1_OnOffL

        if fu_index % 2 == 0:
            aux_m_number = MNumber.EU_Aux1_LevelL
        else:
            aux_m_number = MNumber.EU_Aux1_LevelR

        return await self.mcx_get(aux_m_number + (aux_index * next_aux_delta), dest_fu_index, DBase.MCX_LEVEL)

    # ---------------------------------------------------------------------------- #
    #                                CHANNEL ASSIGN                                #
    # ---------------------------------------------------------------------------- #
    def mcx_enter_assign(self):
        self.mcx_event(MNumber.CONSOLE_ACCESS_ASSIGN_ENTER, 0, DBase.MCX_STATE8(1))

    def mcx_cancel_assign(self):
        self.mcx_event(MNumber.CONSOLE_ACCESS_ASSIGN_CANCEL, 0, DBase.MCX_STATE8(1))

    def mcx_set_access_channel(self, access_channel: int):
        self.mcx_event(MNumber.CONSOLE_ACCESS_CHANNEL, 0, DBase.NNumberType(access_channel))

    def mcx_set_access_bank(self, bank: int):
        self.mcx_toggle_bank(bank)

    def mcx_toggle_bank(self, bank: int):
        # Check if BANK Number is between 1 and 6

        if bank < 0 or bank > 5:
            raise ValueError("Bank number must be between 0 and 5")
        bank_m_numbers = [
            MNumber.CONSOLE_ACCESS_BANK0_STATE,
            MNumber.CONSOLE_ACCESS_BANK1_STATE,
            MNumber.CONSOLE_ACCESS_BANK2_STATE,
            MNumber.CONSOLE_ACCESS_BANK3_STATE,
            MNumber.CONSOLE_ACCESS_BANK4_STATE,
            MNumber.CONSOLE_ACCESS_BANK5_STATE,
        ]
        self.toggle_button_no_wait(bank_m_numbers[bank], 0)

    def mcx_toggle_banks(self, *banks: int):
        for bank in banks:
            self.mcx_toggle_bank(bank)

    async def mcx_get_access_bank(self):
        bank = await self.mcx_get(MNumber.CONSOLE_ACCESS_CURRENT_BANK, 0, DBase.MCX_STATE8)
        return bank.value

    # ----------------------------- STRIP ASSIGNMENT ----------------------------- #
    def mcx_strip_assign_activate_strip_assign(self) -> None:
        self._log.debug("Activating Strip Assign")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_MODE_ASSIGN, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_activate_insert_move(self) -> None:
        self._log.debug("Activating Insert Move")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_MODE_INS_MOVE, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_activate_first_last(self) -> None:
        self._log.debug("Activating First/Last")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_MODE_FIRST_LAST, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_both_layer(self) -> None:
        self._log.debug("Activating Both Layer")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_MULTIMODE_BOTH_LAYERS, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_all_bank(self) -> None:
        self._log.debug("Activating All Bank")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_MULTIMODE_ALL_BANK, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_clear(self) -> None:
        self._log.debug("Activating Clear")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_MULTIMODE_CLEAR, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_clear_bay_iso(self) -> None:
        raise NotImplementedError

    def mcx_strip_assign_clear_bank(self) -> None:
        self._log.debug("Activating Clear Bank")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_CLEAR_BANK, 0, DBase.MCX_STATE8(1))

    def mcx_strip_assign_copy_bank(self) -> None:
        self._log.debug("Activating Copy Bank")
        self.mcx_event(MNumber.CONSOLE_ACCESS_STRIP_COPY_BANK, 0, DBase.MCX_STATE8(1))

    # ------------------------------ BUS ASSIGNMENT ------------------------------ #
    def mcx_bus_assign(self, fu_channel: int, fu_bus: int, assign: bool = True):
        fu_type = FunktionseinheitType.get_fu_type(fu_bus)
        fu_base = FunktionseinheitType.get_fu_base(fu_bus)

        bus_num = fu_bus - fu_base

        if fu_type == FunktionseinheitTypes.INP:
            self.mcx_sum_assign(fu_channel, bus_num, assign)
        elif fu_type == FunktionseinheitTypes.GRP:
            self.mcx_group_assign(fu_channel, bus_num, assign)
        elif fu_type == FunktionseinheitTypes.SUM:
            self.mcx_sum_assign(fu_channel, bus_num, assign)
        elif fu_type == FunktionseinheitTypes.AUX:
            self.mcx_aux_assign(fu_channel, bus_num, assign)
        else:
            raise ValueError(f"Unknown Funktionseinheit type for index {fu_channel}")

    async def assert_mcx_bus_assign(self, fu_channel: int, fu_bus: int):
        fu_type = FunktionseinheitType.get_fu_type(fu_bus)
        fu_base = FunktionseinheitType.get_fu_base(fu_bus)

        bus_num = fu_bus - fu_base

        if fu_type == FunktionseinheitTypes.INP:
            await self.assert_mcx_sum_assign(fu_channel, bus_num)
        elif fu_type == FunktionseinheitTypes.GRP:
            await self.assert_mcx_group_assign(fu_channel, bus_num)
        elif fu_type == FunktionseinheitTypes.SUM:
            await self.assert_mcx_sum_assign(fu_channel, bus_num)
        elif fu_type == FunktionseinheitTypes.AUX:
            await self.assert_mcx_aux_assign(fu_channel, bus_num)
        else:
            raise ValueError(f"Unknown Funktionseinheit type for index {fu_channel}")

    def mcx_sum_assign(self, fu_channel: int, sum_bus: int, assign: bool = True):
        self._log.debug("Assigning Sum %s to %s", sum_bus, LawoMCXDeviceHelper.create_fu_signal_string(fu_channel))
        sum_num = MNumber.EU_Summe_Begin.value + sum_bus
        self.mcx_event(sum_num, fu_channel, DBase.BoolType(assign))

    async def assert_mcx_sum_assign(self, fu_channel: int, sum_bus: int):
        sum_num = MNumber.EU_Summe_Begin.value + sum_bus
        await self.assert_MND(
            sum_num,
            fu_channel,
            DBase.BoolType(True),
            f"Sum {sum_bus} is not assigned to {LawoMCXDeviceHelper.create_fu_signal_string(fu_channel)}",
        )

    def mcx_group_assign(self, fu_channel: int, group: int, assign: bool = True):
        self._log.debug("Assigning Group %s to %s", group, LawoMCXDeviceHelper.create_fu_signal_string(fu_channel))
        group_num = MNumber.EU_Group_Begin.value + group
        self.mcx_event(group_num, fu_channel, DBase.BoolType(assign))

    async def assert_mcx_group_assign(self, fu_channel: int, group: int):
        group_num = MNumber.EU_Group_Begin.value + group
        await self.assert_MND(group_num, fu_channel, DBase.BoolType(True))

    def mcx_aux_assign(self, fu_channel: int, aux: int, assign: bool = True):
        self._log.debug("Assigning Aux %s to %s", aux, LawoMCXDeviceHelper.create_fu_signal_string(fu_channel))
        if aux & 1 != 0:
            aux_num = MNumber.EU_Aux1_OnOffR.value + 16 * (aux // 2)
        else:
            aux_num = MNumber.EU_Aux1_OnOffL.value + 16 * (aux // 2)
        self.mcx_event(aux_num, fu_channel, DBase.BoolType(assign))

    async def assert_mcx_aux_assign(self, fu_channel: int, aux: int):
        if aux & 1 != 0:
            aux_num = MNumber.EU_Aux1_OnOffR.value + 16 * (aux // 2)
        else:
            aux_num = MNumber.EU_Aux1_OnOffL.value + 16 * (aux // 2)
        await self.assert_MND(aux_num, fu_channel, DBase.BoolType(True))

    # ---------------------------------------------------------------------------- #
    #                                DSP RESSOURCES                                #
    # ---------------------------------------------------------------------------- #

    async def mcx_get_active_dsp(self):
        # Unfortunately currently we cannot get the M-Number automatically, so we add it manually
        DEVICE_UHDCORE_REDUNDANCY_GET_ACTIVE_LDA = 1621426179  # pylint: disable=invalid-name
        dsp_id = await self.mcx_get(DEVICE_UHDCORE_REDUNDANCY_GET_ACTIVE_LDA, 0, DBase.MCX_STATE32)
        return dsp_id.value

    async def mcx_get_dsp_channel_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_CHANNEL_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    async def mcx_get_dsp_bus_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_BUS_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    async def mcx_get_dsp_listen_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_LISTEN_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    async def mcx_get_dsp_automix_group_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_AUTOMIX_GROUP_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    async def mcx_get_dsp_ext_key_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_EXT_KEY_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    async def mcx_get_dsp_talkback_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_TALKBACK_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    async def mcx_get_dsp_siggen_count(self) -> int:
        uhdcore_id = await self.mcx_get_active_dsp()
        count = await self.mcx_get(MNumber.DEVICE_UHDCORE_STATE_DSP_SIGGEN_COUNT, uhdcore_id, DBase.MCX_STATE16)
        return count.value

    # ---------------------------------------------------------------------------- #
    #                                  UHD CONFIG                                  #
    # ---------------------------------------------------------------------------- #

    async def mcx_apply_uhd_dsp_config(
        self,
        inputs: int,
        groups: int,
        sums: int,
        auxes: int,
        automixgroups: Optional[int] = None,
        extkeys: Optional[int] = None,
        talkbacks: Optional[int] = None,
        pfl1: Optional[int] = None,
        afl1: Optional[int] = None,
        pfl2: Optional[int] = None,
        afl2: Optional[int] = None,
        crm1: Optional[int] = None,
        crm2: Optional[int] = None,
        crm_hp1: Optional[int] = None,
        crm_hp2: Optional[int] = None,
        do_check: bool = False,
        enable_listen: bool = True,
        afl1_surround_format: DAudioSystem.SurroundFormats = DAudioSystem.SurroundFormats.SURROUND_FORMAT_NONE,
    ):
        self._log.debug(
            "Applying UHD DSP Config - Inputs: %s, Groups: %s, Sums: %s, Auxes: %s", inputs, groups, sums, auxes
        )
        # Currently an input, group, sum or aux count must be a multiple of 8
        if inputs % 8 != 0 or groups % 8 != 0 or sums % 8 != 0 or auxes % 8 != 0:
            raise ValueError("Inputs, Groups, Sums and Auxes must be a multiple of 8")

        # First request the current configuration, to get the user config flags
        dsp_config = await self.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, DAudioSystem.MixerUserConfig)

        # Update the configuration
        dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Input, inputs)
        dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Group, groups)
        dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Sum, sums)
        dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Aux, auxes)

        if automixgroups:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.AutomixGroup, automixgroups)

        if extkeys:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.ExtKey, extkeys)

        if talkbacks:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Talkback, talkbacks)

        # Set Listens

        if pfl1:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Pfl1, pfl1)

        if afl1:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Afl1, afl1)

        if pfl2:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Pfl2, pfl2)

        if afl2:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Afl2, afl2)

        if crm1:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Crm1, crm1)

        if crm2:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.Crm2, crm2)

        if crm_hp1:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.CrmHp1, crm_hp1)

        if crm_hp2:
            dsp_config.set_resource_count(DAudioSystem.MixerResourceType.CrmHp2, crm_hp2)

        dsp_config.listen_enabled = enable_listen
        dsp_config.afl1_surround_format = afl1_surround_format

        # Send the updated configuration
        self.mcx_event(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, dsp_config)

        if do_check:
            await asyncio.sleep(2)
            # Check the configuration
            ck_dsp_config = await self.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, DAudioSystem.MixerUserConfig)
            assert ck_dsp_config == dsp_config, "Configuration failed"

    async def mcx_apply_crm_config(self, crm1: bool, crm2: bool, crmhp1: bool, crmhp2: bool):
        self._log.debug(
            "Applying CRM Config - CRM1: %s, CRM2: %s, CRM_HP1: %s, CRM_HP2: %s", crm1, crm2, crmhp1, crmhp2
        )
        # get current configuration
        mu_config = await self.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, DAudioSystem.MixerUserConfig)
        mu_config.crm1_enabled = crm1
        mu_config.crm2_enabled = crm2
        mu_config.crm_hp1_enabled = crmhp1
        mu_config.crm_hp2_enabled = crmhp2
        # send the updated configuration
        self.mcx_event(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, mu_config)

    # ---------------------------------------------------------------------------- #
    #                                   SNAPSHOTS                                  #
    # ---------------------------------------------------------------------------- #
    async def is_fileworker_busy(self):
        # If the System is busy, it will not response at all. So let's retry until we get a response:
        try:
            in_progress = await self.mcx_get(MNumber.SYSTEM_FILEWORKER_OPERATION_IN_PROGRESS, 0, DBase.MCX_STATE32)
            if in_progress.value == 0:
                await self.wait_for(MNumber.SYSTEM_BLINK, True)
                return False
            return True
        except (ConnectionTimout, asyncio.TimeoutError):
            return True

    async def wait_for_fileworker(self, timeout=10):
        async with asyncio.timeout(timeout):
            while await self.is_fileworker_busy():
                await asyncio.sleep(1)

    async def get_current_snapshot(self):
        data = await self._systemlink_connection.mcx_get_raw(MNumber.SYSTEM_SNAPSHOT, 0)
        folder = DBase.StringType()
        name = DBase.StringType()
        # Split datastream into folder and name each 32 bytes long
        if len(data) != 64:
            raise ValueError("Invalid snapshot data")
        d_folder, d_name = data[:32], data[32:]
        folder.parse(d_folder)
        name.parse(d_name)
        return folder.string, name.string

    async def save_snapshot(self, name: str, snapshot_folder: str):
        self._log.debug("Saving snapshot %s", name)
        data = DBase.StringType(snapshot_folder, DBase.StringTypeSize.STRING32)
        data += DBase.StringType(name, DBase.StringTypeSize.STRING32)
        self.mcx_event(MNumber.SYSTEM_SAVE_SNAPSHOT, 0, data)
        # We don't know when the save process is finished, so we wait for 2 seconds
        await asyncio.sleep(2)
        self._log.debug("Snapshot %s saved", name)

    async def load_snapshot(self, name: str, snapshot_folder: str):
        self._log.debug("Loading snapshot %s", name)
        data = DBase.StringType(snapshot_folder, DBase.StringTypeSize.STRING32)
        data += DBase.StringType(name, DBase.StringTypeSize.STRING32)
        self.mcx_event(MNumber.SYSTEM_LOAD_SNAPSHOT, 0, data)
        # We don't know when the load process is finished, so we wait for 1 second
        # and check if the current snapshot is the one we want to load
        await asyncio.sleep(1)
        async with asyncio.timeout(10):
            while True:
                tmp_folder, tmp_name = await self.get_current_snapshot()
                if tmp_folder == snapshot_folder and tmp_name == name:
                    break
                await asyncio.sleep(1)
        self._log.debug("Snapshot %s loaded", name)

    async def delete_snapshot(self, name: str, snapshot_folder: str):
        self._log.debug("Deleting snapshot %s", name)
        data = DBase.StringType(snapshot_folder, DBase.StringTypeSize.STRING32)
        data += DBase.StringType(name, DBase.StringTypeSize.STRING32)
        self.mcx_event(MNumber.SYSTEM_DELETE_SNAPSHOT, 0, data)
        # We don't know when the delete process is finished, so we wait for 2 seconds
        await asyncio.sleep(2)
        self._log.debug("Snapshot %s deleted", name)

    # ---------------------------------------------------------------------------- #
    #                                    PRESETS                                   #
    # ---------------------------------------------------------------------------- #
    def save_preset(self, mn: MNNumber, snapshot_path_filename: str, snapshot_path_directory: str = ""):
        self._log.debug("Saving preset to %s/%s", snapshot_path_directory, snapshot_path_filename)

        directory = DBase.StringType(snapshot_path_directory, DBase.StringTypeSize.STRING32)
        filename = DBase.StringType(snapshot_path_filename, DBase.StringTypeSize.STRING32)

        snapshotPath = DSystem.SnapshotPathType(directory, filename)

        presetHead = DSystem.PresetHead(mn.m, mn.n, snapshotPath)
        self.mcx_event(MNumber.SYSTEM_SAVE_PRESET, 0, presetHead)

    def load_preset(self, mn: MNNumber, snapshot_path_filename: str, snapshot_path_directory: str = ""):
        self._log.debug("Loading preset from %s/%s", snapshot_path_directory, snapshot_path_filename)

        directory = DBase.StringType(snapshot_path_directory, DBase.StringTypeSize.STRING32)
        filename = DBase.StringType(snapshot_path_filename, DBase.StringTypeSize.STRING32)

        snapshotPath = DSystem.SnapshotPathType(directory, filename)

        presetHead = DSystem.PresetHead(mn.m, mn.n, snapshotPath)
        self.mcx_event(MNumber.SYSTEM_LOAD_PRESET, 0, presetHead)

    # ---------------------------------------------------------------------------- #
    #                                  PRODUCTIONS                                 #
    # ---------------------------------------------------------------------------- #
    async def get_current_production(self):
        name = await self.mcx_get(MNumber.SYSTEM_CURRENT_PRODUCTION, 0, DBase.StringType)
        return name.string

    async def save_production(self, name: str):
        self._log.debug("Saving production %s", name)
        data = DBase.StringType(name, DBase.StringTypeSize.STRING32)
        # Chek that fileworker is not busy:
        await self.wait_for_fileworker()

        self.mcx_event(MNumber.SYSTEM_SAVE_PRODUCTION, 0, data)
        await self.wait_for(MNumber.SYSTEM_FILEWORKER_OPERATION_IN_PROGRESS, open_stream=True, response_timeout=10)
        await self.wait_for_fileworker()

    async def load_production(self, name: str):
        self._log.debug("Loading production %s", name)
        data = DBase.StringType(name, DBase.StringTypeSize.STRING32)
        # Chek that fileworker is not busy:
        await self.wait_for_fileworker()

        self.mcx_event(MNumber.SYSTEM_LOAD_PRODUCTION, 0, data)
        await self.wait_for(
            MNumber.SYSTEM_FILEWORKER_OPERATION_IN_PROGRESS,
            open_stream=True,
            response_timeout=30,
            response_iterations=1,
        )
        await self.wait_for_fileworker()

        async with asyncio.timeout(10):
            while True:
                try:
                    tmp_name = await self.get_current_production()
                except asyncio.TimeoutError:
                    tmp_name = ""
                if tmp_name == name:
                    break
                await asyncio.sleep(1)

    async def delete_production(self, name: str):
        self._log.debug("Deleting production %s", name)
        data = DBase.StringType(name, DBase.StringTypeSize.STRING32)
        # Chek that fileworker is not busy:
        await self.wait_for_fileworker()

        self.mcx_event(MNumber.SYSTEM_DELETE_PRODUCTION, 0, data)
        await self.wait_for_fileworker()

    # ---------------------------------------------------------------------------- #
    #                                 STRIP ASSIGN                                 #
    # ---------------------------------------------------------------------------- #

    def assign_strip(self, strip: int, fu_channel: int):
        self._log.debug("Assigning strip %d to fu_channel", strip)
        self.mcx_event(MNumber.CONSOLE_STRIP_FRONT_CHANNEL, strip, DBase.MCX_STATE32(fu_channel))

    async def assign_strip_via_access(self, strip: int, fu_channel: int):
        self._log.debug("Assigning strip %d to fu_channel via access", strip)
        self.mcx_set_access_channel(fu_channel)
        await self.toggle_button(MNumber.CONSOLE_STRIP_SEL_STATE, strip)

    def unassign_strip(self, strip: int):
        self._log.debug("Unassigning strip %d", strip)
        self.mcx_event(MNumber.CONSOLE_STRIP_FRONT_CHANNEL, strip, DBase.MNumberType(MNumber.INVALID_M))

    def assign_strip_back(self, strip: int, fu_channel: int):
        self._log.debug("Assigning strip %d to back fu_channel %d", strip, fu_channel)
        self.mcx_event(MNumber.CONSOLE_STRIP_BACK_CHANNEL, strip, DBase.MCX_STATE32(fu_channel))

    def unassign_strip_back(self, strip: int):
        self._log.debug("Unassigning strip %d back", strip)
        self.mcx_event(MNumber.CONSOLE_STRIP_BACK_CHANNEL, strip, DBase.MNumberType(MNumber.INVALID_M))

    def multi_assign_strip(self, start_strip: int, start_fu_channel: int, count: int):
        self._log.debug(
            "Assigning %d strips starting from %d to fu_channel starting from %d", count, start_strip, start_fu_channel
        )
        for i in range(count):
            self.assign_strip(start_strip + i, start_fu_channel + i)

    def multi_unassign_strip(self, start_strip: int, count: int):
        self._log.debug("Unassigning %d strips starting from %d", count, start_strip)
        for i in range(count):
            self.unassign_strip(start_strip + i)

    def multi_assign_strip_back(self, start_strip: int, start_fu_channel: int, count: int):
        self._log.debug(
            "Assigning %d strips starting from %d to back fu_channel starting from %d",
            count,
            start_strip,
            start_fu_channel,
        )
        for i in range(count):
            self.assign_strip_back(start_strip + i, start_fu_channel + i)

    def multi_unassign_strip_back(self, start_strip: int, count: int):
        self._log.debug("Unassigning %d strips starting from %d back", count, start_strip)
        for i in range(count):
            self.unassign_strip_back(start_strip + i)

    # ---------------------------------------------------------------------------- #
    #                                   GUI PAGE                                   #
    # ---------------------------------------------------------------------------- #

    async def set_gui_page(self, page: int):
        raise NotImplementedError

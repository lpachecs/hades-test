import asyncio
import logging

import pytest
import systemlink.datamodel.audiosystem as DAudioSystem
from systemlink.common.m_lookup import MNumberLookup as MNumber
from systemlink.common.mcx_com import MNNumber
from systemlink.datamodel.audiosystem import MixerUserConfig
from systemlink.datamodel.base import (MCX_STATE32, BoolType, MNumberType,
                                       StringType)
from systemlink.datamodel.channel import Funktionseinheiten as FU
from systemlink.datamodel.channel import FunktionseinheitType
from systemlink.datamodel.console import LampState
from systemlink.datamodel.signal import SignalType
from systemlink.datamodel.signal import UniqueSignalAddress as USA

from ldf.models.mcx import LawoMCXDevice, LawoMCXDeviceHelper
from tests import log

TEST_PREFIX = "autogen_test_"  # Prefix for all test strings used in the tests (production, snapshot, etc.)


@pytest.mark.dependency
class TestVirtualMixerGroup:
    async def test_get_redunndancy_group(self, test_mixer):
        """Test will validate the response to a get.devices.<id>.group"""

        async with test_mixer.client:
            group_info = await test_mixer.get_redundancy_group()

        if len([x for x in group_info.MemberIDs]) == 0:
            pytest.xfail("Get redundancy group request was successful but mixer is not grouped")

        log.info(f"Group ID: {group_info.ID}\t Group GUID: {group_info.GUID}")
        log.info(f"Group leader: {group_info.LeaderID}")
        assert type(group_info.LeaderID) is str
        for member in group_info.MemberIDs:
            log.info(f"Group Members: {member}")
            assert type(member) is str
        for parent in group_info.MemberIDs:
            log.info(f"Parents: {parent}")
            assert type(parent) is str

    def test_create_mcx_group(self, test_mixer):
        pass

    def test_failover_mcx_group(self):
        pass

    def test_split_mcx_group(self):
        pass


class TestLawoMCXDeviceHelper:
    def test_to_lawo_Hz(self):
        assert LawoMCXDeviceHelper.to_lawo_Hz(1000) == 4914

    def test_from_lawo_Hz(self):
        assert LawoMCXDeviceHelper.from_lawo_Hz(4914) == 1000

    def test_to_lawo_Q(self):
        assert LawoMCXDeviceHelper.to_lawo_Q(1) == 64

    def test_from_lawo_Q(self):
        assert LawoMCXDeviceHelper.from_lawo_Q(64) == 1

    def test_to_lawo_s(self):
        assert LawoMCXDeviceHelper.to_lawo_s(1) == 48000

    def test_from_lawo_s(self):
        assert LawoMCXDeviceHelper.from_lawo_s(48000) == 1

    def test_to_lawo_ms(self):
        assert LawoMCXDeviceHelper.to_lawo_ms(1) == 48

    def test_from_lawo_ms(self):
        assert LawoMCXDeviceHelper.from_lawo_ms(48) == 1

    def test_to_lawo_dB(self):
        assert LawoMCXDeviceHelper.to_lawo_dB(1) == 32

    def test_from_lawo_dB(self):
        assert LawoMCXDeviceHelper.from_lawo_dB(32) == 1


@pytest.mark.dependency
class TestLawoMCXDevice:
    async def test_get_version(self, test_mixer_connected: LawoMCXDevice):
        version = await test_mixer_connected.get_version()
        assert version is not None, "Version is None"
        assert test_mixer_connected.sw_version.split()[0] == version.__str__().replace(
            ".", "-"
        ), f"Version mismatch: {test_mixer_connected.sw_version} != {version}"
        log.info("MCX Version: %s", version)

    async def test_toggle_button(self, test_mixer_connected: LawoMCXDevice):
        # Pre Check
        test_mixer_connected.assign_strip(0, 0)
        c_cut = await test_mixer_connected.mcx_get(MNumber.EU_Cut_Cut, 0, BoolType)
        test_mixer_connected.mcx_event(MNumber.EU_Cut_Cut, 0, BoolType(False))

        # Test
        await test_mixer_connected.toggle_button(MNumber.CONSOLE_STRIP_CUT, 0)
        await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)
        c_cut = await test_mixer_connected.mcx_get(MNumber.EU_Cut_Cut, 0, BoolType)
        assert c_cut.value == 1

        # Cleanup
        await test_mixer_connected.toggle_button(MNumber.CONSOLE_STRIP_CUT, 0)
        await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)
        c_cut = await test_mixer_connected.mcx_get(MNumber.EU_Cut_Cut, 0, BoolType)
        assert c_cut.value is False
        test_mixer_connected.unassign_strip(0)

    async def test_get_lamp_state(self, test_mixer_connected: LawoMCXDevice):
        test_mixer_connected.assign_strip(0, 0)
        data: LampState = await test_mixer_connected.get_lamp_state(MNumber.CONSOLE_STRIP_CUT, 0)
        assert data is not None

        # Cleanup
        test_mixer_connected.unassign_strip(0)

    async def test_toggle_button_to(self, test_mixer_connected: LawoMCXDevice):
        await test_mixer_connected.toggle_button_to(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0, LampState.LAMP_YELLOW)

        lamp_state = await test_mixer_connected.get_lamp_state(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0)
        assert lamp_state == LampState.LAMP_YELLOW

        # Cleanup
        await test_mixer_connected.toggle_button_to(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0, LampState.LAMP_BLACK)

    async def test_toogle_button_from(self, test_mixer_connected: LawoMCXDevice):
        test_mixer_connected.assign_strip(0, 0)
        await test_mixer_connected.toggle_button_to(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0, LampState.LAMP_YELLOW)

        lamp_state = await test_mixer_connected.get_lamp_state(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0)
        assert lamp_state == LampState.LAMP_YELLOW

        await test_mixer_connected.toggle_button_from(
            MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0, LampState.LAMP_YELLOW
        )

        lamp_state = await test_mixer_connected.get_lamp_state(MNumber.CONSOLE_ACCESS_PAN_STICK0_REVEAL, 0)
        assert lamp_state == LampState.LAMP_BLACK

        # Cleanup
        test_mixer_connected.unassign_strip(0)

    async def test_set_and_check(self, test_mixer_connected: LawoMCXDevice):
        data = BoolType(True)
        await test_mixer_connected.set_and_check(MNumber.CHANNEL_CHANNEL_CUT, 0, data)
        await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)
        check: BoolType = await test_mixer_connected.mcx_get(MNumber.CHANNEL_CHANNEL_CUT, 0, data_type=BoolType)
        assert check.value is True
        await test_mixer_connected.set_and_check(MNumber.CHANNEL_CHANNEL_CUT, 0, BoolType(False))

    async def test_assert_mnd(self, test_mixer_connected: LawoMCXDevice):
        data = BoolType(True)
        await test_mixer_connected.set_and_check(MNumber.CHANNEL_CHANNEL_CUT, 0, data)
        check: BoolType = await test_mixer_connected.mcx_get(MNumber.CHANNEL_CHANNEL_CUT, 0, data_type=BoolType)
        assert check.value is True
        # TEST
        await test_mixer_connected.assert_MND(MNumber.CHANNEL_CHANNEL_CUT, 0, data)
        ##
        await test_mixer_connected.set_and_check(MNumber.CHANNEL_CHANNEL_CUT, 0, BoolType(False))

    def test_mcx_shutdown(self):
        # TODO - Implement test... How??
        pytest.skip("Test not implemented")

    def test_mcx_shudown_cold(self):
        # TODO - Implement test... How??
        pytest.skip("Test not implemented")

    async def test_mcx_connect(self, test_mixer_connected: LawoMCXDevice):
        """
        Test the connection of MCX device.
        """
        test_mixer_connected.mcx_connect(USA(SignalType.SigGen, 0, 0), USA(SignalType.DspInput, 0, 0))

        check_source: USA = await test_mixer_connected.mcx_get(
            MNumber.SIGNAL_TARGET_MAIN_SOURCE, USA(SignalType.DspInput, 0, 0).address, data_type=USA
        )

        assert check_source == USA(SignalType.SigGen, 0, 0)

        # Cleanup
        test_mixer_connected.mcx_event(
            MNumber.SIGNAL_TARGET_MAIN_SOURCE, USA(SignalType.DspInput, 0, 0).address, MNumberType(MNumber.INVALID_M)
        )

    async def test_mcx_disconnect(self, test_mixer_connected: LawoMCXDevice):
        test_mixer_connected.mcx_connect(USA(SignalType.SigGen, 0, 0), USA(SignalType.DspInput, 0, 0))
        check_source: USA = await test_mixer_connected.mcx_get(
            MNumber.SIGNAL_TARGET_MAIN_SOURCE, USA(SignalType.DspInput, 0, 0).address, data_type=USA
        )
        check_source.address != MNumber.INVALID_M.value
        test_mixer_connected.mcx_disconnect(USA(SignalType.DspInput, 0, 0))

        # Check
        check_source = await test_mixer_connected.mcx_get(
            MNumber.SIGNAL_TARGET_MAIN_SOURCE, USA(SignalType.DspInput, 0, 0).address, data_type=USA
        )
        assert check_source.address == MNumber.INVALID_M.value

    async def test_set_aux_gain(self, test_mixer_connected: LawoMCXDevice):
        lawo_db = LawoMCXDeviceHelper.to_lawo_dB(-40)
        test_mixer_connected.set_aux_gain(FU.FU_AUX_BASE + 1, 0, lawo_db)
        check_db = await test_mixer_connected.get_aux_gain(FU.FU_AUX_BASE + 1, 0)
        assert lawo_db == check_db.value
        test_mixer_connected.set_aux_gain(FU.FU_AUX_BASE + 1, 0, LawoMCXDeviceHelper.to_lawo_dB(-128))

    async def test_get_first_surround_signal(self, test_mixer_connected: LawoMCXDevice):
        test_mixer_connected.mcx_event(
            MNumber.EU_Modes_SurroundFormat,
            0,
            DAudioSystem.SurroundFormat(DAudioSystem.SurroundFormats.SURROUND_FORMAT_NONE),
        )
        for i in range(0, 8):
            assert await test_mixer_connected.get_first_surround_signal(i) == 0
        for i in range(8, 16):
            assert await test_mixer_connected.get_first_surround_signal(i) == 8

        START_SURROUND = FU.FU_SURROUND_MASTER_BASE
        for i in range(0, 8):
            test_i = i + START_SURROUND
            assert await test_mixer_connected.get_first_surround_signal(test_i) == i * 8

        # Check with an active surround system
        # Surround Format < 8 Channel
        test_mixer_connected.mcx_event(
            MNumber.EU_Modes_SurroundFormat,
            0,
            DAudioSystem.SurroundFormat(DAudioSystem.SurroundFormats.SURROUND_3D_4_0_4),
        )
        for i in range(0, 8):
            assert await test_mixer_connected.get_first_surround_signal(i) == 0
        for i in range(8, 16):
            assert await test_mixer_connected.get_first_surround_signal(i) == 8

        # Surround Format >= 8 Channel
        test_mixer_connected.mcx_event(
            MNumber.EU_Modes_SurroundFormat,
            0,
            DAudioSystem.SurroundFormat(DAudioSystem.SurroundFormats.SURROUND_3D_7_1_4),
        )
        for i in range(0, DAudioSystem.SurroundFormatCount.SURROUND_3D_7_1_4):
            assert await test_mixer_connected.get_first_surround_signal(i) == 0

        # Cleanup
        test_mixer_connected.mcx_event(
            MNumber.EU_Modes_SurroundFormat,
            0,
            DAudioSystem.SurroundFormat(DAudioSystem.SurroundFormats.SURROUND_FORMAT_NONE),
        )

    def test_is_signal_surround_master(self, test_mixer_connected: LawoMCXDevice):
        for i in range(0, 8):
            assert test_mixer_connected.is_signal_surround_master(i) is False
        assert test_mixer_connected.is_signal_surround_master(FU.FU_SURROUND_MASTER_BASE) is True

    async def test_get_surround_master(self, test_mixer_connected: LawoMCXDevice):
        for i in range(0, 6):
            sm = await test_mixer_connected.get_surround_master(i)
            check = FU.FU_SURROUND_MASTER_BASE + 0
            assert sm == check
        for i in range(8, 14):
            assert await test_mixer_connected.get_surround_master(i) == (FU.FU_SURROUND_MASTER_BASE + 1)

    async def test_mcx_bus_assign(self, test_mixer_connected: LawoMCXDevice):
        test_bus = FU.FU_SUMM_BASE
        test_mixer_connected.mcx_bus_assign(0, test_bus, True)

        # Check
        sum_num = MNumber.EU_Summe_Begin + (test_bus - FunktionseinheitType.get_fu_base(test_bus))
        connected: BoolType = await test_mixer_connected.mcx_get(sum_num, 0, data_type=BoolType)
        assert connected.value is True
        await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)

        # Cleanup
        test_mixer_connected.mcx_bus_assign(0, test_bus, False)

    async def test_mcx_sum_assign(self, test_mixer_connected: LawoMCXDevice):
        for sum in range(0, 5):
            # Test
            test_mixer_connected.mcx_sum_assign(0, sum, True)
            # Check
            sum_num = MNumber.EU_Summe_Begin.value + sum
            connected = await test_mixer_connected.mcx_get(sum_num, 0, BoolType)
            assert connected.value is True

            await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)
            # Cleanup
            # Test
            test_mixer_connected.mcx_sum_assign(0, sum, False)
            # Check
            connected = await test_mixer_connected.mcx_get(sum_num, 0, BoolType)
            assert connected.value is False

    async def test_mcx_group_assign(self, test_mixer_connected: LawoMCXDevice):
        for group in range(0, 5):
            # Test
            test_mixer_connected.mcx_group_assign(0, group, True)
            # Check
            group_num = MNumber.EU_Group_Begin.value + group
            connected = await test_mixer_connected.mcx_get(group_num, 0, BoolType)
            assert connected.value is True

            await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)
            # Test
            test_mixer_connected.mcx_group_assign(0, group, False)
            # Check
            connected = await test_mixer_connected.mcx_get(group_num, 0, BoolType)
            assert connected.value is False

    async def test_mcx_aux_assign(self, test_mixer_connected: LawoMCXDevice):
        for aux in range(0, 5):
            # Test
            test_mixer_connected.mcx_aux_assign(0, aux, True)
            # Check
            if aux & 1 != 0:
                aux_num = MNumber.EU_Aux1_OnOffR.value + 16 * (aux // 2)
            else:
                aux_num = MNumber.EU_Aux1_OnOffL.value + 16 * (aux // 2)
            connected = await test_mixer_connected.mcx_get(aux_num, 0, BoolType)
            assert connected.value is True

            await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)
            # Test
            test_mixer_connected.mcx_aux_assign(0, aux, False)
            # Check
            connected = await test_mixer_connected.mcx_get(aux_num, 0, BoolType)
            assert connected.value is False

    async def test_mcx_get_active_dsp(self, test_mixer_connected: LawoMCXDevice):
        dsp = await test_mixer_connected.mcx_get_active_dsp()
        assert dsp

    async def test_mcx_get_dsp_channel_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_channel_count()
        assert count

    async def test_mcx_get_dsp_bus_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_bus_count()
        assert count

    async def test_mcx_get_dsp_listen_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_listen_count()
        assert count

    async def test_mcx_get_dsp_automix_group_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_automix_group_count()
        assert count

    async def test_mcx_get_dsp_ext_key_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_ext_key_count()
        assert count

    async def test_mcx_get_dsp_talkback_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_talkback_count()
        assert count

    async def test_mcx_get_dsp_siggen_count(self, test_mixer_connected: LawoMCXDevice):
        count = await test_mixer_connected.mcx_get_dsp_siggen_count()
        assert count

    async def test_mcx_apply_uhd_dsp_config(self, test_mixer_connected: LawoMCXDevice):
        # Get the current config to cleanup later
        orig_config = await test_mixer_connected.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, MixerUserConfig)

        # Check for ValueError - Input, Aux, Sum and Groups must be multiples of 8
        with pytest.raises(ValueError):
            await test_mixer_connected.mcx_apply_uhd_dsp_config(1, 2, 3, 4, do_check=True)
        await test_mixer_connected.mcx_apply_uhd_dsp_config(32, 16, 8, 8, 2, 3, 4, do_check=True)
        await test_mixer_connected.wait_for(MNumber.SYSTEM_BLINK)

        # Cleanup
        test_mixer_connected.mcx_event(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, orig_config)

    async def test_apply_crm_config(self, test_mixer_connected: LawoMCXDevice):
        # Get the current config to cleanup later
        orig_config = await test_mixer_connected.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, MixerUserConfig)
        Crm1, Crm2, CrmHp1, CrmHp2 = True, False, True, False
        await test_mixer_connected.mcx_apply_crm_config(Crm1, Crm2, CrmHp1, CrmHp2)

        new_config = await test_mixer_connected.mcx_get(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, MixerUserConfig)

        check_config = orig_config
        logging.info(f"CRM Config: {check_config}")
        logging.info(f"CRM Config: {new_config}")

        check_config.crm1_enabled = Crm1
        check_config.crm2_enabled = Crm2
        check_config.crm_hp1_enabled = CrmHp1
        check_config.crm_hp2_enabled = CrmHp2

        try:
            if check_config != new_config:
                logging.info(MixerUserConfig.get_str_compare(check_config, new_config))
                assert False, "CRM Config did not match"
        finally:
            # Cleanup
            test_mixer_connected.mcx_event(MNumber.AUDIOSYSTEM_MIXER_USER_CONFIG, 0, orig_config)

    async def test_save_snapshot(self, test_mixer_connected: LawoMCXDevice):
        await test_mixer_connected.save_snapshot(TEST_PREFIX + "name", TEST_PREFIX + "folder")

        data = await test_mixer_connected._systemlink_connection.mcx_get_raw(MNumber.SYSTEM_SNAPSHOT, 0)
        d_folder, d_name = data[:32], data[32:]
        folder = StringType()
        folder.parse(d_folder)
        name = StringType()
        name.parse(d_name)
        assert folder.string == TEST_PREFIX + "folder"
        assert name.string == TEST_PREFIX + "name"

    async def test_load_snapshot(self, test_mixer_connected: LawoMCXDevice):
        await test_mixer_connected.save_snapshot(TEST_PREFIX + "name_old", TEST_PREFIX + "folder_old")
        await test_mixer_connected.save_snapshot(TEST_PREFIX + "name_new", TEST_PREFIX + "folder_new")
        await test_mixer_connected.load_snapshot(TEST_PREFIX + "name_old", TEST_PREFIX + "folder_old")

        # Check
        data = await test_mixer_connected._systemlink_connection.mcx_get_raw(MNumber.SYSTEM_SNAPSHOT, 0)
        d_folder, d_name = data[:32], data[32:]
        folder = StringType()
        folder.parse(d_folder)
        name = StringType()
        name.parse(d_name)

        assert folder.__str__() == TEST_PREFIX + "folder_old"
        assert name.__str__() == TEST_PREFIX + "name_old"

    async def test_delete_snapshot(self, test_mixer_connected: LawoMCXDevice):
        await test_mixer_connected.save_snapshot(TEST_PREFIX + "name", TEST_PREFIX + "folder")
        await test_mixer_connected.delete_snapshot(TEST_PREFIX + "name", TEST_PREFIX + "folder")

        data = await test_mixer_connected._systemlink_connection.mcx_get_raw(MNumber.SYSTEM_SNAPSHOT, 0)
        d_folder, d_name = data[:32], data[32:]
        folder = StringType()
        folder.parse(d_folder)
        name = StringType()
        name.parse(d_name)
        assert folder.__str__() == ""
        assert name.__str__() == ""

    def test_save_preset(self, test_mixer_connected: LawoMCXDevice):
        test_mixer_connected.save_preset(MNNumber(MNumber.EU_EQU_BASE, 0), TEST_PREFIX + "file")

    def test_load_preset(self, test_mixer_connected: LawoMCXDevice):
        test_mixer_connected.load_preset(MNNumber(MNumber.EU_EQU_BASE, 1), TEST_PREFIX + "file")

    async def test_get_currrent_production(self, test_mixer_connected: LawoMCXDevice):
        name = await test_mixer_connected.get_current_production()
        log.info(f"Current Production: {name}")

    async def test_save_production(self, test_mixer_connected: LawoMCXDevice):
        await test_mixer_connected.save_production(TEST_PREFIX + "production")

        name = await test_mixer_connected.get_current_production()
        assert name.__str__() == TEST_PREFIX + "production"

    async def test_load_production(self, test_mixer_connected: LawoMCXDevice):
        MAX_PROTDUCTION_LOAD_TIME = 30
        await test_mixer_connected.save_production(TEST_PREFIX + "production")
        await test_mixer_connected.save_production(TEST_PREFIX + "production_old")

        async with asyncio.timeout(MAX_PROTDUCTION_LOAD_TIME):
            await test_mixer_connected.load_production(TEST_PREFIX + "production")

        name = await test_mixer_connected.get_current_production()
        assert name.__str__() == TEST_PREFIX + "production"

        await test_mixer_connected.load_production(TEST_PREFIX + "production_old")

    async def test_delete_production(self, test_mixer_connected: LawoMCXDevice):
        raise pytest.skip("Currently not testable.")
        await test_mixer_connected.save_production(TEST_PREFIX + "production")
        await test_mixer_connected.delete_production(TEST_PREFIX + "production")

    async def test_assign_strip(self, test_mixer_connected: LawoMCXDevice):
        strip = 0
        fu_channel = 0
        test_mixer_connected.assign_strip(strip, fu_channel)

        check_fu_channel: MCX_STATE32 = await test_mixer_connected.mcx_get(
            MNumber.CONSOLE_STRIP_FRONT_CHANNEL, strip, data_type=MCX_STATE32
        )
        assert fu_channel == check_fu_channel.value

        # Cleanup
        test_mixer_connected.mcx_event(MNumber.CONSOLE_STRIP_FRONT_CHANNEL, strip, MNumberType(MNumber.INVALID_M))

    async def test_multi_assign_strip(self, test_mixer_connected: LawoMCXDevice):
        strip = 0
        fu_channel = 0
        test_mixer_connected.multi_assign_strip(strip, fu_channel, 5)

        for i in range(5):
            check_fu_channel: MCX_STATE32 = await test_mixer_connected.mcx_get(
                MNumber.CONSOLE_STRIP_FRONT_CHANNEL, strip + i, data_type=MCX_STATE32
            )
            assert fu_channel + i == check_fu_channel.value

        # Cleanup
        for i in range(5):
            test_mixer_connected.mcx_event(
                MNumber.CONSOLE_STRIP_FRONT_CHANNEL, strip + i, MNumberType(MNumber.INVALID_M)
            )

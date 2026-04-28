import asyncio
import logging
import time
from typing import Any, Iterable

from datamodel.endpoints import endpoints_home
from datamodel.sords.sords_pb2 import (AudCodec, Encap, Essence, Flow, Gate,
                                       Protection, Sord, Switching)

CREATE_SORD_TIMEOUT = 10
DEFAULT_CREATE_SORD_ATTRS = {
    "label": "ldf-default-sord",
    "ch_count": 8,
    "sample_rate": 48000,
    "frame_size": 32,
    "codec": "L24",
    "rtp_payload": 98,
    "ttl": 20,
    "pri": {
        "mcast_addr": "",
        "udp_port": 5011,
    },
    "sec": {
        "mcast_addr": "",
        "udp_port": 5015,
    },
    "is_tieline": False,
    "syntonized": False,
    "delay": 12,
}


class SordCreationError(Exception):
    pass


class LawoHomeNativeFlow:

    def __init__(self, flow: Flow, parent: 'LawoHomeNativeSord') -> None:
        self.pb = flow

        # Flow Identification
        self.ID = flow.ID
        self.label = flow.Label
        self.parent = parent

        # Media Content Information
        self.essence = flow.Essence
        self.encap = flow.Encap
        self.supported_encaps = [x for x in flow.SupportedEncaps]
        self.caps = [x for x in flow.Caps]
        self.ref_clock = flow.RefClk
        self.audio_params = flow.AudParams
        self.video_params = flow.VidParams

        # Stream Network Information
        self.media_interface = flow.MediaInterface
        self.primary = flow.Pri
        self.secondary = flow.Sec
        self.status_pri = flow.StatusPri
        self.status_sec = flow.StatusSec
        self.rtp_payload = flow.RtpPayload
        self.ttl = flow.TTL
        self.ssrc = flow.SSRC

        if self.essence == Essence.AUDIO:
            self.sample_rate = int(flow.AudParams.SampleRate)
            self.frame_size = int(flow.AudParams.FrameSize)
            self.ch_count = flow.AudParams.NumChans
            self.codec = flow.AudParams.Codec
            self.stream_info_parts = (
                f"{self.ch_count}ch {Encap.Name(self.encap)} "
                f"{int(self.sample_rate / 1000)} kHz, {AudCodec.Name(self.codec)}"
            )

        elif self.essence == Essence.VIDEO:
            self.stream_info_parts = "Video"
            self.scaling = flow.VidParams.Scaling

        elif self.essence == Essence.META:
            self.stream_info_parts = "Meta"

    def __repr__(self) -> str:
        if self.essence == Essence.AUDIO:
            return f"<{self.__class__.__name__} {self.label} {self.ID} {self.stream_info_parts} {self.packet_time}ms>"
        elif self.essence == Essence.VIDEO:
            return f"<{self.__class__.__name__} {self.label} {self.ID} {self.caps} {self.media_interface}"
        else:
            return f"<{self.__class__.__name__} {self.ID}"

    @property
    def address_label(self) -> str:
        """Return a properly formatted address label for the media flow

        This address label can be used to derive the correct Address object
        for this flow
        """
        return f"{self.parent.device_id}:{self.parent.ID}:{self.ID}"

    @property
    def packet_time(self) -> float:
        """Return the packet time in microseconds based on the sample rate and frame size"""
        try:
            return float((self.frame_size / self.sample_rate) * 1000)
        except ZeroDivisionError:
            return 0.0


class LawoHomeNativeSord:

    def __init__(self, sord: Sord, device_id: str) -> None:
        self.pb = sord
        self.device_id = device_id
        self.label = sord.Label
        self.ID = sord.ID
        self.interface = sord.MediaInterface
        self.flows = [LawoHomeNativeFlow(x, self) for x in sord.Flows]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.ID} {[flow for flow in self.flows]}>"


class LawoHomeNativeSords:

    def __init__(self, device) -> None:

        self.device = device
        self.log = logging.getLogger(__name__)
        self.sords = [
            LawoHomeNativeSord(sord, device.id)
            for sord in self.device.endpoint.Sords
        ]

    def __repr__(self) -> str:
        """Representation of sord is list of sord IDs"""
        return " | ".join(sord.label for sord in self.sords)

    def __call__(self, essence: str | None = None, direction: str | None = None) -> list[LawoHomeNativeSord]:
        """Request sord data from local endpoint cache and return a list matching the search criteria

        Args:
            essence (str, optional): Essence type of the requested sords. Defaults to None.
            direction (str, optional): Direction of the requested sords 'tx' / 'rx'. Defaults to None.

        Returns:
            list[LawoHomeNativeSord]: A list of sord objects matching search criteria
        """

        sords = [x for x in self.device.endpoint.Sords]
        if essence:
            sords = [x for x in sords if any(
                flow.Essence == getattr(Essence, essence.upper()) for flow in x.Flows)
            ]
        match direction:
            case None:
                pass
            case 'tx':
                sords = [x for x in sords if not x.IsDest]
            case 'rx':
                sords = [x for x in sords if x.IsDest]

        return sorted([LawoHomeNativeSord(x, self.device.id) for x in sords], key=lambda sord: sord.label)

    def __len__(self) -> int:
        """Return a count of all available sords on the device

        Returns:
            int: The number of AUDIO, VIDEO, GPIO + META sords on the device
        """
        return len([x for x in self()])

    def __iter__(self):
        """Provide an iterator of sords.sords_pb2.Sord objects"""
        for sord in self():
            yield sord

    async def _wait_for_sord_creation(self, src_label: str) -> None:
        """Block until a single endpoint.Sord update is received"""

        if not src_label:
            raise SordCreationError("No sord Label provided to wait for.")

        tn, perf = time.perf_counter(), 0.0
        while src_label not in [x.label for x in self()]:
            perf = time.perf_counter() - tn
            if perf > CREATE_SORD_TIMEOUT:
                raise SordCreationError(
                    f"Sord updates were not received within the specified timeout ({CREATE_SORD_TIMEOUT})."
                )
            else:
                await asyncio.sleep(.1)

        self.log.info(f"Created sord: {src_label} in {perf:.2f}s")

    async def _wait_for_sord_removal(self, sord_id: str) -> None:
        """Block until a given sord ID has been removed from the local endpoint cache

        Args:
            sord_id (str): The ID of the sord to wait for
        """

        tn, perf = time.perf_counter(), 0.0
        while sord_id in [x.ID for x in self()]:
            perf = time.perf_counter() - tn
            if perf > CREATE_SORD_TIMEOUT:
                raise SordCreationError(
                    f"Sord updates were not received within the specified timeout ({CREATE_SORD_TIMEOUT})."
                )
            else:
                await asyncio.sleep(.1)

        self.log.info(f"Removed sord: {sord_id} in {perf:.2f}s")

    async def get(self) -> Iterable[Sord]:
        """Request sord data directly from the device (bypasses local endpoint cache)

        Returns:
            Iterable[sords_pb2.Sord]: Requested sords from the device
        """

        sords, _ = await endpoints_home.endpoints_get_sords(
            self.device.client,
            self.device.id
        )
        return sords

    async def update(self, sords: list[Sord]) -> list[str]:
        """Modifiy existing senders via a set.sords request to the device

        Args:
            sords (list[sords_pb2.Sord]): A list of modified sord objects

        Returns:
            list[str]: A list of sord IDs for modified objects
        """

        self.log.info(f"Update sords {[x.ID for x in sords]}")
        ids, _ = await endpoints_home.endpoints_set_sords(
            self.device.client,
            self.device.id,
            sords
        )
        return ids

    async def remove_all(self) -> list[str]:
        """Remove all audio sords from the device

        Returns:
            list[str]: A list of removed sord IDs
        """

        tx_sords = [x.ID for x in self(direction='tx')]
        rx_sords = [x.ID for x in self(direction='rx')]
        self.log.info(f"Removing sords: {tx_sords + rx_sords}")
        ids, _ = await endpoints_home.endpoints_delete_sords(
            self.device.client,
            self.device.id,
            tx_sords + rx_sords
        )
        return ids

    async def remove(self, sords: list[Sord]) -> list[str]:
        """Remove one of more sords from the device by sord id

        Args:
            sord_ids (list[str]): list of sord IDs to be removed

        Returns:
            list[str]: list of sord IDs that were removed
        """

        for sord in sords:
            self.log.info(f"!!! Removing sord: {sord.ID}")
        ids, _ = await endpoints_home.endpoints_delete_sords(
            self.device.client, self.device.id, [sord.ID for sord in sords]
        )

        await asyncio.gather(
            *[self._wait_for_sord_removal(sord.ID) for sord in sords]
        )
        return ids

    async def _create_flow(self, essence: Essence, attrs: dict[str, Any]):

        flow = Flow(
            ID=Essence.Name(essence).lower(),
            Label="Automated Test Flow",
            Enable=True,
            Essence=essence,
            RtpPayload=attrs['rtp_payload'],
            TTL=attrs['ttl']
        )
        flow.Pri.McastIpAddr = attrs['pri']['mcast_addr']
        flow.Pri.DestPort = attrs['pri']['udp_port']
        flow.Sec.McastIpAddr = attrs['sec']['mcast_addr']
        flow.Sec.DestPort = attrs['sec']['udp_port']
        match essence:
            case Essence.AUDIO:
                flow.Caps.append(str(attrs['sample_rate']))
                if not attrs['is_dest']:
                    flow.AudParams.NumChans = attrs['ch_count']
                    flow.AudParams.FrameSize = attrs['frame_size']
                    flow.AudParams.Codec = getattr(AudCodec, attrs['codec'])
                    flow.AudParams.SampleRate = attrs['sample_rate']
                    flow.AudParams.ChannelOrder = ""
                else:
                    flow.SrcGate.MergeFrom(Gate())
                    flow.AudParams.Delay = attrs['delay']
                    flow.AudParams.Syntonized = attrs['syntonized']
                    flow.AudParams.MaxRxChans = attrs['channel_count']

            case Essence.VIDEO:
                self.log.warning("Not implemented")

            case Essence.META:
                self.log.warning("Not implemented")

            case Essence.GPIO:
                self.log.warning("Not implemented")

        return flow

    async def create(self, count: int, is_dest: bool = False, flows: list[str] = ['audio'],
                     **kwargs) -> list[LawoHomeNativeSord]:
        """Create any type of network sender/receiver types on the host device.

        Additional attributes can be supplied as kwargs to modify the created
        flows. Where flow attributes are not explicitly defined, a default is
        used.

        Args:
            count (int): Number of sord instances to create.
            is_dest (bool, optional): Creates a receiver sord if True. Defaults to False.
            flows (list[str], optional): Define flow types contained in the sord. Defaults to ['audio'].

        Returns:
            list[LawoHomeNativeSord]: Native sord object for each sord created on the device.
        """

        try:
            self.device.flags['CreateDeleteSords']
            interface = next(iface for iface in self.device.interfaces
                            if iface.iface_media != "-")
        except KeyError:
            raise SordCreationError(f"{self.device.label} is unable to create sords")
        except StopIteration:
            self.log.error("Failed to determine NetworkInterface")

        # Define flow count and attributes
        essences = [getattr(Essence, essence.upper()) for essence in flows]
        attrs = {**DEFAULT_CREATE_SORD_ATTRS, **kwargs}
        attrs['is_dest'] = is_dest
        sords = [
            Sord(
                ID="aulait.test.sord",
                MediaInterface=interface.iface_media,
                Label=attrs['label'],
                Flows=[await self._create_flow(essence, attrs) for essence in essences],
                IsDest=is_dest,
                Protection=Protection.DualRedundant,
                Switching=Switching.Default,
                IsExternalTieline=attrs['is_tieline']
            ) for _ in range(count)
        ]

        resp, err = await endpoints_home.endpoints_create_sords(
            self.device.client,
            self.device.id,
            sords
        )
        if not err:
            # Block until the expected sord updates are received
            await asyncio.gather(
                *[self._wait_for_sord_creation(sord.Label) for sord in resp]
            )
        else:
            raise SordCreationError(f"Failed to create sords: {err}")

        return [LawoHomeNativeSord(sord, self.device.id) for sord in resp]

    # TODO: Deprecated by `self.create`
    def _generate_sords(self, label: str, count: int) -> Sord:
        """Generate a partially populated set of sord objects

        Args:
            label (str): Label to apply to sord and flows
            count (int): Number of sords to generate

        Yields:
            sords_pb2.Sord: Iterator of sords to the number specified
        """

        for iface in self.device.interfaces():
            if iface.iface_media == "-":
                continue
            interface = iface
            break

        sords = [Sord() for _ in range(count)]
        for sord in sords:
            sord.Label = label
            sord.MediaInterface = interface.iface_media
            sord.Protection = Protection.DualRedundant
            sord.Switching = Switching.Default
            sord.Flows.append(
                self._generate_flows(
                    type=Essence.AUDIO,
                    encap=Encap.SMPTE2110_30
                )
            )

        return sords

    # TODO: Deprecated by `self.create`
    def _generate_flows(self, type: Essence, encap: Encap) -> list[Flow]:
        """Create flow objects using the specified configuration

        Args:
            type (sords_pb2.Essence): Essence type of flow to create
            encap (sords_pb2.Encap): Encap of the flow

        Returns:
            list[sords_pb2.Flow]: A list of configured flows
        """

        flow = Flow()
        flow.ID = "audio"
        flow.Label = "Automated Test Flow"
        flow.Enable = True
        flow.Essence = type
        flow.Encap = encap
        return flow

    # TODO: Deprecated by `self.create`
    async def create_audio(
            self,
            count: int,
            ch_count: None | int = None,
            direction: str = 'tx',
            label: str = "ldf-create-audio-sord",
            attrs: None | dict[str, Any] = None,
            event: None | asyncio.Event = None
    ) -> Iterable[Sord]:
        """Create an audio network streamer on the device via NATs request.

        A dictionary can be passed to the `attrs` parameter to apply specific
        flow attributes to the created sords.

        This cororoutine will block until the expected sord updates are
        received.

        Args:
            count (int): Number of sord objects to create
            ch_count (int, optional): Number of channels for each sord. Overridden by value priovided in attrs.
            direction (str, optional): Create a 'tx' or 'rx' sord object on the device. Defaults to 'tx'.
            label (str, optional): Label to apply to created sord objects. Defaults to "ldf-create-audio-sord".
            attrs (dict[str, int | str | bool], optional): Flow attributes for the created sords. Defaults to {}.
            event (asyncio.Event, optional): Asyncio Event object, settable when updates are received. Defaults to None.

        Raises:
            SordCreationError: Raised if called by an endpoint that does not have the CreateDeleteSords flag.

        Returns:
            Iterable[sords_pb2.Sord]: A repeated conatiner containing the created sords protobuf objects
        """

        self.log.warning("""The `create_audio` method is marked for deprecation in a later release,
                         please consider using the `device.sords.create` method instead
        """)
        try:
            self.device.flags['CreateDeleteSords']
        except KeyError:
            raise SordCreationError(f"{self.device.label} is unable to create sords")

        # Combine default flow attrs with user. Duplicates take the user value.
        if not attrs:
            attrs = {}
        attrs = {**DEFAULT_CREATE_SORD_ATTRS, **attrs}
        sords = [x for x in self._generate_sords(label=label, count=count)]
        for sord in sords:

            for flow in sord.Flows:
                flow.Caps.append(str(attrs['sample_rate']))
                if direction == 'tx':
                    flow.Pri.McastIpAddr = attrs['pri']['mcast_addr']
                    flow.Pri.DestPort = attrs['pri']['udp_port']
                    flow.Sec.McastIpAddr = attrs['sec']['mcast_addr']
                    flow.Sec.DestPort = attrs['sec']['udp_port']
                    flow.RtpPayload = attrs['rtp_payload']
                    flow.TTL = attrs['ttl']
                    flow.AudParams.NumChans = ch_count if not attrs['ch_count'] else attrs['ch_count']
                    flow.AudParams.FrameSize = attrs['frame_size']
                    flow.AudParams.Codec = AudCodec.L24
                    flow.AudParams.SampleRate = attrs['sample_rate']
                    flow.AudParams.ChannelOrder = ""
                elif direction == 'rx':
                    sord.IsExternalTieline = attrs['is_tieline']
                    sord.IsDest = True
                    flow.SrcGate.MergeFrom(Gate())
                    flow.AudParams.Delay = attrs['delay']
                    flow.AudParams.Syntonized = attrs['syntonized']
                    flow.AudParams.MaxRxChans = ch_count if not attrs['ch_count'] else attrs['ch_count']

        resp, err = await endpoints_home.endpoints_create_sords(
            self.device.client,
            self.device.id,
            sords
        )
        if err:
            raise SordCreationError(f"Failed to create sords: {err}")

        # Workaround to handle a device not returning sord ID in the response.
        # This is only required for Merging devices.
        # We match the sords in the local endpoint cache by label (assumes update)
        if not any([x.ID for x in resp]):
            self.log.warning("No sord IDs were returned. Matching by label.")
            time.sleep(1)
            resp = [x for x in self() if x.label == label]

        # Block until the expected sord updates are received
        await asyncio.gather(
            *[self._wait_for_sord_creation(sord.Label) for sord in resp]
        )

        if event:
            event.set()
        return resp

    async def get_sdp(self, sord: Sord, target_flow: str) -> str | None:
        """Get the SDP file data for the given sord object on the device

        Args:
            sord (sords_pb2.Sord): The Sord object containing the target flow
            target_flow (str): the ID of the desired flow object

        Returns:
            str | None: String representation of the target flow SDP file
        """

        _, sdp, _, _ = await endpoints_home.endpoints_get_sord_sdp(
            self.device.client,
            self.device.id,
            sord.ID,
            target_flow
        )

        return sdp if sdp != "" else None

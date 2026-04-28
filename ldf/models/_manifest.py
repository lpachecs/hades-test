from ldf.models.amic import LawoAmicDevice
from ldf.models.astage import LawoAstageDevice
from ldf.models.edge import LawoDotEdgeDevice
from ldf.models.kero import (LawoAppServer, LawoColourCorrectorApp, LawoDSKApp,
                             LawoGraphicInserterApp, LawoHomeNativeApp,
                             LawoMultiViewerApp, LawoStreamTranscoderApp,
                             LawoTimecodeGeneratorApp, LawoTPGApp, LawoUDXApp,
                             LawoVirtualMixerApp)
from ldf.models.lcu import LawoLcuDevice
from ldf.models.local_io import LawoLocalIODevice
from ldf.models.mcx import LawoMCXDevice
from ldf.models.powercore import LawoPowercoreDevice
from ldf.models.switch import LawoHomeNetworkSwitch
from ldf.models.ThirdPartyVirtual import LawoThirdPartyVirtualDevice
from ldf.models.uhd_core import LawoUhdCoreDevice, LawoVirtualMixerSlice
from ldf.models.vmatrix_c100 import LawoVmatrixDevice

model_manifest = {
    ".edge": LawoDotEdgeDevice,
    "A__UHD Core": LawoUhdCoreDevice,
    "mc2_36 UHD Core": LawoUhdCoreDevice,
    "Virtual Mixer": LawoVirtualMixerSlice,
    "mcx": LawoMCXDevice,
    "MCX Control Software": LawoMCXDevice,
    "Local I/O": LawoLocalIODevice,
    "A__mic8": LawoAmicDevice,
    "A__stage48": LawoAstageDevice,
    "A__stage64": LawoAstageDevice,
    "PowerCore": LawoPowercoreDevice,
    "Power Core Control System App": LawoHomeNativeApp,
    "LCU": LawoLcuDevice,
    "Third Party Device": LawoThirdPartyVirtualDevice,
    "V__Matrix C100": LawoVmatrixDevice,
    "App Server": LawoAppServer,
    "mc² DSP App": LawoVirtualMixerApp,
    "Multiviewer App": LawoMultiViewerApp,
    "UDX App": LawoUDXApp,
    "Graphic Inserter App": LawoGraphicInserterApp,
    "Test Pattern Generator App": LawoTPGApp,
    "Stream Transcoder App": LawoStreamTranscoderApp,
    "DSK App": LawoDSKApp,
    "Color Corrector App": LawoColourCorrectorApp,
    "Timecode Generator App": LawoTimecodeGeneratorApp,
    "Delay Inserter App": LawoHomeNativeApp,
    "Power Core DSP App": LawoHomeNativeApp,
    "Audio Shuffler App": LawoHomeNativeApp,
    "Demo Home App": LawoHomeNativeApp,
    "Synergy Home App": LawoHomeNativeApp,
    "Arista Switch": LawoHomeNetworkSwitch,
    "N9K-C9332D-GX2B": LawoHomeNetworkSwitch,
}

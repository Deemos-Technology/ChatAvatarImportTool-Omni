import enum
from typing import Optional
from dataclasses import dataclass

class CAPackException(Exception):
    pass

class InvalidPack(CAPackException):
    pass

#region Basic Package Info
class TextureResolution(enum.Enum):
    TwoK = 2048
    FourK = 4096

class Topology(enum.Enum):
    MetaHuman = "MetaHuman"
    Default = "Default"

@dataclass(frozen=True)
class PackInfo:
    resolution: TextureResolution
    topology: Topology

ALL_PACK_INFOS = [PackInfo(res, top) for res in TextureResolution for top in Topology]

def generate_pack_name(pack_info: PackInfo) -> str:
    topology_lookup = {
        Topology.MetaHuman: "MH",
        Topology.Default: "USC",
    }
    res_lookup = {
        TextureResolution.FourK: "High",
        TextureResolution.TwoK: "Basic",
    }
    return f"{topology_lookup[pack_info.topology]}{res_lookup[pack_info.resolution]}Pack"
#endregion


#region Additional Elements
class AdditionalElements(enum.Flag):
    Nothing = None
    RiggedBody = "Rigged Body"
    Components = "Eye & Teeth"
    BlendShapes = "Expression BlendShapes"
    BackHeadTex = "Back Head Textures"

    def __new__(cls, friendly_name_in: Optional[str]):
        assert (isinstance(friendly_name_in, str) and friendly_name_in) or (friendly_name_in is None)

        if friendly_name_in:
            value = 1 << len([i for i in cls.__members__.values() if i.value])
            friendly_name = friendly_name_in
        else:
            if [i for i in cls.__members__.values() if not i.value]:
                raise ValueError("More than one element is empty element!")
            value = 0
            friendly_name = "None"

        obj = object().__new__(cls)
        obj._value_ = value
        obj.friendly_name = friendly_name
        return obj
#endregion
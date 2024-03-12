import os
from os import PathLike
from typing import List
import zipfile
import tempfile
import shutil
# import bpy
from .defs import *
from .utils import *
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

class Pack:
    """Main Package Class"""
    #region Basic Package Info
    pack_paths = {
        PackInfo(TextureResolution.TwoK, Topology.MetaHuman): {
            "model": 'MHBasicPack/model.obj',
            "texture_diffuse": 'MHBasicPack/texture_diffuse.png',
            "texture_normal": 'MHBasicPack/texture_normal.png',
            "texture_specular": 'MHBasicPack/texture_specular.png',
        },
        PackInfo(TextureResolution.TwoK, Topology.Default): {
            "model": 'USCBasicPack/model.obj',
            "texture_diffuse": 'USCBasicPack/texture_diffuse.png',
            "texture_normal": 'USCBasicPack/texture_normal.png',
            "texture_specular": 'USCBasicPack/texture_specular.png',
        },
        PackInfo(TextureResolution.FourK, Topology.MetaHuman): {
            "model":'MHHighPack/model.obj',
            "texture_diffuse":'MHHighPack/texture_diffuse.png',
            "texture_normal":'MHHighPack/texture_normal.png',
            "texture_specular":'MHHighPack/texture_specular.png',
        },
        PackInfo(TextureResolution.FourK, Topology.Default): {
            "model": 'USCHighPack/model.obj',
            "texture_diffuse": 'USCHighPack/texture_diffuse.png',
            "texture_normal": 'USCHighPack/texture_normal.png',
            "texture_specular": 'USCHighPack/texture_specular.png',
        },
    }
    pack_checkers = {
        k: file_checker([[i] for i in v.values()]) for k, v in pack_paths.items()
    }

    @staticmethod
    def list_packs(fps: List[str]) -> List[PackInfo]:
        results = []
        for pack_info in ALL_PACK_INFOS:
            is_complete_pack = Pack.pack_checkers[pack_info](fps)
            if is_complete_pack:
                results.append(pack_info)
        return results
    # endregion

    #region Additional Package Elements
    has_back_head_texture = file_checker([
        ["USCBasicPack/texture_diffuse_backhead.png"],
        ["USCBasicPack/texture_normal_backhead.png"],
        ["USCBasicPack/texture_specular_backhead.png"],
    ])

    has_rigged_body = file_checker([
        ["USCBasicPack/additional_body.fbx"],
    ])

    has_components = file_checker([
        [
            "USCBasicPack/additional_component.fbx",
            "USCBasicPack/additional_component_neutral.obj" # When no blendshape applied
        ]
    ])

    has_blendshapes = file_checker([
        ["USCBasicPack/additional_blendshape.fbx"],
    ])
    # endregion

    def __init__(self, fp: PathLike, unpack_mode):
        assert unpack_mode in {"temp", "local"}
        self.unpack_mode = unpack_mode
        self.original_zip_filepath = fp
        self.pack_name = os.path.basename(fp)[::-1].replace("piz.", "", 1)[::-1]

        if unpack_mode == "temp":
            self.temp_dir = tempfile.TemporaryDirectory()
            self.unpack_path = os.path.join(self.temp_dir.name, self.pack_name)
        elif unpack_mode == "local":
            self.unpack_path = os.path.join(os.path.dirname(self.original_zip_filepath), self.pack_name)

        # Get metadata of package
        try:
            with zipfile.ZipFile(fp, 'r') as z:
                self.file_list = z.namelist()
                # Available packs
                ## Flags
                self.available_packs = Pack.list_packs(self.file_list)
                if self.available_packs:
                    os.makedirs(self.unpack_path, exist_ok=True)
                    # Overwrite logic
                    self.unpack_path = safe_extractall(z, self.unpack_path)
                    logger.debug(f"{fp} is extracted to {self.unpack_path}")
                else:
                    raise InvalidPack
        except zipfile.BadZipFile:
            raise InvalidPack

        # Base metadata
        ## Prompt
        if "prompt.txt" in self.file_list:
            with open(os.path.join(self.unpack_path, "prompt.txt"), encoding="utf8") as f:
                self.prompt_txt = f.read().strip().replace(chr(160), " ")
        else:
            self.prompt_txt = ""
        ## Preview Image
        self.preview_image_path = os.path.join(self.unpack_path, "image.png")

        # Additional elements
        ## Flags
        self.additional_elements = \
            (AdditionalElements.RiggedBody  if Pack.has_rigged_body(self.file_list)       else AdditionalElements.Nothing) | \
            (AdditionalElements.Components  if Pack.has_components(self.file_list)        else AdditionalElements.Nothing) | \
            (AdditionalElements.BlendShapes if Pack.has_blendshapes(self.file_list)       else AdditionalElements.Nothing) | \
            (AdditionalElements.BackHeadTex if Pack.has_back_head_texture(self.file_list) else AdditionalElements.Nothing)

    def pack_file_paths(self, picked_pack):
        """keys: ["model", "diffuse", "specular", "normal"], values: corresponding paths
        """
        return {
            key: os.path.join(self.unpack_path, value) for key, value in Pack.pack_paths[picked_pack].items()
        }

    def additional_elements_paths(self):
        results = {}
        if AdditionalElements.BackHeadTex & self.additional_elements:
            results[AdditionalElements.BackHeadTex] = {
                "texture_diffuse": os.path.join(self.unpack_path, "USCBasicPack/texture_diffuse_backhead.png"),
                "texture_normal": os.path.join(self.unpack_path, "USCBasicPack/texture_normal_backhead.png"),
                "texture_specular": os.path.join(self.unpack_path, "USCBasicPack/texture_specular_backhead.png"),
            }
        if AdditionalElements.RiggedBody & self.additional_elements:
            results[AdditionalElements.RiggedBody] = os.path.join(self.unpack_path, "USCBasicPack/additional_body.fbx")
        if AdditionalElements.Components & self.additional_elements:
            if AdditionalElements.BlendShapes & self.additional_elements:
                results[AdditionalElements.Components] = os.path.join(self.unpack_path, "USCBasicPack/additional_component.fbx")
            else:
                results[AdditionalElements.Components] = os.path.join(self.unpack_path, "USCBasicPack/additional_component_neutral.obj")
        if AdditionalElements.BlendShapes & self.additional_elements:
            results[AdditionalElements.BlendShapes] = os.path.join(self.unpack_path, "USCBasicPack/additional_blendshape.fbx")
        return results
        

    def __del__(self):
        if self.unpack_mode == "temp":
            self.temp_dir.cleanup()
from __future__ import annotations
import omni.ext
import omni.kit.menu.utils as menu_utils
import omni.kit.actions.core as actions_core
from omni.services.core import main
import sys
import os
import subprocess
import importlib
import importlib.util
import carb
from .ChatAvatarPack import defs as CADefs
from . import omni_funcs
import asyncio
import sys

from typing import Dict, List, Optional, Union
if sys.version_info >= (3, 8):
    from typing import TypedDict  # pylint: disable=no-name-in-module
else:
    from typing_extensions import TypedDict

from omni.services.core import routers
from pydantic import BaseModel, Field

#region server

class AdditionalPathsItemType(TypedDict):
    part: CADefs.AdditionalElements
    value: Union[str, TexturePathsItemType]

class TexturePathsItemType(TypedDict):
    texture_diffuse: str
    texture_normal: str
    texture_specular: str
    

class ChatAvatarImportRequestModel(BaseModel):
    model_path: str = Field(
        default=...,
        title="Model Path",
        description="Path to the fbx/obj file"
    )
    obj_name: str = Field(
        default=...,
        title="Object Name",
        description="Not used"
    )
    texture_paths: TexturePathsItemType = Field(
        default=...,
        title="Texture Paths",
        description="Paths to diffuse, normal, specular texture image"
    )
    selected_pack_resolution: CADefs.TextureResolution = Field(
        default=...,
        title="Selected Texture Resolution",
    )
    selected_pack_topology: CADefs.Topology = Field(
        default=...,
        title="Selected Topology",
    )   
    selected_additional: CADefs.AdditionalElements = Field(
        default=...,
        title="Selected additional parts",
    )
    available_additional: CADefs.AdditionalElements = Field(
        default=...,
        title="Available additional parts",
        description="All availabe additional parts in selected pack"
    )
    pack_name: str = Field(
        default=...,
        title="Pack name"
    )
    additional_paths: List[AdditionalPathsItemType] = Field(
        default=...,
        title="Additional item paths",
    )

class ChatAvatarResponseModel(BaseModel):
    success: bool = Field(
        default=False,
        title="Import status",
        description="Status of the importing of the given pack and parameter set.",
    )
    error_message: Optional[str] = Field(
        default=None,
        title="Error message",
        description="Optional error message in case the operation was not successful.",
    )

class ChatAvatarResponseModel(BaseModel):
    success: bool = Field(
        default=False,
        title="Import status",
        description="Status of the importing of the given pack and parameter set.",
    )
    error_message: Optional[str] = Field(
        default=None,
        title="Error message",
        description="Optional error message in case the operation was not successful.",
    )

router = routers.ServiceAPIRouter()
#endregion

@router.get(
    path="/ping",
    summary="Extension ping",
    tags=["ChatAvatar"]
)
async def ping():
    return "pong"

@router.post(
    path="/import",
    summary="Import ChatAvatar Pack",
    response_model=ChatAvatarResponseModel,
    tags=["ChatAvatar"]
)
async def import_pack(request: ChatAvatarImportRequestModel) -> ChatAvatarResponseModel:
    try:
        fut = asyncio.ensure_future(
            omni_funcs.import_pack(
                model_path=request.model_path,
                obj_name=request.obj_name,
                texture_paths=request.texture_paths,
                selected_pack=CADefs.PackInfo(
                    resolution=request.selected_pack_resolution,
                    topology=request.selected_pack_topology
                ),
                selected_additional=request.selected_additional,
                available_additional=request.available_additional,
                pack_name=request.pack_name,
                additional_paths={
                    item["part"]: item["value"]
                    for item in request.additional_paths
                },
            )
        )
        await fut
    except Exception as e:
        return ChatAvatarResponseModel(success=False, error_message=f"{type(e).__name__}: {e}")
    else:
        return ChatAvatarResponseModel(success=True, error_message=None)

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class DeemosChatavatarImport_toolExtension(omni.ext.IExt):
    MENU_PATH = "File/Launch ChatAvatar Import Tool"
    EXTENSION_ID = "deemos.chatavatar.import_tool"
    @staticmethod
    def find_python_path():
        if sys.platform == 'win32':
            executable_path = os.path.abspath(os.path.join(os.path.dirname(os.__file__), "..", "python.exe"))
        else:
            executable_path = os.path.abspath(os.path.join(os.path.dirname(os.__file__), "..", "..", "bin", "python3"))
        return executable_path

    @staticmethod
    def find_PySide6_path():
        spec = importlib.util.find_spec("PySide6")
        pyside6_path = os.path.abspath(os.path.join(os.path.dirname(spec.origin), ".."))
        return pyside6_path

    def set_transfer_path(self):
        https_used = carb.settings.get_settings().get_as_bool(
            f'exts/omni.services.transport.server.http/https/enabled'
        )
        if https_used:
            port = carb.settings.get_settings().get_as_string(
                f'exts/omni.services.transport.server.http/https/port'
            )
        else:
            port = carb.settings.get_settings().get_as_string(
                f'exts/omni.services.transport.server.http/port'
            )
        self.url = f"http{'s' if https_used else ''}://localhost:{port}{self.url_prefix}"

    def kill_window(self):
        if isinstance(self.window_process, subprocess.Popen):
            if not isinstance(self.window_process.poll(), int):
                self.window_process.kill()

    def pop_window(self):
        self.kill_window()

        args = [
            self.find_python_path(),
            "ui_launcher.py",
            "--url", self.url
        ]
        env = {
            **os.environ,
            "PYTHONPATH": ";".join([self.PySide6_path])
        }
        carb.log_warn(
            f"cd {os.path.dirname(__file__)}; "
            f'$env:PYTHONPATH=\'{env["PYTHONPATH"]}\'; '
            f"{' '.join(args)}; "
            f"$env:PYTHONPATH=''"
        )
        self.window_process = subprocess.Popen(
            args,
            cwd=os.path.dirname(__file__),
            env=env,
        )

    def on_startup(self, ext_id):
        print("[deemos.chatavatar.import_tool] deemos chatavatar import_tool startup")
        # Ensure PySide6 installed.
        self.PySide6_path = self.find_PySide6_path()
        # Register action
        self._action_registry = actions_core.get_action_registry()
        self._action_registry.register_action(
            self.EXTENSION_ID,
            "launch_import_tool",
            self.pop_window,
            display_name="ChatAvatar Import Tool->Launch Import Tool",
            description="Launch Import Tool",
        )
        self._action_registry.register_action(
            self.EXTENSION_ID,
            "import_pack",
            import_pack,
        )
        # Add menu item
        self._menu_item_list = [
            menu_utils.MenuItemDescription(
                "Launch Import Tool",
                onclick_action=(self.EXTENSION_ID, "launch_import_tool"),
            )
        ]
        menu_utils.add_menu_items(self._menu_item_list, "ChatAvatar Import Tool")
        self.window_process = None
        # register router
        ext_name = ext_id.split("-")[0]
        self.url_prefix = carb.settings.get_settings().get_as_string(f"exts/{ext_name}/url_prefix")
        main.register_router(router=router, prefix=self.url_prefix)
        self.set_transfer_path()
        

    def on_shutdown(self):
        print("[deemos.chatavatar.import_tool] deemos chatavatar import_tool shutdown")
        self._action_registry.deregister_all_actions_for_extension(self.EXTENSION_ID)
        menu_utils.remove_menu_items(self._menu_item_list, "ChatAvatar Import Tool")
        # deregister router
        main.deregister_router(router=router)
        

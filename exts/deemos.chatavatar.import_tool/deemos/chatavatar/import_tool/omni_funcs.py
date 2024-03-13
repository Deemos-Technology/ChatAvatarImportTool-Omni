from __future__ import annotations
from typing import Set
import omni.usd
import omni.kit.commands
from .ChatAvatarPack import defs as CADefs
import carb
import omni.kit.asset_converter
import tempfile
import zipfile
import os
from datetime import datetime
import re

from pxr import Sdf, Usd, UsdShade, UsdGeom

DEFAULT_MTLS = frozenset(["Face"])
BACKHEAD_MTLS = frozenset(["Backhead"])
COMPONENTS_MTLS = frozenset(["Eye","Eyelashes","Fluid","Occlusion","Teeth","Teeth_fluid"])

def determine_material_by_slot_name(
    slot_name: str,
    selected_pack: CADefs.PackInfo,
    selected_additional: CADefs.AdditionalElements,
    available_additional: CADefs.AdditionalElements,
    materials_need_to_apply: Set[str]
):
    if selected_pack.topology == CADefs.Topology.MetaHuman:
        return {
            "name": "Face",
            "variant": None
        }
    elif selected_pack.topology == CADefs.Topology.Default:
        if "Eyelashes" in materials_need_to_apply and \
            any(i in slot_name for i in {"M_EyeLashes"}) and \
            available_additional & CADefs.AdditionalElements.Components:
            return {
                "name": "Eyelashes",
                "variant": None
            }
        if "TeethFluid" in materials_need_to_apply and \
            any(i in slot_name for i in {"teeth_fluid"}) and \
            available_additional & CADefs.AdditionalElements.Components:
            return {
                "name": "TeethFluid",
                "variant": None
            }
        if "Occlusion" in materials_need_to_apply and \
            any(i in slot_name for i in {"Occ"}) and \
            available_additional & CADefs.AdditionalElements.Components:
            return {
                "name": "Occlusion",
                "variant": None
            }
        if "Eye" in materials_need_to_apply and \
            any(i in slot_name for i in {"left_eyeball", "right_eyeball"}) and \
            available_additional & CADefs.AdditionalElements.Components:
            variant = None
            if "left_eyeball" in slot_name:
                variant = "left"
            elif "right_eyeball" in slot_name:
                variant = "right"
            return {
                "name": "Eye",
                "variant": variant
            }
        if "Teeth" in materials_need_to_apply and \
            any(i in slot_name for i in {"teeth"}) and \
            available_additional & CADefs.AdditionalElements.Components:
            return {
                "name": "Teeth",
                "variant": None
            }
        if "Fluid" in materials_need_to_apply and \
            any(i in slot_name for i in {"Fluid"}) and \
            available_additional & CADefs.AdditionalElements.Components:
            return {
                "name": "Fluid",
                "variant": None
            }
        if "Face" in materials_need_to_apply and \
            any(i in slot_name for i in {"face", "M_Face"}):
            return {
                "name": "Face",
                "variant": None
            }
        if "Backhead" in materials_need_to_apply and \
            any(i in slot_name for i in {"back", "M_BackHead"}) and \
            available_additional & CADefs.AdditionalElements.BackHeadTex:
            return {
                "name": "Backhead",
                "variant": None
            }
        return None

async def import_pack(
    model_path: str,
    obj_name: str,
    texture_paths: dict[str, str],
    selected_pack: CADefs.PackInfo,
    selected_additional: CADefs.AdditionalElements,
    available_additional: CADefs.AdditionalElements,
    pack_name: str,
    additional_paths: dict[CADefs.AdditionalElements, dict[str, str] | str],
):
    # Init
    import_unique_id = f"{pack_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    omni_texture_path = os.path.join(
        os.path.dirname(os.path.dirname(model_path)),
        f"Omni_Directory",
        "Textures",
    )

    omni_import_dir = os.path.join(
        os.path.dirname(os.path.dirname(model_path)),
        f"Omni_Directory",
        import_unique_id,
    )
    os.makedirs(omni_import_dir, exist_ok=True)
    os.makedirs(omni_texture_path, exist_ok=True)

    output_usd_path = os.path.join(
        omni_import_dir,
        f"main.usd",
    )

    # For obj, generate mtl files to correctly generate default materials
    if model_path.endswith(".obj"):
        gen_mtl_files(model_path)

    # Create stage & layer
    main_stage = Usd.Stage.CreateNew(output_usd_path)  

    # Create new prim(Scope) to hold all imported items
    main_prim_path = Sdf.Path(f"/ChatAvatar_{import_unique_id}")
    main_prim = main_stage.DefinePrim(main_prim_path, "Xform")
    main_stage.SetDefaultPrim(main_prim)
    # Create new prim(Xform) to hold reference
    model_prim_path = main_prim_path.AppendChild("model")
    model_prim = main_stage.DefinePrim(model_prim_path, "Xform")
    model_prim.GetReferences().AddReference(model_path)

    # Do scaling
    if (selected_additional & CADefs.AdditionalElements.RiggedBody) or \
       model_path.endswith(".obj"):
        xformable = UsdGeom.Xformable(model_prim)
        for op in xformable.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeScale:
                # 找到现有的缩放操作，更新它的值
                op.Set(value=(100.0, 100.0, 100.0))
                break

    # Create new prim(Scope) to hold new materials
    material_scope_prim_path = main_prim_path.AppendChild("Materials")
    material_scope_prim = main_stage.DefinePrim(material_scope_prim_path, "Scope")

    materials_new = material_usage_summary(model_prim)
    carb.log_warn(materials_new)
    # Apply material
    ## Find materials to apply
    materials_need_to_apply = set(DEFAULT_MTLS)
    if selected_pack.topology == CADefs.Topology.MetaHuman:
        # Only Face is needed
        pass
    elif selected_pack.topology == CADefs.Topology.Default:
        # Backhead
        if selected_additional & CADefs.AdditionalElements.BackHeadTex:
            materials_need_to_apply |= set(BACKHEAD_MTLS)
        # Components
        if selected_additional & CADefs.AdditionalElements.Components:
            materials_need_to_apply |= set(COMPONENTS_MTLS)
        elif (selected_additional & CADefs.AdditionalElements.RiggedBody) and (available_additional & CADefs.AdditionalElements.Components):
            materials_need_to_apply |= set(COMPONENTS_MTLS)
    else:
        raise NotImplementedError("Unknown topology!")

    ## Import needed materials
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(
            os.path.join(
                os.path.dirname(__file__),
                "OmniChatAvatarImportTool_resources.zip"
            )
        ) as resource_zipf:
            needed_textures = set()
            # Extract needed materials
            for material in materials_need_to_apply:
                temp_material_usda_path = os.path.join(
                    temp_dir,
                    f"{material}.material.usda"
                )
                with resource_zipf.open(f"resources/Shader/{material}.material.usda", "r") as material_zipf:
                    material_content = material_zipf.read().decode()
                    new_textures = re.findall(r'@(\{OMNI_TEXTURE_PATH\}/.+)@', material_content)
                    needed_textures.update(new_textures)
                    with open(temp_material_usda_path, "wb") as material_f:
                        material_f.write(material_content.encode("utf-8"))
            # Extract needed textures
            for texture in needed_textures:
                if os.path.exists(
                    texture.format(OMNI_TEXTURE_PATH=omni_texture_path)
                ):
                    continue
                extracted_path = texture.format(OMNI_TEXTURE_PATH=omni_texture_path)
                os.makedirs(os.path.dirname(extracted_path), exist_ok=True)
                with resource_zipf.open(texture.format(OMNI_TEXTURE_PATH="resources/Texture"), "r") as f1:
                    with open(extracted_path, "wb") as f2:
                        f2.write(f1.read())
        
        new_materials = {}
        for material in materials_need_to_apply:
            temp_material_usda_path = os.path.join(
                temp_dir,
                f"{material}.material.usda"
            )
            material_usdc_path = os.path.join(
                omni_import_dir,
                f"{material}.material.usdc"
            )
            # replace file path
            with open(temp_material_usda_path, "r+") as material_f:
                content = material_f.read()
                material_f.seek(0)
                content = content.replace("{OMNI_TEXTURE_PATH}", omni_texture_path.replace('\\', '/'))
                if material == "Backhead":
                    content = content.replace(
                        "{BACKHEAD_SPECULAR_PATH}",
                        additional_paths[CADefs.AdditionalElements.BackHeadTex]["texture_specular"].replace('\\', '/')
                    )
                    content = content.replace(
                        "{BACKHEAD_DIFFUSE_PATH}",
                        additional_paths[CADefs.AdditionalElements.BackHeadTex]["texture_diffuse"].replace('\\', '/')
                    )
                    content = content.replace(
                        "{BACKHEAD_NORMAL_PATH}",
                        additional_paths[CADefs.AdditionalElements.BackHeadTex]["texture_normal"].replace('\\', '/')
                    )
                elif material == "Face":
                    content = content.replace(
                        "{FACE_SPECULAR_PATH}",
                        texture_paths["texture_specular"].replace('\\', '/')
                    )
                    content = content.replace(
                        "{FACE_DIFFUSE_PATH}",
                        texture_paths["texture_diffuse"].replace('\\', '/')
                    )
                    content = content.replace(
                        "{FACE_NORMAL_PATH}",
                        texture_paths["texture_normal"].replace('\\', '/')
                    )
                material_f.write(content)
            
            temp_stage = Usd.Stage.Open(temp_material_usda_path)
            temp_stage.Export(material_usdc_path)

            if material == "Eye":
                left_eye_path = material_scope_prim_path.AppendChild("LeftEye")
                left_eye_mat_prim = main_stage.DefinePrim(left_eye_path, "Material")
                left_eye_mat_prim.GetReferences().AddReference(material_usdc_path, f"/Root/{material}")

                right_eye_path = material_scope_prim_path.AppendChild("RightEye")
                right_eye_mat_prim = main_stage.DefinePrim(right_eye_path, "Material")
                right_eye_mat_prim.GetReferences().AddReference(material_usdc_path, f"/Root/{material}")
                
                new_materials["Eye"] = {
                    "left": left_eye_mat_prim,
                    "right": right_eye_mat_prim,
                }
            else:
                material_path = material_scope_prim_path.AppendChild(material)
                material_prim = main_stage.DefinePrim(material_path, "Material")
                material_prim.GetReferences().AddReference(material_usdc_path, f"/Root/{material}")

                new_materials[material] = material_prim
    
    # For each material, find new material to apply
    for material_path, material_info in materials_new.items():
        target_material_key = determine_material_by_slot_name(
            material_path.name,
            selected_pack,
            selected_additional,
            available_additional,
            materials_need_to_apply
        )
        if target_material_key is None:
            continue
        elif target_material_key["variant"] is None:
            target_material_prim = new_materials[target_material_key["name"]]
        else:
            target_material_prim = new_materials[target_material_key["name"]][target_material_key["variant"]]
        for target_prim in material_info["users"]:
            material_binding_api = UsdShade.MaterialBindingAPI.Apply(target_prim)
            material_binding_api.Bind(UsdShade.Material(target_material_prim))
    
    set_subdiv_scheme_and_refinement(model_prim)

    main_stage.Save()

    # Import target
    context = omni.usd.get_context()
    context_stage = context.get_stage()
    context_import_prim = context_stage.DefinePrim(
        context_stage.GetDefaultPrim().GetPath().AppendChild(f"ChatAvatar_{import_unique_id}"),
        "Xform"
    )
    context_import_prim.GetReferences().AddReference(output_usd_path)

def gen_mtl_files(model_path):
    with open(model_path) as f:
        lines = f.readlines()
    current_mtllib = None
    mtllibs = {} # mtllib: [mtls]
    for line in lines:
        if line.startswith("mtllib"):
            current_mtllib = line.split()[1]
        if line.startswith("usemtl"):
            mtllibs.setdefault(current_mtllib, []).append(line.split()[1])
    new_mtl_files = []
    for mtllib, mtls in mtllibs.items():
        mtllib_full_path = os.path.join(os.path.dirname(model_path), mtllib)
        if os.path.exists(mtllib_full_path):
            continue
        new_mtl_files.append(mtllib_full_path)
        with open(mtllib_full_path, "w") as f:
            for mtl in mtls:
                print(f"newmtl {mtl}", file=f)
    return new_mtl_files

def material_usage_summary(parent_prim):
    results = {}
    for prim in Usd.PrimRange(parent_prim):
        binding = UsdShade.MaterialBindingAPI(prim).GetDirectBinding()
        bound_material_prim = binding.GetMaterial()
        if bound_material_prim:
            results.setdefault(bound_material_prim.GetPath(), {
                "material_prim": bound_material_prim,
                "users": []
            })["users"].append(prim)
    return results

def set_subdiv_scheme_and_refinement(parent_prim):
    for prim in Usd.PrimRange(parent_prim):
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            mesh.GetSubdivisionSchemeAttr().Set(UsdGeom.Tokens.catmullClark)
            prim.CreateAttribute("refinementEnableOverride", Sdf.ValueTypeNames.Bool).Set(True)
            prim.CreateAttribute("refinementLevel", Sdf.ValueTypeNames.Int, True).Set(2)

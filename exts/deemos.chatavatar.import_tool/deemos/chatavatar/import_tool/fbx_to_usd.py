# This conversion script are only intended to convert gltf generated from
# a modified version of fbx2gltf(https://github.com/godotengine/FBX2glTF) using
# fbx generated from ChatAvatar(https://hyperhuman.top/chatavatar).
# Not all transformations are replicated, and some are given in precise values
# that it should be.
# The modified version has a custom field "ORIGINAL_INDICES", having the vertex
# index in the original fbx

import os
import sys
import json
import base64
import numpy as np
from scipy.spatial.transform import Rotation as Rotation
from pxr import Usd, UsdGeom, UsdShade, Gf, UsdSkel, Sdf
import subprocess


# Constants
BUFFER_URI_PERFIX = "data:application/octet-stream;base64,"
COMPONENT_TYPE_SIZE = {
    5120: 1,  # GL_BYTE
    5121: 1,  # GL_UNSIGNED_BYTE
    5122: 2,  # GL_SHORT
    5123: 2,  # GL_UNSIGNED_SHORT
    5125: 4,  # GL_UNSIGNED_INT
    5126: 4   # GL_FLOAT
}
COMPONENT_TYPE_NP = {
    5120: np.int8,    # GL_BYTE
    5121: np.uint8,   # GL_UNSIGNED_BYTE
    5122: np.int16,   # GL_SHORT
    5123: np.uint16,  # GL_UNSIGNED_SHORT
    5125: np.uint32,  # GL_UNSIGNED_INT
    5126: np.float32  # GL_FLOAT
}
TYPE_ELEMENT_COUNT = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16
}
TYPE_ELEMENT_SHAPE = {
    "SCALAR": (1,),
    "VEC2": (2,),
    "VEC3": (3,),
    "VEC4": (4,),
    "MAT2": (2,2,),
    "MAT3": (3,3,),
    "MAT4": (4,4,),
}

def safe_usd_name(name):
    return name.replace(".", "_")

def read_gltf(in_file):
    # load gltf
    with open(in_file, "r") as f:
        content = json.load(f)

    buffers = []
    for buffer in content["buffers"]:
        assert buffer["uri"].startswith(BUFFER_URI_PERFIX)
        buf = base64.b64decode(buffer["uri"][len(BUFFER_URI_PERFIX):])
        assert len(buf) == buffer["byteLength"]
        buffers.append(buf)

    buffer_views = []
    for buffer_view in content["bufferViews"]:
        current_using_buffer = buffers[buffer_view["buffer"]]
        start = buffer_view["byteOffset"]
        end = buffer_view["byteOffset"] + buffer_view["byteLength"]
        buffer_views.append(
            current_using_buffer[start:end]
        )
    
    assert len(content["scenes"]) == 1

    accessors = []
    for accessor in content["accessors"]:
        accessor: dict
        item = {}
        item["name"] = accessor.get("name", "")
        component_per_element = TYPE_ELEMENT_COUNT[accessor["type"]]
        component_size = COMPONENT_TYPE_SIZE[accessor["componentType"]]
        element_count = accessor["count"]
        byte_offset = accessor.get("byteOffset", 0)
        byte_length = element_count * component_size * component_per_element
        assert len(buffer_views[accessor["bufferView"]]) >= byte_offset + byte_length
        data = np.frombuffer(buffer_views[accessor["bufferView"]][byte_offset:byte_offset + byte_length], COMPONENT_TYPE_NP[accessor["componentType"]])
        data = data.reshape((element_count, *TYPE_ELEMENT_SHAPE[accessor["type"]]))
        item["data"] = data
        accessors.append(item)

    materials = []
    for mat in content["materials"]:
        materials.append({
            "name": mat["name"],
        })
    
    nodes_parent = [*range(len(content["nodes"]))]
    # 1. Check tree structure (we will use a disjoint-set-like structure)
    for i, node in enumerate(content["nodes"]):
        if "children" in node:
            for j in node["children"]:
                assert nodes_parent[j] == j
                nodes_parent[j] = i
    nodes = content["nodes"]
    
    # Meshes
    meshes = content["meshes"]
    for mesh in content["meshes"]:
        for prim_index, primitive in enumerate(mesh["primitives"]):
            # Applying accessors
            for attr in primitive["attributes"]:
                primitive["attributes"][attr] = accessors[primitive["attributes"][attr]]["data"]
            primitive["indices"] = accessors[primitive["indices"]]["data"]
            primitive["faceindices"] = accessors[primitive["faceindices"]]["data"]

            for target in primitive.get("targets", []):
                for target_key in target:
                    target[target_key] = accessors[target[target_key]]["data"]
    
    # Skin
    skins = []
    if "skins" in content:
        skins = content["skins"]
        for skin in skins:
            if "inverseBindMatrices" in skin:
                skin["inverseBindMatrices"] = accessors[skin["inverseBindMatrices"]]["data"]
    
    for node in nodes:
        if "mesh" in node:
            node["mesh"] = meshes[node["mesh"]]
        if "skin" in node:
            node["skin"] = skins[node["skin"]]

    return {
        "materials": materials,
        "nodes_parent": nodes_parent,
        "nodes": nodes,
        "skins": skins
    }

def _merge_prim_arraies(arrays, indices_arraies, vertices_count):
    points = np.zeros((vertices_count, arrays[0].shape[1]))
    flags = np.zeros((vertices_count,), dtype=bool)
    for array, indices_array in zip(arrays, indices_arraies):
        for new_vertex_point, original_index in zip(array, indices_array):
            if flags[original_index] == 1:
                assert np.allclose(new_vertex_point, points[original_index])
            points[original_index] = new_vertex_point
            flags[original_index] = 1
    
    assert np.all(flags==1)
    return points

def _get_node_path(start_node_index, end_node_index, nodes, nodes_parent):
    path = []
    current_node_index = start_node_index
    while current_node_index != end_node_index:
        path.append(nodes[current_node_index]["name"])
        current_node_index = nodes_parent[current_node_index]
    path.append(nodes[current_node_index]["name"])
    
    return "/".join(reversed(path))

def _get_transform_from_node(node):
    translation = node.get("translation", np.array([0,0,0]))
    rotation = node.get("rotation", np.array([0,0,0,1]))
    scale = node.get("scale", np.array([1, 1, 1]))
    matrix = np.eye(4)
    matrix[:3, :3] = Rotation.from_quat(rotation).as_matrix() * scale
    matrix[:3, 3] = translation
    return matrix


def gen_usd(gltf_data, out_file):
    # write usd
    materials = gltf_data["materials"]
    nodes_parent = gltf_data["nodes_parent"]
    nodes = gltf_data["nodes"]
    skins = gltf_data["skins"]

    # Create a new stage
    stage = Usd.Stage.CreateNew(out_file)
    stage.SetMetadata('metersPerUnit', 0.01)
    stage.SetMetadata('upAxis', 'Y')

    root_prim = UsdGeom.Xform.Define(stage, '/root')
    stage.SetDefaultPrim(root_prim.GetPrim())

    # Add transformation operations to the root prim
    xform = UsdGeom.Xformable(root_prim)
    translate_op = xform.AddTranslateOp(UsdGeom.XformOp.PrecisionFloat)
    translate_op.Set(Gf.Vec3f(0, 0, 0))
    rotate_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionFloat)
    rotate_op.Set(Gf.Quatf(np.sqrt(2)/2, -np.sqrt(2)/2, 0.0, 0.0))
    scale_op = xform.AddXformOp(UsdGeom.XformOp.TypeScale, UsdGeom.XformOp.PrecisionFloat)
    scale_op.Set(Gf.Vec3f(100, 100, 100))

    # Find root node
    root_nodes = [node for i, node in enumerate(nodes) if nodes_parent[i] == i]
    assert len(root_nodes) == 1
    root_node = root_nodes.pop()
    # Create prim for root node
    stuffs_root_path = f'/root/{safe_usd_name(root_node["name"])}'
    skel_root = UsdSkel.Root.Define(stage, stuffs_root_path)
    xform = UsdGeom.Xformable(skel_root)
    translate_op = xform.AddTranslateOp(UsdGeom.XformOp.PrecisionFloat)
    translate_op.Set(Gf.Vec3f(0, 0, 0))
    rotate_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionFloat)
    rotate_op.Set(Gf.Quatf(1, 0, 0, 0))
    scale_op = xform.AddScaleOp(UsdGeom.XformOp.PrecisionFloat)
    scale_op.Set(Gf.Vec3f(1, 1, 1))
    
    # Create materials
    UsdGeom.Scope.Define(stage, '/root/Looks')
    usd_materials = []
    for mat in materials:
        mat_path = f'/root/Looks/{safe_usd_name(mat["name"])}'
        usd_materials.append(UsdShade.Material.Define(stage, mat_path))

    # Create mesh node
    mesh_nodes = [node for node in nodes if "mesh" in node]
    assert len(mesh_nodes) == 1
    mesh_node = mesh_nodes.pop()

    # The mesh
    mesh_prim_path = f'{stuffs_root_path}/{safe_usd_name(mesh_node["name"])}'
    mesh_prim = UsdGeom.Mesh.Define(stage, mesh_prim_path)
    UsdShade.MaterialBindingAPI.Apply(mesh_prim.GetPrim())
    UsdShade.MaterialBindingAPI(mesh_prim).SetMaterialBindSubsetsFamilyType('nonOverlapping')
    UsdSkel.BindingAPI.Apply(mesh_prim.GetPrim())

    xform = UsdGeom.Xformable(mesh_prim)
    translate_op = xform.AddTranslateOp(UsdGeom.XformOp.PrecisionFloat)
    translate_op.Set(Gf.Vec3f(0, 0, 0))
    rotate_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionFloat)
    rotate_op.Set(Gf.Quatf(np.sqrt(2)/2, np.sqrt(2)/2, 0.0, 0.0))
    scale_op = xform.AddScaleOp(UsdGeom.XformOp.PrecisionFloat)
    scale_op.Set(Gf.Vec3f(1, 1, 1))
    gltf_mesh_obj = mesh_node["mesh"]

    mesh_prim.CreateDoubleSidedAttr(True, False)

    vertices_count = 0
    faces_count = 0
    for mesh_gltf_prim in gltf_mesh_obj["primitives"]:
        vertices_count = max(np.max(mesh_gltf_prim["attributes"]["ORIGINAL_INDICES"])+1, vertices_count)
        faces_count = max(np.max(mesh_gltf_prim["faceindices"])+1, faces_count)
    
    points = _merge_prim_arraies(
        [prim["attributes"]["POSITION"] for prim in gltf_mesh_obj["primitives"]],
        [prim["attributes"]["ORIGINAL_INDICES"] for prim in gltf_mesh_obj["primitives"]],
        vertices_count
    )
    mesh_prim.CreatePointsAttr(points, False)
    
    face_vertex_counts = []
    face_vertex_indices = []
    texcoord = []
    triangle_collections = [[] for _ in range(faces_count)]
    for gltf_prim_index, mesh_gltf_prim in enumerate(gltf_mesh_obj["primitives"]):
        gltf_indices = mesh_gltf_prim["indices"]
        gltf_indices = gltf_indices.reshape(-1, 3)

        total_triangle_count = gltf_indices.shape[0]
        assert len(mesh_gltf_prim["faceindices"]) == total_triangle_count

        geom_subset_prim = UsdGeom.Subset.Define(stage, f'{mesh_prim_path}/{safe_usd_name(materials[mesh_gltf_prim["material"]]["name"])}')
        geom_subset_prim.CreateElementTypeAttr("face", False)
        geom_subset_prim.CreateIndicesAttr(mesh_gltf_prim["faceindices"].ravel().tolist(), False)
        geom_subset_prim.CreateFamilyNameAttr("materialBind", False)
        UsdShade.MaterialBindingAPI.Apply(geom_subset_prim.GetPrim())
        mat_prim = usd_materials[mesh_gltf_prim["material"]]
        UsdShade.MaterialBindingAPI(geom_subset_prim).Bind(mat_prim)

        for i, polygon_index in enumerate(mesh_gltf_prim["faceindices"].ravel()):
            triangle_collections[polygon_index].append({
                "prim_index": gltf_prim_index,
                "indices": gltf_indices[i].ravel().tolist(),
            })
    for triangle_collection in triangle_collections:
        assert 1 <= len(triangle_collection) <= 2
        if len(triangle_collection) == 1:
            prim_index = triangle_collection[0]["prim_index"]
            face_vertex_counts.append(3)
            face_vertex_indices.extend(gltf_mesh_obj["primitives"][prim_index]["attributes"]["ORIGINAL_INDICES"][triangle_collection[0]["indices"]].ravel().tolist())
            texcoord.extend(gltf_mesh_obj["primitives"][prim_index]["attributes"]["TEXCOORD_0"][triangle_collection[0]["indices"]].tolist())
        elif len(triangle_collection) == 2:
            prim_index = triangle_collection[0]["prim_index"]
            assert prim_index == triangle_collection[1]["prim_index"]
            face_vertex_counts.append(4)
            face_1, face_2 = triangle_collection
            face_1 = face_1["indices"]
            face_2 = face_2["indices"]

            face_1_ori = gltf_mesh_obj["primitives"][prim_index]["attributes"]["ORIGINAL_INDICES"][face_1].ravel().tolist()
            face_2_ori = gltf_mesh_obj["primitives"][prim_index]["attributes"]["ORIGINAL_INDICES"][face_2].ravel().tolist()

            assert len(set([*face_1_ori, *face_2_ori])) == 4
            if face_1_ori[1] == face_2_ori[2]:
                face_1, face_2 = face_2, face_1
                face_1_ori, face_2_ori = face_2_ori, face_1_ori
            face_vertex_indices.extend([*face_1_ori, face_2_ori[2]])

            texcoord.extend(gltf_mesh_obj["primitives"][prim_index]["attributes"]["TEXCOORD_0"][[*face_1, face_2[2]]].tolist())

    mesh_prim.CreateFaceVertexCountsAttr(face_vertex_counts, False)
    mesh_prim.CreateFaceVertexIndicesAttr(face_vertex_indices, False)
    UsdGeom.PrimvarsAPI(mesh_prim.GetPrim()).CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, "faceVarying", len(texcoord)).Set(texcoord)

    # Blendshapes
    if "weights" in gltf_mesh_obj:
        bs_length_sets = set([
            len(gltf_mesh_obj["weights"]),
            len(gltf_mesh_obj["extras"]["targetNames"]),
            *[
                len(prim["targets"]) for prim in gltf_mesh_obj["primitives"]
            ]
        ])
        assert len(bs_length_sets)== 1
        bs_length = bs_length_sets.pop()

        bs_prims = []
        bs_names = [safe_usd_name(i) for i in gltf_mesh_obj["extras"]["targetNames"]]
        UsdSkel.BindingAPI(mesh_prim).CreateBlendShapesAttr(bs_names)
        UsdSkel.BindingAPI(mesh_prim).CreateBlendShapeTargetsRel()
        bs_rel = []
        for i in range(bs_length):
            bs_points = _merge_prim_arraies(
                [prim["targets"][i]["POSITION"] for prim in gltf_mesh_obj["primitives"]],
                [prim["attributes"]["ORIGINAL_INDICES"] for prim in gltf_mesh_obj["primitives"]],
                vertices_count
            )
            bs_name = bs_names[i]
            bs_prim = UsdSkel.BlendShape.Define(stage, f'{mesh_prim_path}/{bs_name}')
            
            non_zero_vecs = np.any(bs_points != 0, axis=1)
            new_indices = np.where(non_zero_vecs)[0]
            new_offsets = bs_points[non_zero_vecs]

            bs_prim.CreateOffsetsAttr(new_offsets, False)
            bs_prim.CreatePointIndicesAttr(new_indices, False)
            bs_prims.append(bs_prim)
            bs_rel.append(bs_prim.GetPath())
        UsdSkel.BindingAPI(mesh_prim).GetBlendShapeTargetsRel().SetTargets(bs_rel)
    
    # Skeleton
    skin = None
    if "skin" in mesh_node:
        skin = mesh_node["skin"]
        root_joints = [
            joint for joint in skin["joints"]
            if nodes_parent[joint] not in skin["joints"]
        ]
        assert len(root_joints) == 1
        root_joint = root_joints.pop()
        assert len(nodes[nodes_parent[root_joint]]["children"]) == 1
        skel_prim_name = safe_usd_name(nodes[nodes_parent[root_joint]]["name"])
        skel_prim = UsdSkel.Skeleton.Define(stage, f"{stuffs_root_path}/{skel_prim_name}")
        UsdSkel.BindingAPI.Apply(skel_prim.GetPrim())
        
        bind_transforms = []
        rest_transforms = []
        joint_names = []
        for i, joint in enumerate(skin["joints"]):
            path = _get_node_path(joint, root_joint, nodes, nodes_parent)
            joint_names.append(path)
            coord_convert = np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]], dtype=float)
            bind_transform = np.linalg.inv(skin["inverseBindMatrices"][i]) @ coord_convert
            rest_transform = _get_transform_from_node(nodes[joint]) @ coord_convert
            bind_transforms.append(bind_transform)
            rest_transforms.append(rest_transform)
        skel_prim.CreateJointsAttr(joint_names, False)
        skel_prim.CreateBindTransformsAttr(np.array(bind_transforms), False)
        skel_prim.CreateRestTransformsAttr(np.array(bind_transforms), False)

        prims_joints, prims_weights = [], []
        element_sizes = []
        for mesh_gltf_prim in gltf_mesh_obj["primitives"]:
            joint_attributes, weight_attributes = [], []
            for attribute in mesh_gltf_prim["attributes"]:
                if attribute.startswith("JOINTS_"):
                    joint_attributes.append(attribute)
                elif attribute.startswith("WEIGHTS_"):
                    weight_attributes.append(attribute)
            element_size = len(joint_attributes)
            joint_attributes.sort(key=lambda x:int(x[len("JOINTS_"):]))
            weight_attributes.sort(key=lambda x:int(x[len("WEIGHTS_"):]))
            prim_joints = np.hstack([mesh_gltf_prim["attributes"][i] for i in joint_attributes])
            prim_weights = np.hstack([mesh_gltf_prim["attributes"][i] for i in weight_attributes])
            prims_joints.append(prim_joints)
            prims_weights.append(prim_weights)
            element_sizes.append(element_size)
        if len(set(element_sizes)) > 1:
            max_element_size = max(element_sizes)
            for i in range(len(prims_joints)):
                prims_joints[i] = np.pad(prims_joints[i], ((0,0), (0, max_element_size - element_sizes[i])))
                prims_weights[i] = np.pad(prims_weights[i], ((0,0), (0, max_element_size - element_sizes[i])))

        joints = _merge_prim_arraies(prims_joints, [prim["attributes"]["ORIGINAL_INDICES"] for prim in gltf_mesh_obj["primitives"]], vertices_count)
        weights = _merge_prim_arraies(prims_weights, [prim["attributes"]["ORIGINAL_INDICES"] for prim in gltf_mesh_obj["primitives"]], vertices_count)
        UsdSkel.BindingAPI(mesh_prim.GetPrim()).CreateJointIndicesPrimvar(False, element_size).Set(joints)
        UsdSkel.BindingAPI(mesh_prim.GetPrim()).CreateJointWeightsPrimvar(False, element_size).Set(weights)
        UsdSkel.BindingAPI(mesh_prim.GetPrim()).CreateSkeletonRel()
        UsdSkel.BindingAPI(mesh_prim.GetPrim()).GetSkeletonRel().SetTargets([skel_prim.GetPath()])

    # Save the stage to file
    stage.GetRootLayer().Save()

def gltf2usd(in_file, out_file):
    gen_usd(read_gltf(in_file), out_file)

def find_fbx2gltf_bin():
    binary_lookup = {
        "win32": os.path.join(os.path.dirname(__file__), "binaries", "win32", "FBX2glTF.exe"),
        "linux": os.path.join(os.path.dirname(__file__), "binaries", "linux", "FBX2glTF")
    }
    if sys.platform not in binary_lookup:
        raise OSError("Unsupported platform!")
    binary_path = binary_lookup[sys.platform]
    if sys.platform == "linux":
        os.chmod(binary_path, "0755")
    return binary_path


def fbx2gltf(in_file, out_file, bin_path=find_fbx2gltf_bin()):
    args = "-v --long-indices always --no-flip-u --no-flip-v --skinning-weights 512 --blend-shape-no-sparse -e".split()
    subprocess.run([
        os.path.abspath(bin_path), *args, "-i", in_file, "-o", out_file
    ])

if __name__ == "__main__":
    fbx_path = r"C:\Users\ericc\Desktop\ChatAvatarPlugins\Omniverse_ChatAvatar_Plugin\Assets\USD_Audio2FaceTest_20240514\additional_body.fbx"
    gltf_path = fbx_path.replace(".fbx", ".gltf")
    usda_path = r"C:\Users\ericc\Desktop\ChatAvatarPlugins\Omniverse_ChatAvatar_Plugin\Assets\USD_Audio2FaceTest_20240514\my_body.usda"
    sfbx2gltf(fbx_path, gltf_path)
    gltf2usd(gltf_path, usda_path)

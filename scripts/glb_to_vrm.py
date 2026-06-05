#!/usr/bin/env python3
"""Convert a rigged GLB to VRM 1.0 format.

VRM 1.0 is glTF 2.0 with these extensions:
- VRMC_vrm (metadata, expressions, humanoid, firstPerson, lookAt)

This script adds VRM 1.0 extension data to a rigged GLB file.
"""
import json
import struct
import sys
import os
import copy


def read_glb(filepath):
    """Read a GLB file and return header, JSON chunk, and binary chunk."""
    with open(filepath, "rb") as f:
        # GLB header: magic(4) + version(4) + length(4)
        magic = f.read(4)
        if magic != b"glTF":
            sys.exit(f"Not a valid GLB file: {filepath}")
        version = struct.unpack("<I", f.read(4))[0]
        total_length = struct.unpack("<I", f.read(4))[0]

        # Chunk 0: JSON
        chunk0_length = struct.unpack("<I", f.read(4))[0]
        chunk0_type = f.read(4)
        assert chunk0_type == b"JSON", f"Expected JSON chunk, got {chunk0_type}"
        json_data = f.read(chunk0_length)

        # Chunk 1: BIN (if exists)
        bin_data = b""
        remaining = total_length - 12 - 8 - chunk0_length
        if remaining > 0:
            chunk1_length = struct.unpack("<I", f.read(4))[0]
            chunk1_type = f.read(4)
            assert chunk1_type == b"BIN\x00", f"Expected BIN chunk, got {chunk1_type}"
            bin_data = f.read(chunk1_length)

    gltf = json.loads(json_data.decode("utf-8"))
    return version, gltf, bin_data


def write_glb(filepath, gltf, bin_data):
    """Write a GLB file from glTF JSON and binary data."""
    json_str = json.dumps(gltf, ensure_ascii=False, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")
    # Pad JSON to 4-byte boundary with spaces
    json_pad = (4 - len(json_bytes) % 4) % 4
    json_bytes += b" " * json_pad
    # Pad BIN to 4-byte boundary with zeros
    bin_pad = (4 - len(bin_data) % 4) % 4
    bin_data += b"\x00" * bin_pad

    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)

    with open(filepath, "wb") as f:
        # Header
        f.write(b"glTF")
        f.write(struct.pack("<I", 2))  # version
        f.write(struct.pack("<I", total_length))
        # JSON chunk
        f.write(struct.pack("<I", len(json_bytes)))
        f.write(b"JSON")
        f.write(json_bytes)
        # BIN chunk
        f.write(struct.pack("<I", len(bin_data)))
        f.write(b"BIN\x00")
        f.write(bin_data)


def find_bone_node(gltf, bone_name_candidates):
    """Find a node index by bone name (case-insensitive, multiple candidates)."""
    nodes = gltf.get("nodes", [])
    for i, node in enumerate(nodes):
        name = (node.get("name") or "").lower()
        for candidate in bone_name_candidates:
            if candidate.lower() in name:
                return i
    return None


# VRM 1.0 humanoid bone mapping: vrm_bone_name -> search terms in GLB node names
HUMANOID_BONE_MAP = {
    "hips": ["hips", "hip", "pelvis"],
    "spine": ["spine", "spine1"],
    "chest": ["chest", "spine2"],
    "upperChest": ["upperchest", "spine3", "upper_chest"],
    "neck": ["neck"],
    "head": ["head"],
    "leftUpperArm": ["leftshoulder", "left_shoulder", "l_shoulder", "leftupperarm", "left_upper_arm", "l_upperarm"],
    "leftLowerArm": ["leftforearm", "left_forearm", "leftlowerarm", "left_lower_arm", "l_forearm", "l_lowerarm"],
    "leftHand": ["lefthand", "left_hand", "l_hand"],
    "rightUpperArm": ["rightshoulder", "right_shoulder", "r_shoulder", "rightupperarm", "right_upper_arm", "r_upperarm"],
    "rightLowerArm": ["rightforearm", "right_forearm", "rightlowerarm", "right_lower_arm", "r_forearm", "r_lowerarm"],
    "rightHand": ["righthand", "right_hand", "r_hand"],
    "leftUpperLeg": ["leftupleg", "left_upleg", "leftupperleg", "left_upper_leg", "l_upperleg"],
    "leftLowerLeg": ["leftleg", "left_leg", "leftlowerleg", "left_lower_leg", "l_lowerleg"],
    "leftFoot": ["leftfoot", "left_foot", "l_foot"],
    "rightUpperLeg": ["rightupleg", "right_upleg", "rightupperleg", "right_upper_leg", "r_upperleg"],
    "rightLowerLeg": ["rightleg", "right_leg", "rightlowerleg", "right_lower_leg", "r_lowerleg"],
    "rightFoot": ["rightfoot", "right_foot", "r_foot"],
}


def build_humanoid(gltf):
    """Build VRMC_vrm humanoid bone mapping from GLB nodes."""
    human_bones = {}
    nodes = gltf.get("nodes", [])

    # First pass: try exact matching with bone map
    for vrm_bone, candidates in HUMANOID_BONE_MAP.items():
        idx = find_bone_node(gltf, candidates)
        if idx is not None:
            human_bones[vrm_bone] = {"node": idx}

    # Second pass: exact name matching (Mixamo / Meshy conventions)
    exact_map = {
        "hips": ["mixamorig:Hips", "Hips"],
        "spine": ["mixamorig:Spine", "Spine"],
        "chest": ["mixamorig:Spine1", "Spine1", "Spine01"],
        "upperChest": ["mixamorig:Spine2", "Spine2", "Spine02"],
        "neck": ["mixamorig:Neck", "Neck", "neck"],
        "head": ["mixamorig:Head", "Head"],
        "leftShoulder": ["mixamorig:LeftShoulder", "LeftShoulder"],
        "leftUpperArm": ["mixamorig:LeftArm", "LeftArm"],
        "leftLowerArm": ["mixamorig:LeftForeArm", "LeftForeArm"],
        "leftHand": ["mixamorig:LeftHand", "LeftHand"],
        "rightShoulder": ["mixamorig:RightShoulder", "RightShoulder"],
        "rightUpperArm": ["mixamorig:RightArm", "RightArm"],
        "rightLowerArm": ["mixamorig:RightForeArm", "RightForeArm"],
        "rightHand": ["mixamorig:RightHand", "RightHand"],
        "leftUpperLeg": ["mixamorig:LeftUpLeg", "LeftUpLeg"],
        "leftLowerLeg": ["mixamorig:LeftLeg", "LeftLeg"],
        "leftFoot": ["mixamorig:LeftFoot", "LeftFoot"],
        "leftToes": ["mixamorig:LeftToeBase", "LeftToeBase"],
        "rightUpperLeg": ["mixamorig:RightUpLeg", "RightUpLeg"],
        "rightLowerLeg": ["mixamorig:RightLeg", "RightLeg"],
        "rightFoot": ["mixamorig:RightFoot", "RightFoot"],
        "rightToes": ["mixamorig:RightToeBase", "RightToeBase"],
    }
    for vrm_bone, candidates in exact_map.items():
        if vrm_bone not in human_bones:
            for i, node in enumerate(nodes):
                if node.get("name") in candidates:
                    human_bones[vrm_bone] = {"node": i}
                    break

    return human_bones


def add_vrm_extensions(gltf):
    """Add VRM 1.0 extensions to glTF data."""
    # Ensure extensionsUsed
    if "extensionsUsed" not in gltf:
        gltf["extensionsUsed"] = []
    if "VRMC_vrm" not in gltf["extensionsUsed"]:
        gltf["extensionsUsed"].append("VRMC_vrm")

    # Build humanoid mapping
    human_bones = build_humanoid(gltf)
    print(f"  Mapped {len(human_bones)} humanoid bones: {', '.join(sorted(human_bones.keys()))}")

    required_bones = ["hips", "spine", "head", "leftUpperArm", "rightUpperArm",
                      "leftUpperLeg", "rightUpperLeg"]
    missing = [b for b in required_bones if b not in human_bones]
    if missing:
        print(f"  WARNING: Missing required bones: {missing}")
        print(f"  Available nodes: {[n.get('name') for n in gltf.get('nodes', [])]}")

    # VRM 1.0 extension
    vrm_ext = {
        "specVersion": "1.0",
        "meta": {
            "name": "Iris - SmartIR AI Financial Analyst",
            "version": "1.0",
            "authors": ["SmartIR Project"],
            "contactInformation": "",
            "references": [],
            "thirdPartyLicenses": "",
            "thumbnailImage": None,
            "licenseUrl": "https://vrm.dev/licenses/1.0/",
            "avatarPermission": "onlyAuthor",
            "allowExcessivelyViolentUsage": False,
            "allowExcessivelySexualUsage": False,
            "commercialUsage": "personalProfit",
            "allowPoliticalOrReligiousUsage": False,
            "allowAntisocialOrHateUsage": False,
            "creditNotation": "required",
            "allowRedistribution": False,
            "modification": "allowModification",
        },
        "humanoid": {
            "humanBones": human_bones,
        },
        "firstPerson": {
            "meshAnnotations": [],
        },
        "lookAt": {
            "type": "bone",
            "offsetFromHeadBone": [0, 0.06, 0],
            "rangeMapHorizontalInner": {"inputMaxValue": 90, "outputScale": 10},
            "rangeMapHorizontalOuter": {"inputMaxValue": 90, "outputScale": 10},
            "rangeMapVerticalDown": {"inputMaxValue": 90, "outputScale": 10},
            "rangeMapVerticalUp": {"inputMaxValue": 90, "outputScale": 10},
        },
        "expressions": {
            "preset": {
                "happy": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "angry": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "sad": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "surprised": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "neutral": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "blink": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "aa": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "ih": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "ou": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "ee": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
                "oh": {"morphTargetBinds": [], "materialColorBinds": [], "textureTransformBinds": []},
            },
            "custom": {},
        },
    }

    # Add to glTF extensions
    if "extensions" not in gltf:
        gltf["extensions"] = {}
    gltf["extensions"]["VRMC_vrm"] = vrm_ext

    return gltf


def main():
    if len(sys.argv) < 2:
        print("Usage: glb_to_vrm.py <input.glb> [output.vrm]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace(".glb", ".vrm")

    print(f"Converting {input_path} → {output_path}")

    version, gltf, bin_data = read_glb(input_path)
    print(f"  glTF version: {version}")
    print(f"  Nodes: {len(gltf.get('nodes', []))}")
    print(f"  Meshes: {len(gltf.get('meshes', []))}")

    gltf = add_vrm_extensions(gltf)
    write_glb(output_path, gltf, bin_data)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nDone! Output: {output_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()

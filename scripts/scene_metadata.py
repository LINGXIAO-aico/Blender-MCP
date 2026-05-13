import argparse
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


DEFAULT_ROOT = Path(os.environ.get("BLENDER_VLM_ROOT", r"E:\blender"))


def parse_args():
    argv = sys.argv
    script_args = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Export scene metadata for VLM evaluation.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--scene-name", default="")
    return parser.parse_args(script_args)


def safe_name(name):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name).strip("_") or "scene"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def list_vec(value):
    return [float(v) for v in value]


def world_bbox(obj):
    if obj.type not in {"MESH", "CURVE", "FONT", "SURFACE", "META"}:
        return None
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_v = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    max_v = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return {
        "min": list_vec(min_v),
        "max": list_vec(max_v),
        "center": list_vec((min_v + max_v) * 0.5),
        "size": list_vec(max_v - min_v),
    }


def material_names(obj):
    data = getattr(obj, "data", None)
    if data is None or not hasattr(data, "materials"):
        return []
    return [mat.name if mat else None for mat in data.materials]


def serialize_object(obj):
    return {
        "name": obj.name,
        "type": obj.type,
        "location": list_vec(obj.location),
        "rotation_euler": list_vec(obj.rotation_euler),
        "scale": list_vec(obj.scale),
        "dimensions": list_vec(obj.dimensions),
        "bounding_box": world_bbox(obj),
        "material_names": material_names(obj),
        "visible": bool(obj.visible_get()),
        "selected": bool(obj.select_get()),
    }


def serialize_camera(obj):
    data = obj.data
    return {
        "name": obj.name,
        "location": list_vec(obj.location),
        "rotation_euler": list_vec(obj.rotation_euler),
        "type": data.type,
        "lens": float(data.lens),
        "ortho_scale": float(data.ortho_scale),
        "clip_start": float(data.clip_start),
        "clip_end": float(data.clip_end),
        "dof": {
            "use_dof": bool(data.dof.use_dof),
            "focus_distance": float(data.dof.focus_distance),
            "aperture_fstop": float(data.dof.aperture_fstop),
        },
    }


def serialize_light(obj):
    data = obj.data
    payload = {
        "name": obj.name,
        "type": data.type,
        "location": list_vec(obj.location),
        "rotation_euler": list_vec(obj.rotation_euler),
        "energy": float(data.energy),
        "color": list_vec(data.color),
    }
    if hasattr(data, "size"):
        payload["size"] = float(data.size)
    if hasattr(data, "size_y"):
        payload["size_y"] = float(data.size_y)
    return payload


def export_metadata(root, scene_name):
    scene = bpy.context.scene
    scene_name = scene_name or safe_name(scene.name)
    output_dir = Path(root) / "metadata"
    ensure_dir(output_dir)
    output_path = output_dir / f"{scene_name}.json"

    cameras = [serialize_camera(obj) for obj in bpy.data.objects if obj.type == "CAMERA"]
    lights = [serialize_light(obj) for obj in bpy.data.objects if obj.type == "LIGHT"]
    objects = [serialize_object(obj) for obj in bpy.data.objects]
    active_camera = scene.camera.name if scene.camera else None

    payload = {
        "scene_name": scene_name,
        "filepath": bpy.data.filepath,
        "active_camera": active_camera,
        "render": {
            "engine": scene.render.engine,
            "resolution_x": int(scene.render.resolution_x),
            "resolution_y": int(scene.render.resolution_y),
            "filepath": scene.render.filepath,
        },
        "color_management": {
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "exposure": float(scene.view_settings.exposure),
            "gamma": float(scene.view_settings.gamma),
        },
        "objects": objects,
        "cameras": cameras,
        "lights": lights,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result_payload = {
        "scene_name": scene_name,
        "metadata_path": str(output_path),
        "object_count": len(objects),
        "camera_count": len(cameras),
        "light_count": len(lights),
    }
    globals()["result"] = result_payload
    return result_payload


def main():
    args = parse_args()
    output = export_metadata(Path(args.root), args.scene_name)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

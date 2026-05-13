import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


DEFAULT_ROOT = Path(os.environ.get("BLENDER_VLM_ROOT", r"E:\blender"))
VIEWS = ("camera", "front", "side", "top", "back")


def parse_args():
    argv = sys.argv
    script_args = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Render camera/front/side/top/back views.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--scene-name", default="")
    parser.add_argument("--resolution", type=int, default=768)
    parser.add_argument("--samples", type=int, default=32)
    return parser.parse_args(script_args)


def safe_name(name):
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name).strip("_") or "scene"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def object_world_bbox(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return corners


def scene_bbox():
    mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.visible_get()]
    if not mesh_objects:
        return Vector((-1, -1, -1)), Vector((1, 1, 1))
    corners = []
    for obj in mesh_objects:
        corners.extend(object_world_bbox(obj))
    min_v = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    max_v = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return min_v, max_v


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_view_camera(name, view, center, extent):
    max_extent = max(extent.x, extent.y, extent.z, 1.0)
    distance = max_extent * 2.8
    locations = {
        "front": center + Vector((0.0, -distance, extent.z * 0.35)),
        "back": center + Vector((0.0, distance, extent.z * 0.35)),
        "side": center + Vector((distance, 0.0, extent.z * 0.35)),
        "top": center + Vector((0.0, 0.0, distance)),
    }
    bpy.ops.object.camera_add(location=locations[view])
    camera = bpy.context.active_object
    camera.name = name
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(extent.x, extent.y, extent.z) * 1.55
    look_at(camera, center)
    return camera


def configure_render(resolution, samples):
    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
    elif hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = samples


def render_views(root, scene_name, resolution, samples):
    scene = bpy.context.scene
    scene_name = scene_name or safe_name(scene.name)
    output_dir = Path(root) / "renders" / scene_name
    ensure_dir(output_dir)
    configure_render(resolution, samples)

    min_v, max_v = scene_bbox()
    center = (min_v + max_v) * 0.5
    extent = max_v - min_v
    original_camera = scene.camera
    temp_cameras = []
    rendered = {}

    for view in VIEWS:
        if view == "camera":
            camera = original_camera
            if camera is None:
                camera = make_view_camera("auto_camera_view", "front", center, extent)
                temp_cameras.append(camera)
        else:
            camera = make_view_camera(f"temp_{view}_camera", view, center, extent)
            temp_cameras.append(camera)
        scene.camera = camera
        path = output_dir / f"{view}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        rendered[view] = str(path)

    scene.camera = original_camera
    for camera in temp_cameras:
        bpy.data.objects.remove(camera, do_unlink=True)

    result_payload = {
        "scene_name": scene_name,
        "output_dir": str(output_dir),
        "views": rendered,
    }
    globals()["result"] = result_payload
    return result_payload


def main():
    args = parse_args()
    output = render_views(Path(args.root), args.scene_name, args.resolution, args.samples)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

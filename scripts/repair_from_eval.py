import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


DEFAULT_ROOT = Path(os.environ.get("BLENDER_VLM_ROOT", r"E:\blender"))


def parse_args():
    argv = sys.argv
    script_args = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Repair the current Blender scene from VLM eval JSON.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--eval-result", default="")
    parser.add_argument("--output", default="")
    return parser.parse_args(script_args)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def find_node(node_tree, *, node_type=None, bl_idname=None):
    for node in node_tree.nodes:
        if bl_idname and node.bl_idname == bl_idname:
            return node
        if node_type and node.type == node_type:
            return node
    return None


def make_material(name, rgba, roughness=0.42, metallic=0.0):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.use_nodes = True
    principled = find_node(
        material.node_tree,
        node_type="BSDF_PRINCIPLED",
        bl_idname="ShaderNodeBsdfPrincipled",
    )
    if principled is not None:
        principled.inputs["Base Color"].default_value = rgba
        principled.inputs["Roughness"].default_value = roughness
        principled.inputs["Metallic"].default_value = metallic
    return material


def world_bbox(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    min_v = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    max_v = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return min_v, max_v


def find_object(*candidates):
    lowered = [candidate.lower() for candidate in candidates if candidate]
    for obj in bpy.data.objects:
        name = obj.name.lower()
        if any(candidate in name for candidate in lowered):
            return obj
    return None


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def issue_types(eval_payload):
    values = []
    for issue in eval_payload.get("detected_issues", []):
        issue_type = issue.get("type")
        if issue_type and issue_type not in values:
            values.append(issue_type)
    return values


def align_cup_to_table():
    cup = find_object("ceramic_cup")
    table = find_object("wooden_table")
    if cup is None or table is None:
        return {"status": "skipped", "reason": "ceramic_cup or wooden_table not found"}
    cup_min, _cup_max = world_bbox(cup)
    _table_min, table_max = world_bbox(table)
    dz = table_max.z - cup_min.z
    cup.location.z += dz
    handle = find_object("ceramic_cup_handle")
    if handle is not None:
        handle.location.z += dz
    return {"status": "ok", "z_delta": float(dz), "table_top_z": float(table_max.z)}


def repair_floating_object(_eval_payload):
    return align_cup_to_table()


def repair_object_penetration(_eval_payload):
    return align_cup_to_table()


def repair_underexposed(_eval_payload):
    light = find_object("area_key_light")
    if light is None or light.type != "LIGHT":
        bpy.ops.object.light_add(type="AREA", location=(0.0, -1.2, 3.0))
        light = bpy.context.active_object
        light.name = "area_key_light"
    light.data.type = "AREA"
    light.data.energy = max(float(light.data.energy), 520.0)
    light.data.size = max(float(getattr(light.data, "size", 0.0)), 4.0)
    light.data.color = (1.0, 0.98, 0.94)
    bpy.context.scene.view_settings.exposure = 0.0
    bpy.context.scene.view_settings.gamma = 1.0
    return {"status": "ok", "energy": float(light.data.energy)}


def repair_overexposed(_eval_payload):
    light = find_object("area_key_light")
    if light is not None and light.type == "LIGHT":
        light.data.energy = min(float(light.data.energy), 420.0)
    bpy.context.scene.view_settings.exposure = min(float(bpy.context.scene.view_settings.exposure), 0.0)
    return {"status": "ok", "energy": float(light.data.energy) if light else None}


def repair_missing_material(_eval_payload):
    ceramic = make_material("white_ceramic_material", (0.95, 0.92, 0.86, 1.0), roughness=0.32)
    repaired = []
    for obj in bpy.data.objects:
        if "ceramic_cup" in obj.name.lower() and hasattr(obj.data, "materials"):
            obj.data.materials.clear()
            obj.data.materials.append(ceramic)
            repaired.append(obj.name)
    return {"status": "ok", "objects": repaired}


def repair_camera_bad_framing(_eval_payload):
    cup = find_object("ceramic_cup")
    table = find_object("wooden_table")
    camera = bpy.context.scene.camera or find_object("camera")
    if camera is None:
        bpy.ops.object.camera_add()
        camera = bpy.context.active_object
        camera.name = "Camera"
        bpy.context.scene.camera = camera
    if cup is None and table is None:
        return {"status": "skipped", "reason": "no cup/table target found"}

    boxes = [world_bbox(obj) for obj in (cup, table) if obj is not None]
    min_v = Vector((min(box[0].x for box in boxes), min(box[0].y for box in boxes), min(box[0].z for box in boxes)))
    max_v = Vector((max(box[1].x for box in boxes), max(box[1].y for box in boxes), max(box[1].z for box in boxes)))
    center = (min_v + max_v) * 0.5
    extent = max_v - min_v
    camera.location = center + Vector((2.7, -3.8, max(1.6, extent.z * 1.2)))
    camera.data.lens = 50.0
    camera.data.clip_start = 0.05
    camera.data.clip_end = 100.0
    look_at(camera, center + Vector((0.0, 0.0, 0.1)))
    bpy.context.scene.camera = camera
    return {"status": "ok", "camera_location": [float(v) for v in camera.location]}


REPAIRERS = {
    "floating_object": repair_floating_object,
    "object_penetration": repair_object_penetration,
    "underexposed": repair_underexposed,
    "overexposed": repair_overexposed,
    "missing_material": repair_missing_material,
    "camera_bad_framing": repair_camera_bad_framing,
    "camera_missing_subject": repair_camera_bad_framing,
}


def repair_from_eval(eval_path, output_path):
    eval_payload = json.loads(Path(eval_path).read_text(encoding="utf-8"))
    applied = {}
    for issue_type in issue_types(eval_payload):
        repairer = REPAIRERS.get(issue_type)
        if repairer is None:
            applied[issue_type] = {
                "status": "todo",
                "todo": "Add a repair function using bpy object transforms, materials, lights, or camera APIs.",
            }
            continue
        applied[issue_type] = repairer(eval_payload)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = max(int(scene.cycles.samples), 64)
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"

    ensure_dir(Path(output_path).parent)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    result_payload = {
        "eval_path": str(eval_path),
        "output_path": str(output_path),
        "applied_repairs": applied,
        "objects": [obj.name for obj in bpy.data.objects],
    }
    globals()["result"] = result_payload
    return result_payload


def main():
    args = parse_args()
    root = Path(args.root)
    eval_path = Path(args.eval_result) if args.eval_result else root / "logs" / "eval_result.json"
    output_path = Path(args.output) if args.output else root / "blends" / "repaired_cup_scene.blend"
    output = repair_from_eval(eval_path, output_path)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


DEFAULT_ROOT = Path(os.environ.get("BLENDER_VLM_ROOT", r"E:\blender"))
TARGET_DESCRIPTION = (
    "A ceramic cup should be placed on a wooden table under balanced studio "
    "lighting. The cup should be clearly visible in the camera view."
)


def parse_args():
    argv = sys.argv
    script_args = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description="Create an intentionally flawed cup scene.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--scene-name", default="bad_cup_scene")
    return parser.parse_args(script_args)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for data_blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
        for block in list(data_blocks):
            if block.users == 0:
                data_blocks.remove(block)


def find_node(node_tree, *, node_type=None, bl_idname=None):
    for node in node_tree.nodes:
        if bl_idname and node.bl_idname == bl_idname:
            return node
        if node_type and node.type == node_type:
            return node
    return None


def make_material(name, rgba, roughness=0.55, metallic=0.0):
    material = bpy.data.materials.new(name)
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


def assign_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def shade_smooth(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def add_box(name, location, scale, material):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    assign_material(obj, material)
    return obj


def add_cylinder(name, radius, depth, location, material):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth, location=location)
    obj = bpy.context.active_object
    obj.name = name
    assign_material(obj, material)
    shade_smooth(obj)
    return obj


def add_torus(name, location, rotation, major_radius, minor_radius, material):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=96,
        minor_segments=16,
        major_radius=major_radius,
        minor_radius=minor_radius,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = name
    assign_material(obj, material)
    shade_smooth(obj)
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build_bad_scene(root, scene_name):
    reset_scene()
    scene = bpy.context.scene
    scene.name = scene_name

    wood = make_material("wood_table_material", (0.55, 0.34, 0.18, 1.0), roughness=0.62)
    default_gray = make_material("default_gray_cup_material", (0.48, 0.48, 0.48, 1.0), roughness=0.5)
    dark_floor = make_material("matte_dark_floor", (0.09, 0.09, 0.09, 1.0), roughness=0.85)

    add_box("studio_floor", (0.0, 0.0, -0.035), (3.5, 3.5, 0.035), dark_floor)

    table_height = 0.75
    top_thickness = 0.10
    top_center_z = table_height
    table_top = add_box(
        "wooden_table",
        (0.0, 0.0, top_center_z),
        (1.25, 0.75, top_thickness / 2.0),
        wood,
    )
    leg_height = table_height - top_thickness / 2.0
    for index, (x, y) in enumerate(((-1.05, -0.55), (1.05, -0.55), (-1.05, 0.55), (1.05, 0.55)), 1):
        add_box(f"wooden_table_leg_{index}", (x, y, leg_height / 2.0), (0.07, 0.07, leg_height / 2.0), wood)

    # Intentionally wrong: the cup bottom floats far above the tabletop.
    cup_height = 0.55
    cup_radius = 0.23
    cup_center_z = 1.42
    cup = add_cylinder("ceramic_cup", cup_radius, cup_height, (0.0, 0.0, cup_center_z), default_gray)
    add_torus(
        "ceramic_cup_handle",
        (cup_radius + 0.04, -0.02, cup_center_z),
        (math.radians(90.0), 0.0, 0.0),
        0.15,
        0.025,
        default_gray,
    )

    # Intentionally wrong: balanced studio lighting is requested, but the area light is very dim.
    bpy.ops.object.light_add(type="AREA", location=(0.0, -1.2, 3.0))
    light = bpy.context.active_object
    light.name = "area_key_light"
    light.data.energy = 18.0
    light.data.size = 3.5
    light.data.color = (1.0, 0.97, 0.92)

    # Intentionally wrong: the camera looks away from the table/cup subject.
    bpy.ops.object.camera_add(location=(-3.2, -4.0, 2.0))
    camera = bpy.context.active_object
    camera.name = "Camera"
    camera.data.lens = 55.0
    look_at(camera, (2.4, 0.95, 0.7))
    scene.camera = camera

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 960
    scene.render.resolution_y = 960
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = -1.2
    scene.view_settings.gamma = 1.0

    blends_dir = Path(root) / "blends"
    ensure_dir(blends_dir)
    blend_path = blends_dir / f"{scene_name}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    return {
        "scene_name": scene_name,
        "target_description": TARGET_DESCRIPTION,
        "blend_path": str(blend_path),
        "intentional_errors": [
            "floating_object",
            "underexposed",
            "missing_material",
            "camera_bad_framing",
        ],
        "objects": [obj.name for obj in bpy.data.objects],
        "cup_location": list(cup.location),
        "table_location": list(table_top.location),
        "area_light_energy": light.data.energy,
    }


def main():
    args = parse_args()
    output = build_bad_scene(Path(args.root), args.scene_name)
    globals()["result"] = output
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

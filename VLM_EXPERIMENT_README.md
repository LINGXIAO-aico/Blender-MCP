# Blender MCP VLM Scene Quality Demo

This repository contains a minimal reproducible demo for a VLM-style 3D scene
quality assessment and repair loop in Blender.

## Goal

Target scene:

```text
A ceramic cup should be placed on a wooden table under balanced studio lighting.
The cup should be clearly visible in the camera view.
```

The first scene intentionally contains four defects:

- `floating_object`: the cup floats above the tabletop.
- `underexposed`: the area light is too dim and exposure is low.
- `missing_material`: the cup uses a default gray material instead of ceramic.
- `camera_bad_framing`: the camera is not well framed around the cup and table.

The loop is:

```text
create bad scene
-> render camera/front/side/top/back views
-> export scene metadata
-> VLM-style JSON evaluation
-> repair current Blender MCP scene
-> re-render and re-score
```

## Key Files

- `reports/vlm_blender_scene_quality_experiment_report.docx`: final experiment report.
- `scripts/create_bad_cup_scene_mcp.py`: creates the intentionally flawed Blender scene.
- `scripts/render_multiview.py`: renders camera, front, side, top, and back views.
- `scripts/scene_metadata.py`: exports object, camera, light, bounding-box, and material metadata.
- `scripts/prepare_evaluation_input.py`: writes the VLM evaluation input manifest.
- `scripts/repair_from_eval.py`: repairs the current Blender scene from `logs/eval_result.json`.
- `scripts/run_script_via_mcp.py`: sends a local Blender Python script into the active MCP session.
- `scripts/build_vlm_experiment_report.py`: builds the DOCX report from renders and JSON logs.
- `vlm_eval_prompt.md`: strict JSON prompt used for VLM-style evaluation.

## Artifacts

- `renders/bad_cup_scene/`: five rendered views before repair.
- `renders/repaired_cup_scene/`: five rendered views after repair.
- `metadata/bad_cup_scene.json`: scene metadata before repair.
- `metadata/repaired_cup_scene.json`: scene metadata after repair.
- `logs/eval_result.json`: before-repair VLM-style diagnosis.
- `logs/eval_result_after_repair.json`: after-repair VLM-style diagnosis.
- `blends/bad_cup_scene.blend`: saved intentionally flawed scene.
- `blends/repaired_cup_scene.blend`: saved repaired scene.

## Reproduce With Current Blender MCP Session

Assume Blender has the official MCP bridge enabled and listening locally.

```powershell
E:\blender\.venv-mcp\Scripts\python.exe E:\blender\scripts\run_script_via_mcp.py E:\blender\scripts\create_bad_cup_scene_mcp.py -- --root E:\blender --scene-name bad_cup_scene

E:\blender\.venv-mcp\Scripts\python.exe E:\blender\scripts\run_script_via_mcp.py E:\blender\scripts\render_multiview.py -- --root E:\blender --scene-name bad_cup_scene --resolution 768 --samples 32

E:\blender\.venv-mcp\Scripts\python.exe E:\blender\scripts\run_script_via_mcp.py E:\blender\scripts\scene_metadata.py -- --root E:\blender --scene-name bad_cup_scene

python E:\blender\scripts\prepare_evaluation_input.py --root E:\blender --scene-name bad_cup_scene

E:\blender\.venv-mcp\Scripts\python.exe E:\blender\scripts\run_script_via_mcp.py E:\blender\scripts\repair_from_eval.py -- --root E:\blender --eval-result E:\blender\logs\eval_result.json --output E:\blender\blends\repaired_cup_scene.blend
```

After repair, render and export metadata again with `scene-name repaired_cup_scene`.

## Current Result

The demo score improved from `42/100` before repair to `90/100` after repair.

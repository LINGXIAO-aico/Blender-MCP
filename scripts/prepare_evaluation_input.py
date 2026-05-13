import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TARGET_DESCRIPTION = (
    "A ceramic cup should be placed on a wooden table under balanced studio "
    "lighting. The cup should be clearly visible in the camera view."
)
VIEWS = ("camera", "front", "side", "top", "back")


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare VLM evaluation input markdown.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--scene-name", default="bad_cup_scene")
    parser.add_argument("--target-description", default=TARGET_DESCRIPTION)
    return parser.parse_args()


def ensure_dir(path):
    path.mkdir(parents=True, exist_ok=True)


def build_eval_template():
    return {
        "total_score": 0,
        "geometry_score": 0,
        "layout_score": 0,
        "material_score": 0,
        "lighting_score": 0,
        "camera_score": 0,
        "alignment_score": 0,
        "overall_quality_level": "bad",
        "detected_issues": [],
        "repair_suggestions": [],
        "summary": "",
    }


def main():
    args = parse_args()
    root = Path(args.root)
    scene_name = args.scene_name
    logs_dir = root / "logs"
    ensure_dir(logs_dir)

    render_dir = root / "renders" / scene_name
    metadata_path = root / "metadata" / f"{scene_name}.json"
    prompt_path = root / "vlm_eval_prompt.md"
    eval_input_path = logs_dir / "evaluation_input.md"
    eval_result_path = logs_dir / "eval_result.json"

    view_lines = []
    for view in VIEWS:
        image_path = render_dir / f"{view}.png"
        status = "exists" if image_path.is_file() else "missing"
        view_lines.append(f"- {view}: `{image_path}` ({status})")

    content = "\n".join(
        [
            "# VLM Evaluation Input",
            "",
            "## Target Description",
            "",
            args.target_description,
            "",
            "## Multi-view Render Paths",
            "",
            *view_lines,
            "",
            "## Metadata",
            "",
            f"- metadata: `{metadata_path}`",
            "",
            "## VLM Prompt",
            "",
            f"- prompt: `{prompt_path}`",
            "",
            "## Output",
            "",
            f"Paste or write the strict JSON VLM result to `{eval_result_path}`.",
            "",
        ]
    )
    eval_input_path.write_text(content, encoding="utf-8")
    if not eval_result_path.exists():
        eval_result_path.write_text(json.dumps(build_eval_template(), indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "evaluation_input": str(eval_input_path),
                "eval_result": str(eval_result_path),
                "metadata": str(metadata_path),
                "renders": {view: str(render_dir / f"{view}.png") for view in VIEWS},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

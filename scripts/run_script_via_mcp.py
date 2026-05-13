import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_MCP = ROOT / "_blender_mcp_official" / "mcp"


def parse_args():
    parser = argparse.ArgumentParser(description="Execute a Blender Python script in the current MCP session.")
    parser.add_argument("script", help="Path to the Blender Python script to execute.")
    parser.add_argument("--root", default=str(ROOT), help="Project root passed through BLENDER_VLM_ROOT.")
    parser.add_argument("--strict-json", action="store_true", help="Require JSON-serializable result.")
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help="Arguments passed after -- to the script.")
    return parser.parse_args()


def main():
    args = parse_args()
    script_path = Path(args.script).resolve()
    if not script_path.is_file():
        raise FileNotFoundError(script_path)

    sys.path.insert(0, str(OFFICIAL_MCP))
    from blmcp.tools_helpers.connection import send_code

    source = script_path.read_text(encoding="utf-8")
    script_args = args.script_args
    if script_args and script_args[0] == "--":
        script_args = script_args[1:]
    mcp_argv = [str(script_path), "--", *script_args]

    wrapper = (
        "import os, sys\n"
        "os.environ['BLENDER_VLM_ROOT'] = {!r}\n"
        "sys.argv = {!r}\n"
        "_globals = {{'__name__': '__main__', '__file__': {!r}}}\n"
        "exec({!r}, _globals)\n"
        "result = _globals.get('result', {{'status': 'ok'}})\n"
    ).format(str(Path(args.root).resolve()), mcp_argv, str(script_path), source)
    response = send_code(wrapper, strict_json=args.strict_json)
    print(json.dumps(response, indent=2, ensure_ascii=False))
    if response.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

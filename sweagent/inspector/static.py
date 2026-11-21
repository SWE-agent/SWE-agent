from __future__ import annotations

import json
import logging
import traceback
from argparse import ArgumentParser
from pathlib import Path

import yaml
from tqdm.auto import tqdm

try:
    from .server import load_content
except ImportError:
    from server import load_content


logger = logging.getLogger(__name__)
logging.getLogger("simple_parsing").setLevel(logging.INFO)


TEMPLATE = """
<html>
<head>
    <title>Trajectory Viewer</title>
    <style>
    {style_sheet}
    </style>
</head>
<body>
    <div class="container">
        {file_path_tree}
        <h2>Conversation History</h2>
        <pre id="fileContent">{file_content}</pre>
    </div>
</body>
</html>
"""

try:
    with open(Path(__file__).parent / "style.css", encoding="utf-8") as infile:
        STYLE_SHEET = infile.read()
except Exception as e:
    style_file = Path(__file__).parent / "style.css"
    logger.error(f"Failed to load style sheet from {style_file}: {traceback.format_exc()}")
    raise e


def _load_file(file_name, gold_patches, test_patches):
    try:
        role_map = {
            "user": "Computer",
            "assistant": "SWE-Agent",
            "subroutine": "SWE-Agent subroutine",
            "default": "Default",
            "system": "System",
            "demo": "Demonstration",
        }
        content = load_content(file_name, gold_patches, test_patches)
        if "history" in content and isinstance(content["history"], list):
            history_content = ""
            for index, item in enumerate(content["history"]):
                item_content = item.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
                if item.get("agent") and item["agent"] != "primary":
                    role_class = "subroutine"
                else:
                    role_class = item.get("role", "default").lower().replace(" ", "-")
                element_id = f"historyItem{index}"
                role_name = role_map.get(item.get("role", ""), item.get("role", ""))
                history_content += (
                    f"""<div class="history-item {role_class}" id="{element_id}">"""
                    f"""<div class="role-bar {role_class}"><strong><span>{role_name}</span></strong></div>"""
                    f"""<div class="content-container">"""
                    f"""<pre>{item_content}</pre>"""
                    f"""</div>"""
                    f"""<div class="shadow"></div>"""
                    f"""</div>"""
                )
            return history_content
        else:
            return "No history content found."
    except Exception:
        return f"Error loading content. {traceback.format_exc()}"


def _make_file_path_tree(file_path):
    path_parts = file_path.split("/")
    relevant_parts = path_parts[-3:]
    html_string = '<div class="filepath">\n'
    for part in relevant_parts:
        html_string += f'<div class="part">{part}</div>\n'
    html_string += "</div>"
    return html_string


def save_static_viewer(file_path):
    if not isinstance(file_path, Path):
        file_path = Path(file_path)
    data = []
    if "args.yaml" in list(map(lambda x: x.name, file_path.parent.iterdir())):
        args = yaml.safe_load(Path(file_path.parent / "args.yaml").read_text(encoding="utf-8"))
        if "environment" in args and "data_path" in args["environment"]:
            data_path = Path(__file__).parent.parent / args["environment"]["data_path"]
            if data_path.exists():
                with open(data_path, encoding="utf-8") as f:
                    data = json.load(f)
            if not isinstance(data, list) or not data or "patch" not in data[0] or "test_patch" not in data[0]:
                data = []
    gold_patches = {x["instance_id"]: x["patch"] for x in data}
    test_patches = {x["instance_id"]: x["test_patch"] for x in data}
    content = _load_file(file_path, gold_patches, test_patches)
    file_path_tree = _make_file_path_tree(file_path.absolute().as_posix())
    icons_path = Path(__file__).parent / "icons"
    relative_icons_path = find_relative_path(file_path, icons_path)
    style_sheet = STYLE_SHEET.replace("url('icons/", f"url('{relative_icons_path.as_posix()}/").replace(
        'url("icons/',
        f'url("{relative_icons_path.as_posix()}/',
    )
    data = TEMPLATE.format(file_content=content, style_sheet=style_sheet, file_path_tree=file_path_tree)
    output_file = file_path.with_suffix(".html")
    with open(output_file, "w+", encoding="utf-8") as outfile:
        print(data, file=outfile)
    logger.info(f"Saved static viewer to {output_file}")


def find_relative_path(from_path, to_path):
    # Convert paths to absolute for uniformity
    from_path = from_path.resolve()
    to_path = to_path.resolve()
    if from_path.is_file():
        from_path = from_path.parent
    if to_path.is_file():
        to_path = to_path.parent
    if not from_path.is_dir() or not to_path.is_dir():
        msg = f"Both from_path and to_path must be directories, but got {from_path} and {to_path}"
        raise ValueError(msg)

    # Identify the common ancestor and the parts of each path beyond it
    common_parts = 0
    for from_part, to_part in zip(from_path.parts, to_path.parts):
        if from_part != to_part:
            break
        common_parts += 1

    # Calculate the '../' needed to get back from from_path to the common ancestor
    back_to_ancestor = [".."] * (len(from_path.parts) - common_parts)

    # Direct path from common ancestor to to_path
    to_target = to_path.parts[common_parts:]

    # Combine to get the relative path
    return Path(*back_to_ancestor, *to_target)


def save_all_trajectories(directory):
    if not isinstance(directory, Path):
        directory = Path(directory)
    all_files = list(directory.glob("**/*.traj"))
    logger.info(f"Found {len(all_files)} trajectory files in {directory}")
    for file_path in tqdm(all_files, desc="Saving static viewers"):
        save_static_viewer(file_path)
    logger.info(f"Saved static viewers for all trajectories in {args.directory}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("directory", type=str, help="Directory containing trajectory files")
    args = parser.parse_args()
    save_all_trajectories(args.directory)

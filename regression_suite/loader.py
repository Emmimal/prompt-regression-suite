"""
loader.py
---------
Loads prompt YAML files and golden query set.
Zero external dependencies — pure stdlib only.
YAML is parsed with a minimal hand-written parser sufficient for this schema.
"""

import json
import re
from pathlib import Path


def _parse_yaml_prompt(text: str) -> dict:
    """
    Minimal YAML parser for prompt files.
    Handles: string fields, multiline block scalars (|), version field.
    Does NOT handle anchors, aliases, or arbitrary nesting.
    """
    result = {}
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip comments and blank lines
        if line.strip().startswith("#") or not line.strip():
            i += 1
            continue

        # Match key: value or key: |
        match = re.match(r'^(\w+):\s*(.*)', line)
        if not match:
            i += 1
            continue

        key = match.group(1)
        value = match.group(2).strip()

        if value == "|":
            # Block scalar — collect indented lines
            block_lines = []
            i += 1
            # Detect indent of first content line
            indent = None
            while i < len(lines):
                block_line = lines[i]
                if block_line.strip() == "" and indent is None:
                    i += 1
                    continue
                if indent is None:
                    indent = len(block_line) - len(block_line.lstrip())
                # Stop when we hit a line at or below root indent that looks like a new key
                if block_line.strip() and not block_line.startswith(" " * indent):
                    break
                block_lines.append(block_line[indent:] if block_line.strip() else "")
                i += 1
            result[key] = "\n".join(block_lines).rstrip()
        elif value.startswith('"') and value.endswith('"'):
            result[key] = value[1:-1]
        else:
            result[key] = value

        i += 1

    return result


def load_prompts(prompts_dir: str) -> dict[str, dict]:
    """
    Load all prompt_v*.yaml files from prompts_dir.
    Returns dict keyed by version string: {"v1": {...}, "v2": {...}, ...}
    """
    prompts = {}
    path = Path(prompts_dir)

    for yaml_file in sorted(path.glob("prompt_v*.yaml")):
        text = yaml_file.read_text(encoding="utf-8")
        parsed = _parse_yaml_prompt(text)
        version = parsed.get("version", yaml_file.stem)
        prompts[version] = parsed

    if not prompts:
        raise FileNotFoundError(f"No prompt_v*.yaml files found in {prompts_dir}")

    return prompts


def load_golden_set(golden_set_path: str) -> list[dict]:
    """
    Load golden queries from JSON file.
    Strips JS-style // comments before parsing (not valid JSON but used for readability).
    """
    text = Path(golden_set_path).read_text(encoding="utf-8")

    # Strip // line comments (not standard JSON — used for annotated golden sets)
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    queries = json.loads(cleaned)

    if not isinstance(queries, list):
        raise ValueError("Golden set must be a JSON array of query objects.")

    return queries

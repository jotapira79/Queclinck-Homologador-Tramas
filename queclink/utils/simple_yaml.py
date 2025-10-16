"""Minimal YAML loader tailored for the Queclink specs.

This loader is intentionally tiny and only implements the subset of YAML that
is used by the homologation specs.  It supports:

* key/value mappings
* nested mappings via indentation
* lists using the ``-`` prefix
* inline dictionaries (``{ key: value }``)
* inline lists (``[a, b, c]``)

The goal is to keep the project self-contained without depending on external
YAML parsers which are not available in the execution environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List


@dataclass(frozen=True)
class _Line:
    indent: int
    content: str


def _strip_comment(line: str) -> str:
    """Remove YAML comments while keeping indentation intact."""

    in_single = False
    in_double = False
    result: List[str] = []
    prev = ""

    for char in line:
        if char == "'" and prev != "\\" and not in_double:
            in_single = not in_single
        elif char == '"' and prev != "\\" and not in_single:
            in_double = not in_double
        if char == "#" and not in_single and not in_double:
            break
        result.append(char)
        prev = char

    return "".join(result).rstrip("\n").rstrip()


def _iter_lines(text: str) -> Iterator[_Line]:
    for raw_line in text.splitlines():
        stripped = _strip_comment(raw_line)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        yield _Line(indent=indent, content=stripped.strip())


def _split_items(text: str) -> List[str]:
    items: List[str] = []
    current: List[str] = []
    depth = 0
    for char in text:
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth = max(depth - 1, 0)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _parse_scalar(value: str):
    lowered = value.lower()
    if lowered in {"~", "null", "none"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.startswith("0x") or value.startswith("0X"):
        return value
    try:
        if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
            return int(value)
        return float(value)
    except ValueError:
        return value


def _parse_inline_list(value: str) -> List:
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [
        _parse_value(part)
        for part in _split_items(inner)
    ]


def _parse_inline_dict(value: str) -> dict:
    inner = value[1:-1].strip()
    if not inner:
        return {}
    result: dict = {}
    for part in _split_items(inner):
        if ":" not in part:
            continue
        key, raw_val = part.split(":", 1)
        result[key.strip()] = _parse_value(raw_val.strip())
    return result


def _parse_value(text: str):
    if text.startswith("{") and text.endswith("}"):
        return _parse_inline_dict(text)
    if text.startswith("[") and text.endswith("]"):
        return _parse_inline_list(text)
    return _parse_scalar(text)


def _parse_block(lines: List[_Line], index: int, indent: int):
    if index >= len(lines):
        return None, index
    line = lines[index]
    if line.indent < indent:
        return None, index
    if line.content.startswith("- ") or line.content == "-":
        return _parse_list(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: List[_Line], index: int, indent: int):
    mapping: dict = {}
    i = index
    while i < len(lines):
        line = lines[i]
        if line.indent < indent:
            break
        if line.content.startswith("- ") or line.content == "-":
            break
        if ":" not in line.content:
            i += 1
            continue
        key, rest = line.content.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        i += 1
        if rest:
            mapping[key] = _parse_value(rest)
            continue
        if i < len(lines) and lines[i].indent > line.indent:
            value, i = _parse_block(lines, i, lines[i].indent)
            mapping[key] = value
        else:
            mapping[key] = None
    return mapping, i


def _parse_list(lines: List[_Line], index: int, indent: int):
    items: list = []
    i = index
    while i < len(lines):
        line = lines[i]
        if line.indent < indent:
            break
        if not (line.content.startswith("- ") or line.content == "-"):
            break
        item_text = line.content[1:].strip()
        i += 1
        if not item_text:
            if i < len(lines) and lines[i].indent > line.indent:
                value, i = _parse_block(lines, i, lines[i].indent)
            else:
                value = None
            items.append(value)
            continue
        if item_text.startswith("{") and item_text.endswith("}"):
            items.append(_parse_inline_dict(item_text))
            continue
        if item_text.startswith("[") and item_text.endswith("]"):
            items.append(_parse_inline_list(item_text))
            continue
        if ":" in item_text:
            key, rest = item_text.split(":", 1)
            entry = {key.strip(): _parse_value(rest.strip())}
            if i < len(lines) and lines[i].indent > line.indent:
                nested, i = _parse_mapping(lines, i, lines[i].indent)
                if isinstance(nested, dict):
                    entry.update(nested)
            items.append(entry)
            continue
        value = _parse_value(item_text)
        if i < len(lines) and lines[i].indent > line.indent:
            nested, i = _parse_block(lines, i, lines[i].indent)
            if isinstance(value, dict) and isinstance(nested, dict):
                value.update(nested)
            elif nested is not None:
                value = nested
        items.append(value)
    return items, i


def load(text: str):
    """Parse the provided YAML text into Python primitives."""

    lines = list(_iter_lines(text))
    if not lines:
        return {}
    value, _ = _parse_block(lines, 0, lines[0].indent)
    return value if value is not None else {}


def load_file(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return load(handle.read())


__all__ = ["load", "load_file"]


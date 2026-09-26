"""Shared helpers for parser adapter normalization."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

BBox = Optional[Tuple[float, float, float, float]]


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source_id(path: Path, source_id: Optional[str]) -> str:
    if source_id:
        return source_id
    if not Path(path).is_file():
        raise FileNotFoundError(path)
    return source_sha256(Path(path))


def coerce_bbox(value: Any) -> BBox:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None


def polygon_to_bbox(value: Any) -> BBox:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    points = []
    for point in value:
        if (
            not isinstance(point, Sequence)
            or isinstance(point, (str, bytes))
            or len(point) < 2
        ):
            return None
        try:
            points.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return None
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def stable_node_id(
    *,
    parser: str,
    source_id: str,
    page_index: int,
    logical_path: str,
    node_type: str,
    content: str,
    bbox: BBox,
) -> str:
    material = json.dumps(
        {
            "parser": parser,
            "source_id": source_id,
            "page_index": page_index,
            "logical_path": logical_path,
            "node_type": node_type,
            "content": content,
            "bbox": list(bbox) if bbox is not None else None,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"node-{uuid.uuid5(uuid.NAMESPACE_URL, material)}"

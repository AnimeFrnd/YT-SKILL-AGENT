from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path

from animatube.core.models import Project


def save_project(project: Project, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = target.parent / f"{target.stem}_assets"
    assets: list[tuple[object, str]] = [
        (layer, "asset_path")
        for scene in project.scenes
        for layer in scene.objects
        if layer.kind == "image" and layer.asset_path
    ]
    assets.extend((track, "path") for track in project.audio_tracks if track.path)
    for item, attribute in assets:
        source_path = Path(project.resolve_asset(getattr(item, attribute)))
        if not source_path.is_file():
            continue
        try:
            source_path.resolve().relative_to(asset_dir.resolve())
            continue
        except ValueError:
            pass
        asset_dir.mkdir(parents=True, exist_ok=True)
        destination = asset_dir / source_path.name
        if destination.exists() and destination.resolve() != source_path.resolve():
            digest = hashlib.sha256(str(source_path.resolve()).encode("utf-8")).hexdigest()[:8]
            destination = asset_dir / f"{source_path.stem}_{digest}{source_path.suffix}"
        if destination.resolve() != source_path.resolve():
            shutil.copy2(source_path, destination)
        setattr(item, attribute, str(destination.relative_to(target.parent)))
    target.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    project.path = str(target.resolve())


def load_project(path: str | Path) -> Project:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not open project: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("The selected file is not a valid AnimaTube project.")
    project = Project.from_dict(data)
    project.path = str(source.resolve())
    return project

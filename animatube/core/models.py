from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4


def _new_id() -> str:
    return uuid4().hex


@dataclass
class Keyframe:
    frame: int
    x: float
    y: float
    scale: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    text_progress: float = 1.0
    easing: str = "linear"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Keyframe":
        return cls(
            frame=max(0, int(value.get("frame", 0))),
            x=float(value.get("x", 0)),
            y=float(value.get("y", 0)),
            scale=max(0.01, float(value.get("scale", 1))),
            rotation=float(value.get("rotation", 0)),
            opacity=min(1.0, max(0.0, float(value.get("opacity", 1)))),
            text_progress=min(1.0, max(0.0, float(value.get("text_progress", 1)))),
            easing=str(value.get("easing", "linear")),
        )


@dataclass
class LayerObject:
    id: str = field(default_factory=_new_id)
    kind: str = "text"
    name: str = "Text"
    x: float = 100
    y: float = 100
    width: float = 300
    height: float = 100
    color: str = "#ffffff"
    text: str = "Your text"
    asset_path: str = ""
    font_size: int = 54
    character_color: str = "#ffb36b"
    keyframes: list[Keyframe] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "LayerObject":
        return cls(
            id=str(value.get("id") or _new_id()),
            kind=str(value.get("kind", "text")),
            name=str(value.get("name", "Layer")),
            x=float(value.get("x", 100)),
            y=float(value.get("y", 100)),
            width=max(1.0, float(value.get("width", 100))),
            height=max(1.0, float(value.get("height", 100))),
            color=str(value.get("color", "#ffffff")),
            text=str(value.get("text", "")),
            asset_path=str(value.get("asset_path", "")),
            font_size=max(1, int(value.get("font_size", 48))),
            character_color=str(value.get("character_color", "#ffb36b")),
            keyframes=[Keyframe.from_dict(k) for k in value.get("keyframes", [])],
        )


@dataclass
class AudioTrack:
    id: str = field(default_factory=_new_id)
    name: str = "Audio"
    path: str = ""
    volume: float = 1.0
    start: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AudioTrack":
        return cls(
            id=str(value.get("id") or _new_id()),
            name=str(value.get("name", "Audio")),
            path=str(value.get("path", "")),
            volume=min(2.0, max(0.0, float(value.get("volume", 1)))),
            start=max(0.0, float(value.get("start", 0))),
            fade_in=max(0.0, float(value.get("fade_in", 0))),
            fade_out=max(0.0, float(value.get("fade_out", 0))),
        )


@dataclass
class Scene:
    id: str = field(default_factory=_new_id)
    name: str = "Scene 1"
    duration: int = 150
    transition: str = "fade"
    transition_duration: int = 15
    objects: list[LayerObject] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scene":
        return cls(
            id=str(value.get("id") or _new_id()),
            name=str(value.get("name", "Scene")),
            duration=max(1, int(value.get("duration", 150))),
            transition=str(value.get("transition", "fade")),
            transition_duration=max(0, int(value.get("transition_duration", 15))),
            objects=[LayerObject.from_dict(item) for item in value.get("objects", [])],
        )


@dataclass
class Project:
    name: str = "Untitled Project"
    width: int = 1920
    height: int = 1080
    fps: int = 30
    background_color: str = "#11131a"
    scenes: list[Scene] = field(default_factory=lambda: [Scene()])
    audio_tracks: list[AudioTrack] = field(default_factory=list)
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("path", None)
        data["format_version"] = 1
        return data

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Project":
        if value.get("format_version", 1) != 1:
            raise ValueError("This project was created with an unsupported AnimaTube version.")
        project = cls(
            name=str(value.get("name", "Untitled Project")),
            width=int(value.get("width", 1920)),
            height=int(value.get("height", 1080)),
            fps=int(value.get("fps", 30)),
            background_color=str(value.get("background_color", "#11131a")),
            scenes=[Scene.from_dict(item) for item in value.get("scenes", [])],
            audio_tracks=[AudioTrack.from_dict(item) for item in value.get("audio_tracks", [])],
        )
        if not 1 <= project.width <= 7680 or not 1 <= project.height <= 7680:
            raise ValueError("Project dimensions must be between 1 and 7680 pixels.")
        if project.fps not in (24, 30, 60):
            raise ValueError("Project frame rate must be 24, 30, or 60 fps.")
        if not project.scenes:
            project.scenes = [Scene()]
        return project

    def resolve_asset(self, asset_path: str) -> str:
        path = Path(asset_path)
        if path.is_absolute() or not self.path:
            return str(path)
        return str((Path(self.path).parent / path).resolve())

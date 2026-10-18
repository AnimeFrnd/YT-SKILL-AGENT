from __future__ import annotations

from bisect import bisect_right

from animatube.core.models import Keyframe, LayerObject


def _ease(progress: float, easing: str) -> float:
    progress = min(1.0, max(0.0, progress))
    if easing == "ease-in":
        return progress * progress
    if easing == "ease-out":
        return 1 - (1 - progress) * (1 - progress)
    if easing == "ease-in-out":
        return 2 * progress * progress if progress < 0.5 else 1 - ((-2 * progress + 2) ** 2) / 2
    return progress


def state_at(layer: LayerObject, frame: int) -> dict[str, float]:
    base = {"x": layer.x, "y": layer.y, "scale": 1.0, "rotation": 0.0, "opacity": 1.0, "text_progress": 1.0}
    frames = sorted(layer.keyframes, key=lambda key: key.frame)
    if not frames:
        return base
    positions = [key.frame for key in frames]
    right = bisect_right(positions, max(0, frame))
    if right == 0:
        return _key_state(frames[0])
    if right == len(frames):
        return _key_state(frames[-1])
    before, after = frames[right - 1], frames[right]
    span = after.frame - before.frame
    progress = 1.0 if span <= 0 else _ease((frame - before.frame) / span, after.easing)
    return {
        field: getattr(before, field) + (getattr(after, field) - getattr(before, field)) * progress
        for field in ("x", "y", "scale", "rotation", "opacity", "text_progress")
    }


def set_state_value(layer: LayerObject, frame: int, field: str, value: float, easing: str = "linear") -> None:
    if field not in ("x", "y", "scale", "rotation", "opacity", "text_progress"):
        raise ValueError(f"Unsupported animated property: {field}")
    if frame == 0 and not layer.keyframes and field in ("x", "y"):
        setattr(layer, field, value)
        return

    key = next((keyframe for keyframe in layer.keyframes if keyframe.frame == frame), None)
    state = state_at(layer, frame)
    if key is None:
        key = Keyframe(
            frame=frame,
            x=state["x"],
            y=state["y"],
            scale=state["scale"],
            rotation=state["rotation"],
            opacity=state["opacity"],
            text_progress=state["text_progress"],
            easing=easing,
        )
        layer.keyframes.append(key)
    setattr(key, field, value)
    layer.keyframes.sort(key=lambda item: item.frame)


def _key_state(key: Keyframe) -> dict[str, float]:
    return {field: float(getattr(key, field)) for field in ("x", "y", "scale", "rotation", "opacity", "text_progress")}

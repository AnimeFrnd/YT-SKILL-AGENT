from __future__ import annotations


def output_dimensions(profile: str, resolution: str) -> tuple[int, int]:
    heights = {"720p": 720, "1080p": 1080, "4K": 2160}
    if profile not in ("wide", "vertical", "square"):
        raise ValueError(f"Unsupported output profile: {profile}")
    if resolution not in heights:
        raise ValueError(f"Unsupported output resolution: {resolution}")
    height = heights[resolution]
    if profile == "wide":
        width = height * 16 // 9
    elif profile == "vertical":
        width = height * 9 // 16
    else:
        width = height
    return width - width % 2, height - height % 2

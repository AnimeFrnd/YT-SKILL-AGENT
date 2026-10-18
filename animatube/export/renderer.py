from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF

from animatube.core.animation import state_at
from animatube.core.models import LayerObject, Project, Scene


Progress = Callable[[int, str], None]


def _draw_scene(project: Project, scene: Scene, frame: int, width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#11131a"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scale_x, scale_y = width / project.width, height / project.height

    for layer in scene.objects:
        state = state_at(layer, frame)
        opacity = min(1.0, max(0.0, state["opacity"]))
        painter.save()
        painter.setOpacity(opacity)
        x, y = state["x"] * scale_x, state["y"] * scale_y
        w, h = layer.width * state["scale"] * scale_x, layer.height * state["scale"] * scale_y
        painter.translate(x + w / 2, y + h / 2)
        painter.rotate(state["rotation"])
        bounds = QRectF(-w / 2, -h / 2, w, h)
        color = QColor(layer.color)

        if layer.kind in ("rect", "ellipse"):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            if layer.kind == "ellipse":
                painter.drawEllipse(bounds)
            else:
                painter.drawRoundedRect(bounds, min(w, h) * 0.08, min(w, h) * 0.08)
        elif layer.kind == "triangle":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([bounds.topLeft(), bounds.bottomRight(), bounds.bottomLeft()]))
        elif layer.kind == "image":
            asset = QImage(project.resolve_asset(layer.asset_path))
            if asset.isNull():
                painter.restore()
                painter.end()
                raise ValueError(f"Could not load image asset: {layer.asset_path}")
            painter.drawImage(bounds, asset)
        elif layer.kind == "character":
            head_height = h * 0.38
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(layer.character_color))
            painter.drawEllipse(QRectF(-w * 0.2, -h * 0.48, w * 0.4, head_height))
            painter.setBrush(QColor("#7c6cff"))
            painter.drawRoundedRect(QRectF(-w * 0.28, -h * 0.05, w * 0.56, h * 0.52), w * 0.16, w * 0.16)
            painter.setBrush(QColor("#f3f4f6"))
            painter.drawEllipse(QRectF(-w * 0.11, -h * 0.36, w * 0.06, h * 0.06))
            painter.drawEllipse(QRectF(w * 0.05, -h * 0.36, w * 0.06, h * 0.06))
        elif layer.kind == "text":
            painter.setPen(QPen(color))
            font = QFont("Arial", max(1, round(layer.font_size * scale_y)))
            font.setBold(True)
            painter.setFont(font)
            text_length = max(0, min(len(layer.text), round(len(layer.text) * state["text_progress"])))
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, layer.text[:text_length])
        painter.restore()
    painter.end()
    return image


def _transition(previous: QImage, current: QImage, progress: float, kind: str) -> QImage:
    image = QImage(current.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#11131a"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    width, height = current.width(), current.height()
    if kind == "slide":
        offset = round(width * progress)
        painter.drawImage(-offset, 0, previous)
        painter.drawImage(width - offset, 0, current)
    elif kind == "wipe":
        painter.drawImage(0, 0, previous)
        painter.setClipRect(QRectF(0, 0, width * progress, height))
        painter.drawImage(0, 0, current)
    else:
        painter.drawImage(0, 0, previous)
        painter.setOpacity(progress)
        painter.drawImage(0, 0, current)
    painter.end()
    return image


def _paint_frame(image: QImage, path: Path) -> None:
    if not image.save(str(path), "PNG"):
        raise OSError(f"Could not write temporary render frame: {path}")


def render_project(
    project: Project,
    output: str | Path,
    *,
    resolution: tuple[int, int] | None = None,
    fps: int | None = None,
    ffmpeg: str = "ffmpeg",
    progress: Progress | None = None,
) -> None:
    ffmpeg_path = shutil.which(ffmpeg)
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg and add it to PATH before exporting.")

    width, height = resolution or (project.width, project.height)
    frame_rate = fps or project.fps
    if width <= 0 or height <= 0 or frame_rate not in (24, 30, 60):
        raise ValueError("Choose a valid output resolution and frame rate.")
    total_frames = sum(scene.duration for scene in project.scenes)
    if total_frames <= 0:
        raise ValueError("The project has no frames to render.")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="animatube-") as temporary:
        temp_dir = Path(temporary)
        frame_index = 0
        last_scene_image: QImage | None = None
        for scene_index, scene in enumerate(project.scenes):
            for local_frame in range(scene.duration):
                current = _draw_scene(project, scene, local_frame, width, height)
                transition_frames = min(scene.transition_duration, scene.duration)
                if scene_index > 0 and last_scene_image is not None and local_frame < transition_frames and transition_frames:
                    blend = _transition(last_scene_image, current, (local_frame + 1) / transition_frames, scene.transition)
                    _paint_frame(blend, temp_dir / f"frame_{frame_index:06d}.png")
                else:
                    _paint_frame(current, temp_dir / f"frame_{frame_index:06d}.png")
                frame_index += 1
                if progress:
                    progress(round(frame_index / total_frames * 65), "Rendering frames")
            last_scene_image = _draw_scene(project, scene, scene.duration - 1, width, height)

        command = [
            ffmpeg_path, "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(frame_rate), "-i", str(temp_dir / "frame_%06d.png"),
        ]
        audio_tracks = []
        for track in project.audio_tracks:
            if not track.path:
                continue
            audio_path = Path(project.resolve_asset(track.path))
            if not audio_path.is_file():
                raise FileNotFoundError(f"Audio track '{track.name}' was not found: {audio_path}")
            audio_tracks.append((track, audio_path))
            command.extend(["-i", str(audio_path)])
        duration = total_frames / frame_rate
        if audio_tracks:
            filters: list[str] = []
            labels: list[str] = []
            for index, (track, _audio_path) in enumerate(audio_tracks):
                source_index = index + 1
                label = f"a{index}"
                chain = [
                    f"[{source_index}:a]atrim=duration={duration:.4f}",
                    "asetpts=PTS-STARTPTS",
                    f"adelay={round(track.start * 1000)}|{round(track.start * 1000)}",
                    f"volume={track.volume}",
                ]
                if track.fade_in:
                    chain.append(f"afade=t=in:st=0:d={track.fade_in}")
                if track.fade_out:
                    chain.append(f"afade=t=out:st={max(0.0, duration - track.fade_out):.4f}:d={track.fade_out}")
                filters.append(",".join(chain) + f"[{label}]")
                labels.append(f"[{label}]")
            filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:dropout_transition=0[aout]")
            command.extend(["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k"])
        else:
            command.append("-an")
        command.extend([
            "-t", f"{duration:.4f}", "-c:v", "libx264", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-progress", "pipe:1", str(target),
        ])
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise RuntimeError(f"Could not start FFmpeg: {exc}") from exc

        assert process.stdout is not None
        output_lines: list[str] = []
        for line in process.stdout:
            output_lines.append(line.rstrip())
            if line.startswith("out_time_ms=") and progress:
                try:
                    elapsed = int(line.split("=", 1)[1]) / 1_000_000
                    progress(65 + min(34, round(elapsed / duration * 34)), "Encoding MP4")
                except ValueError:
                    continue
        return_code = process.wait()
        if return_code:
            details = "\n".join(output_lines[-12:])
            raise RuntimeError(f"FFmpeg could not render the video.\n{details}")
        if progress:
            progress(100, "Export complete")

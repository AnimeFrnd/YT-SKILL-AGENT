import tempfile
import unittest
from pathlib import Path

from animatube.core.animation import state_at
from animatube.core.models import AudioTrack, Keyframe, LayerObject, Project, Scene
from animatube.core.project import load_project, save_project


class AnimationTests(unittest.TestCase):
    def test_interpolates_keyframe_properties(self):
        layer = LayerObject(
            x=10,
            y=20,
            keyframes=[
                Keyframe(frame=0, x=0, y=10, scale=1, rotation=0, opacity=0, text_progress=0),
                Keyframe(frame=10, x=100, y=50, scale=3, rotation=90, opacity=1, text_progress=1),
            ],
        )
        state = state_at(layer, 5)
        self.assertEqual(state, {"x": 50, "y": 30, "scale": 2, "rotation": 45, "opacity": 0.5, "text_progress": 0.5})

    def test_easing_and_keyframe_boundaries(self):
        layer = LayerObject(keyframes=[
            Keyframe(frame=10, x=0, y=0),
            Keyframe(frame=20, x=100, y=0, easing="ease-in"),
        ])
        self.assertEqual(state_at(layer, 0)["x"], 0)
        self.assertEqual(state_at(layer, 15)["x"], 25)
        self.assertEqual(state_at(layer, 30)["x"], 100)


class ProjectTests(unittest.TestCase):
    def test_project_round_trip_includes_scene_animation_and_audio(self):
        project = Project(
            name="Test",
            scenes=[Scene(name="Opening", objects=[LayerObject(
                name="Title", text="Hello", keyframes=[Keyframe(frame=8, x=120, y=90)]
            )])],
            audio_tracks=[AudioTrack(name="Music", path="music.wav", volume=0.5, fade_in=2)],
        )
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(restored.name, "Test")
        self.assertEqual(restored.scenes[0].objects[0].keyframes[0].frame, 8)
        self.assertEqual(restored.audio_tracks[0].volume, 0.5)

    def test_rejects_unsupported_frame_rate_and_dimensions(self):
        with self.assertRaises(ValueError):
            Project.from_dict({"fps": 25})
        with self.assertRaises(ValueError):
            Project.from_dict({"width": 9000})

    def test_save_bundles_assets_and_load_resolves_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "art.png"
            image.write_bytes(b"image data")
            audio = root / "music.wav"
            audio.write_bytes(b"audio data")
            project = Project(
                scenes=[Scene(objects=[LayerObject(kind="image", asset_path=str(image))])],
                audio_tracks=[AudioTrack(path=str(audio))],
            )
            destination = root / "project.anima"
            save_project(project, destination)
            restored = load_project(destination)
            image_path = Path(restored.resolve_asset(restored.scenes[0].objects[0].asset_path))
            audio_path = Path(restored.resolve_asset(restored.audio_tracks[0].path))
            self.assertTrue(image_path.is_file())
            self.assertTrue(audio_path.is_file())
            self.assertEqual(image_path.read_bytes(), b"image data")
            self.assertEqual(audio_path.read_bytes(), b"audio data")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from animatube.core.animation import set_state_value, state_at
from animatube.core.models import AudioTrack, Keyframe, LayerObject, Project, Scene
from animatube.core.profiles import output_dimensions
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

    def test_frame_zero_transform_edits_are_keyframed_without_fake_layer_attributes(self):
        layer = LayerObject(x=24, y=48)
        set_state_value(layer, 0, "scale", 1.5)
        set_state_value(layer, 0, "rotation", 30)
        set_state_value(layer, 0, "opacity", 0.4)
        state = state_at(layer, 0)
        self.assertEqual((state["x"], state["y"]), (24, 48))
        self.assertEqual((state["scale"], state["rotation"], state["opacity"]), (1.5, 30, 0.4))
        self.assertEqual(len(layer.keyframes), 1)
        self.assertFalse(hasattr(layer, "scale"))

    def test_frame_zero_position_edit_updates_base_layer_when_unanimated(self):
        layer = LayerObject()
        set_state_value(layer, 0, "x", 42)
        self.assertEqual(layer.x, 42)
        self.assertEqual(layer.keyframes, [])
        self.assertEqual(state_at(layer, 0)["x"], 42)

    def test_export_profiles_use_even_dimensions(self):
        self.assertEqual(output_dimensions("wide", "1080p"), (1920, 1080))
        self.assertEqual(output_dimensions("vertical", "720p"), (404, 720))
        self.assertEqual(output_dimensions("vertical", "1080p"), (606, 1080))
        self.assertEqual(output_dimensions("vertical", "4K"), (1214, 2160))
        self.assertEqual(output_dimensions("square", "1080p"), (1080, 1080))
        for profile in ("wide", "vertical", "square"):
            for resolution in ("720p", "1080p", "4K"):
                width, height = output_dimensions(profile, resolution)
                self.assertEqual(width % 2, 0)
                self.assertEqual(height % 2, 0)


class ProjectTests(unittest.TestCase):
    def test_project_round_trip_includes_scene_animation_and_audio(self):
        project = Project(
            name="Test",
            background_color="#223344",
            scenes=[Scene(name="Opening", objects=[LayerObject(
                name="Title", text="Hello", keyframes=[Keyframe(frame=8, x=120, y=90)]
            )])],
            audio_tracks=[AudioTrack(name="Music", path="music.wav", volume=0.5, fade_in=2)],
        )
        restored = Project.from_dict(project.to_dict())
        self.assertEqual(restored.name, "Test")
        self.assertEqual(restored.background_color, "#223344")
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

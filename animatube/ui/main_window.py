from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable
from uuid import uuid4

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from animatube.core.animation import state_at
from animatube.core.models import AudioTrack, Keyframe, LayerObject, Project, Scene
from animatube.core.project import load_project, save_project
from animatube.export.renderer import _draw_scene, render_project


APP_STYLE = """
QWidget { background: #11131a; color: #e7e9f2; font: 10pt "Segoe UI"; }
QMainWindow { background: #0b0d12; }
QFrame#Panel { background: #171a23; border: 1px solid #282c38; border-radius: 9px; }
QLabel#Muted { color: #8b91a3; }
QLabel#Section { color: #a5aabd; font-size: 9pt; font-weight: 700; }
QPushButton { background: #242836; border: 1px solid #343949; border-radius: 6px; padding: 7px 10px; }
QPushButton:hover { background: #303648; }
QPushButton:pressed { background: #3a4260; }
QPushButton#Primary { background: #725cff; border: 0; color: white; font-weight: 700; }
QPushButton#Primary:hover { background: #826fff; }
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateTimeEdit, QListWidget {
  background: #10121a; border: 1px solid #303545; border-radius: 5px; padding: 6px;
}
QListWidget::item { padding: 7px; border-radius: 4px; }
QListWidget::item:selected { background: #37345c; color: white; }
QSlider::groove:horizontal { height: 5px; background: #303545; border-radius: 2px; }
QSlider::handle:horizontal { background: #8c7bff; width: 14px; margin: -5px 0; border-radius: 7px; }
QProgressBar { border: 1px solid #343949; border-radius: 5px; text-align: center; }
QProgressBar::chunk { background: #725cff; border-radius: 4px; }
"""


class CanvasWidget(QWidget):
    move_started = Signal(str)
    layer_moved = Signal(str, float, float)
    asset_dropped = Signal(str, float, float)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = Project()
        self.scene_index = 0
        self.frame = 0
        self.selected_id = ""
        self.drag_id = ""
        self.drag_offset = QPointF()
        self.setMinimumSize(480, 280)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

    def set_view(self, project: Project, scene_index: int, frame: int, selected_id: str) -> None:
        self.project, self.scene_index, self.frame, self.selected_id = project, scene_index, frame, selected_id
        self.update()

    def _target_rect(self) -> QRectF:
        if not self.project.width or not self.project.height:
            return QRectF()
        margin = 18
        available_w, available_h = max(1, self.width() - margin * 2), max(1, self.height() - margin * 2)
        ratio = min(available_w / self.project.width, available_h / self.project.height)
        width, height = self.project.width * ratio, self.project.height * ratio
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0e1016"))
        board = self._target_rect()
        painter.setPen(QPen(QColor("#3a3e4d"), 1))
        painter.setBrush(QColor("#11131a"))
        painter.drawRoundedRect(board, 4, 4)
        if self.scene_index >= len(self.project.scenes):
            return
        scene = self.project.scenes[self.scene_index]
        try:
            image = _draw_scene(self.project, scene, self.frame, self.project.width, self.project.height)
            painter.drawImage(board, image)
        except (OSError, ValueError) as exc:
            painter.setPen(QColor("#ff9a9a"))
            painter.drawText(board.adjusted(20, 20, -20, -20), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, str(exc))
        selected = next((obj for obj in scene.objects if obj.id == self.selected_id), None)
        if selected:
            state = state_at(selected, self.frame)
            factor = board.width() / self.project.width
            bounds = QRectF(board.x() + state["x"] * factor, board.y() + state["y"] * factor,
                            selected.width * state["scale"] * factor, selected.height * state["scale"] * factor)
            painter.setPen(QPen(QColor("#a99cff"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bounds)

    def _project_point(self, point: QPointF) -> QPointF:
        board = self._target_rect()
        if not board.contains(point):
            return QPointF(-1, -1)
        return QPointF((point.x() - board.x()) * self.project.width / board.width(),
                       (point.y() - board.y()) * self.project.height / board.height())

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.scene_index >= len(self.project.scenes):
            return
        point = self._project_point(event.position())
        if point.x() < 0:
            return
        scene = self.project.scenes[self.scene_index]
        selected = None
        for obj in reversed(scene.objects):
            state = state_at(obj, self.frame)
            if (state["x"] <= point.x() <= state["x"] + obj.width * state["scale"]
                    and state["y"] <= point.y() <= state["y"] + obj.height * state["scale"]):
                selected = obj
                selected_state = state
                break
        if selected:
            self.selected_id = selected.id
            self.drag_id = selected.id
            self.drag_offset = QPointF(point.x() - selected_state["x"], point.y() - selected_state["y"])
            self.move_started.emit(selected.id)
            self.update()
        else:
            self.selected_id = ""
            self.drag_id = ""
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if not self.drag_id or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        point = self._project_point(event.position())
        if point.x() >= 0:
            self.layer_moved.emit(self.drag_id, max(0, point.x() - self.drag_offset.x()),
                                  max(0, point.y() - self.drag_offset.y()))

    def mouseReleaseEvent(self, event) -> None:
        self.drag_id = ""

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            point = self._project_point(event.position())
            self.asset_dropped.emit(urls[0].toLocalFile(), max(0, point.x()), max(0, point.y()))
            event.acceptProposedAction()


class TaskWorker(QThread):
    progress = Signal(int, str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, task: Callable, parent: QWidget | None = None):
        super().__init__(parent)
        self.task = task

    def run(self) -> None:
        def report(*values) -> None:
            self.progress.emit(int(values[0]), str(values[1]) if len(values) > 1 else "")
        try:
            self.succeeded.emit(self.task(report))
        except Exception as exc:
            self.failed.emit(str(exc))


class BusyDialog(QDialog):
    def __init__(self, title: str, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.message = QLabel("Starting…")
        self.bar = QProgressBar()
        layout.addWidget(self.message)
        layout.addWidget(self.bar)
        self.setMinimumWidth(360)

    def update_progress(self, percent: int, message: str) -> None:
        self.bar.setValue(max(0, min(100, percent)))
        if message:
            self.message.setText(message)


class ExportOptionsDialog(QDialog):
    def __init__(self, parent: QWidget, project: Project):
        super().__init__(parent)
        self.setWindowTitle("Export settings")
        form = QFormLayout(self)
        self.aspect = QComboBox()
        self.aspect.addItem("YouTube · 16:9", "wide")
        self.aspect.addItem("Shorts · 9:16", "vertical")
        self.aspect.addItem("Square · 1:1", "square")
        self.size = QComboBox()
        self.size.addItems(["720p", "1080p", "4K"])
        self.fps = QComboBox()
        self.fps.addItems(["24", "30", "60"])
        self.aspect.setCurrentIndex(0 if project.width >= project.height else 1)
        self.fps.setCurrentText(str(project.fps))
        form.addRow("Format", self.aspect)
        form.addRow("Resolution", self.size)
        form.addRow("Frame rate", self.fps)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def output_settings(self) -> tuple[tuple[int, int], int]:
        maximum = {"720p": 720, "1080p": 1080, "4K": 2160}[self.size.currentText()]
        aspect = self.aspect.currentData()
        dimensions = (maximum * 16 // 9, maximum) if aspect == "wide" else (
            (maximum * 9 // 16, maximum) if aspect == "vertical" else (maximum, maximum)
        )
        if dimensions[0] % 2:
            dimensions = (dimensions[0] - 1, dimensions[1])
        return dimensions, int(self.fps.currentText())


class UploadDialog(QDialog):
    def __init__(self, parent: QWidget, initial_video: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Upload to YouTube")
        self.resize(500, 520)
        self.thumbnail_path = ""
        form = QFormLayout(self)
        self.video = QLineEdit(initial_video)
        video_button = QPushButton("Browse…")
        video_button.clicked.connect(self._pick_video)
        video_row = QHBoxLayout()
        video_row.addWidget(self.video)
        video_row.addWidget(video_button)
        form.addRow("MP4 video", video_row)
        self.oauth = QLineEdit(str(Path.home() / ".animatube" / "client_secret.json"))
        oauth_button = QPushButton("Browse…")
        oauth_button.clicked.connect(self._pick_oauth)
        oauth_row = QHBoxLayout()
        oauth_row.addWidget(self.oauth)
        oauth_row.addWidget(oauth_button)
        form.addRow("Google OAuth JSON", oauth_row)
        self.title = QLineEdit()
        self.title.setMaxLength(100)
        form.addRow("Title", self.title)
        self.description = QTextEdit()
        self.description.setMaximumHeight(90)
        form.addRow("Description", self.description)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("Separate tags with commas")
        form.addRow("Tags", self.tags)
        self.category = QComboBox()
        for text, code in (("Film & Animation", "1"), ("Education", "27"), ("Entertainment", "24"),
                           ("Howto & Style", "26"), ("Science & Technology", "28"), ("People & Blogs", "22")):
            self.category.addItem(text, code)
        form.addRow("Category", self.category)
        self.privacy = QComboBox()
        self.privacy.addItems(["Private", "Unlisted", "Public"])
        form.addRow("Visibility", self.privacy)
        self.thumbnail = QPushButton("Choose custom thumbnail…")
        self.thumbnail.clicked.connect(self._pick_thumbnail)
        form.addRow("Thumbnail", self.thumbnail)
        self.schedule = QCheckBox("Schedule publishing")
        form.addRow(self.schedule)
        self.publish_at = QDateTimeEdit()
        self.publish_at.setCalendarPopup(True)
        self.publish_at.setDateTime(self.publish_at.dateTime().addDays(1))
        form.addRow("Publish at", self.publish_at)
        self.schedule.toggled.connect(self.publish_at.setEnabled)
        self.publish_at.setEnabled(False)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Sign in & upload")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _pick_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select rendered MP4", "", "MP4 video (*.mp4)")
        if path:
            self.video.setText(path)

    def _pick_oauth(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Google OAuth client", "", "JSON files (*.json)")
        if path:
            self.oauth.setText(path)

    def _pick_thumbnail(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select thumbnail", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.thumbnail_path = path
            self.thumbnail.setText(Path(path).name)

    def upload_values(self) -> dict:
        publish_at = self.publish_at.dateTime().toUTC().toString("yyyy-MM-dd'T'HH:mm:ss'Z'") if self.schedule.isChecked() else None
        return {
            "video_path": self.video.text().strip(),
            "oauth_path": self.oauth.text().strip(),
            "title": self.title.text().strip(),
            "description": self.description.toPlainText(),
            "tags": self.tags.text().split(","),
            "category_id": self.category.currentData(),
            "privacy": self.privacy.currentText().lower(),
            "thumbnail_path": self.thumbnail_path or None,
            "publish_at": publish_at,
        }


class VoiceRecorderDialog(QDialog):
    def __init__(self, output_path: str, parent: QWidget):
        super().__init__(parent)
        try:
            from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaRecorder
        except ImportError as exc:
            raise RuntimeError("Voice recording requires the PySide6 Qt Multimedia component.") from exc
        self.setWindowTitle("Record voice-over")
        self.output_path = output_path
        self.session = QMediaCaptureSession(self)
        self.audio_input = QAudioInput(self)
        self.recorder = QMediaRecorder(self)
        self.session.setAudioInput(self.audio_input)
        self.session.setRecorder(self.recorder)
        self.recorder.setOutputLocation(QUrl.fromLocalFile(output_path))
        self.recorder.errorOccurred.connect(self._record_error)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Record narration from the selected microphone, then stop to save the WAV file."))
        self.state = QLabel("Ready")
        layout.addWidget(self.state)
        self.toggle = QPushButton("Start recording")
        self.toggle.clicked.connect(self._toggle)
        layout.addWidget(self.toggle)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self._finish_recording)
        layout.addWidget(buttons)

    def _toggle(self) -> None:
        from PySide6.QtMultimedia import QMediaRecorder
        if self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.recorder.stop()
            self.toggle.setText("Start recording")
            self.state.setText(f"Saved: {self.output_path}")
        else:
            self.recorder.record()
            self.toggle.setText("Stop recording")
            self.state.setText("Recording…")

    def _record_error(self, error, message: str) -> None:
        self.state.setText(f"Recording error: {message}")

    def _finish_recording(self) -> None:
        from PySide6.QtMultimedia import QMediaRecorder
        if self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.recorder.stop()
        if Path(self.output_path).is_file():
            self.accept()
        else:
            self.reject()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = Project()
        self.scene_index = 0
        self.frame = 0
        self.selected_id = ""
        self.selected_audio_id = ""
        self.dirty = False
        self.last_export_path = ""
        self.undo_stack: list[str] = []
        self.redo_stack: list[str] = []
        self.worker: TaskWorker | None = None
        self.busy_dialog: BusyDialog | None = None
        self._inspectors_loading = False
        self.setWindowTitle("AnimaTube")
        self.resize(1500, 920)
        self.setMinimumSize(1050, 690)
        self._build_ui()
        self._build_shortcuts()
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._tick)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(120_000)
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start()
        self._refresh_all()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 8)
        root_layout.setSpacing(10)
        bar = QHBoxLayout()
        brand = QLabel("ANIMATUBE")
        brand.setStyleSheet("color:#a99cff;font-weight:800;letter-spacing:2px")
        bar.addWidget(brand)
        self.project_name = QLineEdit(self.project.name)
        self.project_name.setMaximumWidth(250)
        self.project_name.editingFinished.connect(self._rename_project)
        bar.addWidget(self.project_name)
        for label, callback in (
            ("New", self.new_project), ("Open", self.open_project), ("Save", self.save_project_dialog),
            ("Undo", self.undo), ("Redo", self.redo), ("Project settings", self.project_settings),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch(1)
        self.export_button = QPushButton("Export MP4")
        self.export_button.setObjectName("Primary")
        self.export_button.clicked.connect(self.export_video)
        bar.addWidget(self.export_button)
        upload_button = QPushButton("YouTube upload")
        upload_button.clicked.connect(self.upload_video)
        bar.addWidget(upload_button)
        root_layout.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._make_scene_panel())
        split.addWidget(self._make_editor_panel())
        split.addWidget(self._make_inspector_panel())
        split.setSizes([220, 900, 280])
        root_layout.addWidget(split, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")

    def _panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        heading = QLabel(title.upper())
        heading.setObjectName("Section")
        layout.addWidget(heading)
        return frame, layout

    def _make_scene_panel(self) -> QWidget:
        frame, layout = self._panel("Scenes")
        self.scene_list = QListWidget()
        self.scene_list.currentRowChanged.connect(self._select_scene)
        layout.addWidget(self.scene_list, 1)
        row = QHBoxLayout()
        for label, callback in (("+", self.add_scene), ("Duplicate", self.duplicate_scene), ("−", self.delete_scene)):
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        row = QHBoxLayout()
        for label, delta in (("↑", -1), ("↓", 1)):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, offset=delta: self.move_scene(offset))
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(QLabel("Transition"))
        self.transition = QComboBox()
        self.transition.addItems(["fade", "wipe", "slide", "dissolve"])
        self.transition.currentTextChanged.connect(self._set_transition)
        layout.addWidget(self.transition)
        self.transition_length = QSpinBox()
        self.transition_length.setRange(0, 300)
        self.transition_length.setSuffix(" frames")
        self.transition_length.valueChanged.connect(self._set_transition_length)
        layout.addWidget(self.transition_length)
        self.scene_duration = QSpinBox()
        self.scene_duration.setRange(1, 36000)
        self.scene_duration.setSuffix(" frames")
        self.scene_duration.valueChanged.connect(self._set_scene_duration)
        layout.addWidget(QLabel("Scene length"))
        layout.addWidget(self.scene_duration)
        return frame

    def _make_editor_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        tools, tools_layout = self._panel("Add to scene")
        tool_row = QHBoxLayout()
        for label, callback in (
            ("Text", self.add_text), ("Rectangle", lambda: self.add_shape("rect")),
            ("Circle", lambda: self.add_shape("ellipse")), ("Triangle", lambda: self.add_shape("triangle")),
            ("Character", self.add_character), ("Import image", self.import_image),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            tool_row.addWidget(button)
        tools_layout.addLayout(tool_row)
        layout.addWidget(tools)
        canvas_panel, canvas_layout = self._panel("Preview canvas")
        self.canvas = CanvasWidget()
        self.canvas.move_started.connect(self._begin_canvas_move)
        self.canvas.layer_moved.connect(self._move_layer)
        self.canvas.asset_dropped.connect(self._drop_asset)
        canvas_layout.addWidget(self.canvas, 1)
        layout.addWidget(canvas_panel, 4)
        controls, controls_layout = self._panel("Timeline")
        transport = QHBoxLayout()
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self.toggle_playback)
        transport.addWidget(self.play_button)
        self.frame_label = QLabel("Frame 0")
        transport.addWidget(self.frame_label)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.valueChanged.connect(self._set_frame)
        transport.addWidget(self.frame_slider, 1)
        self.set_keyframe_button = QPushButton("Set keyframe")
        self.set_keyframe_button.clicked.connect(self.add_keyframe)
        transport.addWidget(self.set_keyframe_button)
        self.easing = QComboBox()
        self.easing.addItems(["linear", "ease-in", "ease-out", "ease-in-out"])
        self.easing.setMaximumWidth(125)
        transport.addWidget(self.easing)
        controls_layout.addLayout(transport)
        lower = QHBoxLayout()
        layers_column = QVBoxLayout()
        layers_column.addWidget(QLabel("Layers"))
        self.layer_list = QListWidget()
        self.layer_list.currentItemChanged.connect(self._select_layer)
        self.layer_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.layer_list.model().rowsMoved.connect(self._reorder_layers)
        layers_column.addWidget(self.layer_list)
        remove_layer = QPushButton("Remove selected layer")
        remove_layer.clicked.connect(self.delete_layer)
        layers_column.addWidget(remove_layer)
        lower.addLayout(layers_column, 3)
        audio_column = QVBoxLayout()
        audio_header = QHBoxLayout()
        audio_header.addWidget(QLabel("Audio tracks"))
        add_audio = QPushButton("Import")
        add_audio.clicked.connect(self.import_audio)
        record_audio = QPushButton("Record")
        record_audio.clicked.connect(self.record_audio)
        tts = QPushButton("Text to speech")
        tts.clicked.connect(self.text_to_speech)
        audio_header.addWidget(add_audio)
        audio_header.addWidget(record_audio)
        audio_header.addWidget(tts)
        audio_column.addLayout(audio_header)
        self.audio_list = QListWidget()
        self.audio_list.currentRowChanged.connect(self._select_audio)
        audio_column.addWidget(self.audio_list, 1)
        audio_controls = QHBoxLayout()
        audio_controls.addWidget(QLabel("Volume"))
        self.audio_volume = QDoubleSpinBox()
        self.audio_volume.setRange(0, 2)
        self.audio_volume.setSingleStep(0.1)
        self.audio_volume.valueChanged.connect(self._change_audio_volume)
        audio_controls.addWidget(self.audio_volume)
        audio_controls.addWidget(QLabel("Start (s)"))
        self.audio_start = QDoubleSpinBox()
        self.audio_start.setRange(0, 86400)
        self.audio_start.valueChanged.connect(self._change_audio_start)
        audio_controls.addWidget(self.audio_start)
        remove_audio = QPushButton("Remove")
        remove_audio.clicked.connect(self.remove_audio)
        audio_controls.addWidget(remove_audio)
        audio_column.addLayout(audio_controls)
        audio_fades = QHBoxLayout()
        audio_fades.addWidget(QLabel("Fade in/out (s)"))
        self.fade_in = QDoubleSpinBox()
        self.fade_out = QDoubleSpinBox()
        for control in (self.fade_in, self.fade_out):
            control.setRange(0, 600)
            control.setSingleStep(0.5)
            control.valueChanged.connect(self._change_audio_fades)
            audio_fades.addWidget(control)
        audio_column.addLayout(audio_fades)
        lower.addLayout(audio_column, 5)
        controls_layout.addLayout(lower, 1)
        layout.addWidget(controls, 2)
        return widget

    def _make_inspector_panel(self) -> QWidget:
        frame, layout = self._panel("Properties")
        self.inspector_stack = QStackedWidget()
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addWidget(QLabel("Select a layer on the canvas to edit its properties."))
        empty_layout.addStretch()
        self.inspector_stack.addWidget(empty)
        properties = QWidget()
        form = QFormLayout(properties)
        form.setContentsMargins(0, 0, 0, 0)
        self.layer_name = QLineEdit()
        self.layer_name.editingFinished.connect(self._edit_layer_name)
        form.addRow("Layer", self.layer_name)
        self.text_value = QTextEdit()
        self.text_value.setMaximumHeight(100)
        self.text_value.textChanged.connect(self._edit_layer_text)
        form.addRow("Text", self.text_value)
        self.property_controls: dict[str, QDoubleSpinBox] = {}
        for name, low, high, step in (
            ("X", 0, 7680, 10), ("Y", 0, 7680, 10), ("Width", 1, 7680, 10),
            ("Height", 1, 7680, 10), ("Scale", 0.01, 20, 0.1),
            ("Rotation", -3600, 3600, 5), ("Opacity", 0, 1, 0.05),
        ):
            control = QDoubleSpinBox()
            control.setRange(low, high)
            control.setSingleStep(step)
            control.valueChanged.connect(lambda value, key=name.lower(): self._edit_property(key, value))
            self.property_controls[name.lower()] = control
            form.addRow(name, control)
        self.color_button = QPushButton("Choose color…")
        self.color_button.clicked.connect(self.choose_color)
        form.addRow("Fill", self.color_button)
        self.preset = QComboBox()
        self.preset.addItems(["fade in", "fade out", "slide in", "bounce", "zoom", "typewriter"])
        preset_button = QPushButton("Apply animation")
        preset_button.clicked.connect(self.apply_preset)
        preset_row = QHBoxLayout()
        preset_row.addWidget(self.preset, 1)
        preset_row.addWidget(preset_button)
        form.addRow("Preset", preset_row)
        self.inspector_stack.addWidget(properties)
        layout.addWidget(self.inspector_stack)
        layout.addStretch()
        return frame

    def _build_shortcuts(self) -> None:
        for sequence, callback in (("Ctrl+S", self.save_project_dialog), ("Ctrl+O", self.open_project),
                                   ("Ctrl+Z", self.undo), ("Ctrl+Y", self.redo), ("Space", self.toggle_playback)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)

    def _snapshot(self) -> None:
        self.undo_stack.append(json.dumps(self.project.to_dict(), ensure_ascii=False))
        del self.undo_stack[:-80]
        self.redo_stack.clear()

    def _restore(self, snapshot: str) -> None:
        path = self.project.path
        self.project = Project.from_dict(json.loads(snapshot))
        self.project.path = path
        self.scene_index = min(self.scene_index, len(self.project.scenes) - 1)
        self.selected_id = ""
        self._mark_dirty()
        self._refresh_all()

    def undo(self) -> None:
        if self.undo_stack:
            self.redo_stack.append(json.dumps(self.project.to_dict(), ensure_ascii=False))
            self._restore(self.undo_stack.pop())

    def redo(self) -> None:
        if self.redo_stack:
            self.undo_stack.append(json.dumps(self.project.to_dict(), ensure_ascii=False))
            self._restore(self.redo_stack.pop())

    def _mark_dirty(self) -> None:
        self.dirty = True
        self._update_title()

    def _update_title(self) -> None:
        suffix = " *" if self.dirty else ""
        self.setWindowTitle(f"{self.project.name}{suffix} — AnimaTube")
        self.project_name.setText(self.project.name)

    def _refresh_all(self) -> None:
        self._refresh_scenes()
        self._refresh_layers()
        self._refresh_audio()
        self._refresh_canvas()
        self._refresh_inspector()
        self._update_title()

    def _refresh_scenes(self) -> None:
        self.scene_list.blockSignals(True)
        self.scene_list.clear()
        for index, scene in enumerate(self.project.scenes):
            self.scene_list.addItem(f"{index + 1:02d}  {scene.name}")
        self.scene_index = min(max(0, self.scene_index), len(self.project.scenes) - 1)
        self.scene_list.setCurrentRow(self.scene_index)
        self.scene_list.blockSignals(False)
        if self.project.scenes:
            scene = self.project.scenes[self.scene_index]
            for control in (self.transition, self.transition_length, self.scene_duration):
                control.blockSignals(True)
            self.transition.setCurrentText(scene.transition)
            self.transition_length.setValue(scene.transition_duration)
            self.scene_duration.setValue(scene.duration)
            self.transition.blockSignals(False)
            self.transition_length.blockSignals(False)
            self.scene_duration.blockSignals(False)
            self.frame_slider.setMaximum(max(0, scene.duration - 1))
            self.frame = min(self.frame, scene.duration - 1)
            self.frame_slider.setValue(self.frame)

    def _refresh_layers(self) -> None:
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        if self.project.scenes:
            for layer in reversed(self.project.scenes[self.scene_index].objects):
                item = QListWidgetItem(layer.name)
                item.setData(Qt.ItemDataRole.UserRole, layer.id)
                self.layer_list.addItem(item)
                if layer.id == self.selected_id:
                    self.layer_list.setCurrentItem(item)
        self.layer_list.blockSignals(False)

    def _refresh_audio(self) -> None:
        self.audio_list.blockSignals(True)
        self.audio_list.clear()
        for track in self.project.audio_tracks:
            item = QListWidgetItem(f"♫  {track.name}")
            item.setData(Qt.ItemDataRole.UserRole, track.id)
            self.audio_list.addItem(item)
            if track.id == self.selected_audio_id:
                self.audio_list.setCurrentItem(item)
        self.audio_list.blockSignals(False)
        selected = self._selected_audio()
        self._inspectors_loading = True
        for control in (self.audio_volume, self.audio_start, self.fade_in, self.fade_out):
            control.setEnabled(bool(selected))
        if selected:
            self.audio_volume.setValue(selected.volume)
            self.audio_start.setValue(selected.start)
            self.fade_in.setValue(selected.fade_in)
            self.fade_out.setValue(selected.fade_out)
        self._inspectors_loading = False

    def _refresh_canvas(self) -> None:
        if self.project.scenes:
            self.canvas.set_view(self.project, self.scene_index, self.frame, self.selected_id)
            self.frame_label.setText(f"Frame {self.frame} / {self.project.scenes[self.scene_index].duration - 1}")

    def _selected_layer(self) -> LayerObject | None:
        if not self.project.scenes:
            return None
        return next((layer for layer in self.project.scenes[self.scene_index].objects if layer.id == self.selected_id), None)

    def _selected_audio(self) -> AudioTrack | None:
        return next((track for track in self.project.audio_tracks if track.id == self.selected_audio_id), None)

    def _refresh_inspector(self) -> None:
        layer = self._selected_layer()
        self.inspector_stack.setCurrentIndex(1 if layer else 0)
        if not layer:
            return
        self._inspectors_loading = True
        state = state_at(layer, self.frame)
        self.layer_name.setText(layer.name)
        self.text_value.setVisible(layer.kind == "text")
        self.text_value.setPlainText(layer.text)
        values = {"x": state["x"], "y": state["y"], "width": layer.width, "height": layer.height,
                  "scale": state["scale"], "rotation": state["rotation"], "opacity": state["opacity"]}
        for name, control in self.property_controls.items():
            control.setValue(values[name])
            control.setEnabled(name not in ("width", "height") or layer.kind not in ("image", "character"))
        self.color_button.setVisible(layer.kind in ("text", "rect", "ellipse", "triangle"))
        self.color_button.setStyleSheet(f"background:{layer.color};color:#111;border:0;padding:8px")
        self._inspectors_loading = False

    def _select_scene(self, index: int) -> None:
        if index < 0 or index >= len(self.project.scenes):
            return
        self.scene_index, self.frame, self.selected_id = index, 0, ""
        self._refresh_scenes()
        self._refresh_layers()
        self._refresh_canvas()
        self._refresh_inspector()

    def _select_layer(self, current, previous=None) -> None:
        self.selected_id = current.data(Qt.ItemDataRole.UserRole) if current else ""
        self._refresh_canvas()
        self._refresh_inspector()

    def _select_audio(self, row: int) -> None:
        item = self.audio_list.item(row) if row >= 0 else None
        self.selected_audio_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        self._refresh_audio()

    def _set_frame(self, frame: int) -> None:
        self.frame = frame
        self._refresh_canvas()
        self._refresh_inspector()

    def _set_transition(self, value: str) -> None:
        if not self._inspectors_loading:
            self._snapshot()
            self.project.scenes[self.scene_index].transition = value
            self._mark_dirty()

    def _set_transition_length(self, value: int) -> None:
        if not self._inspectors_loading:
            self._snapshot()
            self.project.scenes[self.scene_index].transition_duration = value
            self._mark_dirty()

    def _set_scene_duration(self, value: int) -> None:
        if not self._inspectors_loading:
            self._snapshot()
            self.project.scenes[self.scene_index].duration = value
            self.frame = min(self.frame, value - 1)
            self._mark_dirty()
            self._refresh_scenes()
            self._refresh_canvas()

    def _begin_canvas_move(self, layer_id: str) -> None:
        self.selected_id = layer_id
        self._snapshot()
        self._refresh_layers()
        self._refresh_inspector()

    def _move_layer(self, layer_id: str, x: float, y: float) -> None:
        layer = next((obj for obj in self.project.scenes[self.scene_index].objects if obj.id == layer_id), None)
        if layer:
            if self.frame == 0 and not layer.keyframes:
                layer.x, layer.y = x, y
            else:
                self._store_keyframe_value(layer, "x", x)
                self._store_keyframe_value(layer, "y", y)
            self._mark_dirty()
            self._refresh_canvas()

    def _edit_layer_name(self) -> None:
        layer = self._selected_layer()
        if layer and self.layer_name.text().strip() and layer.name != self.layer_name.text().strip():
            self._snapshot()
            layer.name = self.layer_name.text().strip()
            self._mark_dirty()
            self._refresh_layers()

    def _edit_layer_text(self) -> None:
        layer = self._selected_layer()
        if layer and layer.kind == "text" and not self._inspectors_loading and layer.text != self.text_value.toPlainText():
            self._snapshot()
            layer.text = self.text_value.toPlainText()
            self._mark_dirty()
            self._refresh_canvas()

    def _edit_property(self, key: str, value: float) -> None:
        if self._inspectors_loading:
            return
        layer = self._selected_layer()
        if not layer:
            return
        self._snapshot()
        if key in ("width", "height"):
            setattr(layer, key, value)
        elif self.frame == 0 and not layer.keyframes:
            setattr(layer, key, value)
        else:
            self._store_keyframe_value(layer, key, value)
        self._mark_dirty()
        self._refresh_canvas()

    def _store_keyframe_value(self, layer: LayerObject, field: str, value: float) -> None:
        key = next((keyframe for keyframe in layer.keyframes if keyframe.frame == self.frame), None)
        state = state_at(layer, self.frame)
        if key is None:
            key = Keyframe(
                frame=self.frame, x=state["x"], y=state["y"], scale=state["scale"],
                rotation=state["rotation"], opacity=state["opacity"],
                text_progress=state.get("text_progress", 1), easing=self.easing.currentText(),
            )
            layer.keyframes.append(key)
        setattr(key, field, value)
        layer.keyframes.sort(key=lambda item: item.frame)

    def _edit_audio(self, field: str, value: float) -> None:
        if self._inspectors_loading:
            return
        track = self._selected_audio()
        if track:
            self._snapshot()
            setattr(track, field, value)
            self._mark_dirty()

    def _change_audio_volume(self, value: float) -> None:
        self._edit_audio("volume", value)

    def _change_audio_start(self, value: float) -> None:
        self._edit_audio("start", value)

    def _change_audio_fades(self, _value: float) -> None:
        if not self._inspectors_loading and self._selected_audio():
            self._snapshot()
            track = self._selected_audio()
            track.fade_in, track.fade_out = self.fade_in.value(), self.fade_out.value()
            self._mark_dirty()

    def choose_color(self) -> None:
        layer = self._selected_layer()
        if layer:
            color = QColorDialog.getColor(QColor(layer.color), self, "Layer color")
            if color.isValid():
                self._snapshot()
                layer.color = color.name()
                self._mark_dirty()
                self._refresh_inspector()
                self._refresh_canvas()

    def add_text(self) -> None:
        self._snapshot()
        self._add_layer(LayerObject(kind="text", name="Text", x=self.project.width * .2, y=self.project.height * .38,
                                    width=self.project.width * .6, height=self.project.height * .2,
                                    text="Your text", font_size=max(30, self.project.height // 20)))

    def add_shape(self, kind: str) -> None:
        self._snapshot()
        size = min(self.project.width, self.project.height) * .18
        self._add_layer(LayerObject(kind=kind, name=kind.title(), x=(self.project.width - size) / 2,
                                    y=(self.project.height - size) / 2, width=size, height=size, color="#7c6cff"))

    def add_character(self) -> None:
        self._snapshot()
        width, height = self.project.width * .18, self.project.height * .55
        self._add_layer(LayerObject(kind="character", name="Character", x=self.project.width * .4,
                                    y=self.project.height * .25, width=width, height=height))

    def _add_layer(self, layer: LayerObject) -> None:
        self.project.scenes[self.scene_index].objects.append(layer)
        self.selected_id = layer.id
        self._mark_dirty()
        self._refresh_layers()
        self._refresh_canvas()
        self._refresh_inspector()

    def delete_layer(self) -> None:
        layer = self._selected_layer()
        if layer:
            self._snapshot()
            self.project.scenes[self.scene_index].objects.remove(layer)
            self.selected_id = ""
            self._mark_dirty()
            self._refresh_layers()
            self._refresh_canvas()
            self._refresh_inspector()

    def add_keyframe(self) -> None:
        layer = self._selected_layer()
        if not layer:
            self.statusBar().showMessage("Select a layer before adding a keyframe.", 4000)
            return
        self._snapshot()
        state = state_at(layer, self.frame)
        layer.keyframes = [item for item in layer.keyframes if item.frame != self.frame]
        layer.keyframes.append(Keyframe(frame=self.frame, x=state["x"], y=state["y"], scale=state["scale"],
                                        rotation=state["rotation"], opacity=state["opacity"],
                                        text_progress=state.get("text_progress", 1), easing=self.easing.currentText()))
        layer.keyframes.sort(key=lambda item: item.frame)
        self._mark_dirty()
        self.statusBar().showMessage(f"Keyframe added at frame {self.frame}.", 3000)

    def apply_preset(self) -> None:
        layer = self._selected_layer()
        if not layer:
            return
        self._snapshot()
        start, end = self.frame, min(self.project.scenes[self.scene_index].duration - 1, self.frame + self.project.fps)
        if end == start:
            QMessageBox.information(self, "Animation preset", "Move the playhead earlier or increase the scene duration to apply an animation.")
            return
        current = state_at(layer, start)
        final = dict(current)
        if self.preset.currentText() == "fade in":
            current["opacity"], final["opacity"] = 0, 1
        elif self.preset.currentText() == "fade out":
            current["opacity"], final["opacity"] = 1, 0
        elif self.preset.currentText() == "slide in":
            current["x"] += self.project.width * .2
            final["x"] = layer.x
        elif self.preset.currentText() == "bounce":
            current["y"] -= self.project.height * .12
            final["y"] = layer.y
        elif self.preset.currentText() == "zoom":
            current["scale"], final["scale"] = .1, 1
        elif self.preset.currentText() == "typewriter" and layer.kind == "text":
            current["text_progress"], final["text_progress"] = 0, 1
        else:
            QMessageBox.information(self, "Typewriter animation", "Typewriter is available for text layers only.")
            return
        layer.keyframes = [key for key in layer.keyframes if key.frame not in (start, end)]
        for frame, state in ((start, current), (end, final)):
            layer.keyframes.append(Keyframe(
                frame=frame, x=state["x"], y=state["y"], scale=state["scale"],
                rotation=state["rotation"], opacity=state["opacity"],
                text_progress=state.get("text_progress", 1), easing=self.easing.currentText(),
            ))
        layer.keyframes.sort(key=lambda item: item.frame)
        self._mark_dirty()
        self._refresh_canvas()
        self._refresh_inspector()

    def _drop_asset(self, path: str, x: float, y: float) -> None:
        if path and Path(path).suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".gif", ".bmp", ".webp"):
            self._import_image_path(path, x, y)
        elif path:
            self._import_audio_path(path)

    def import_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import image or animation", "", "Images (*.png *.jpg *.jpeg *.svg *.gif *.bmp *.webp)")
        if path:
            self._import_image_path(path, self.project.width * .3, self.project.height * .3)

    def _import_image_path(self, path: str, x: float, y: float) -> None:
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Import failed", f"Could not read this image. Check the file or install Qt SVG support.\n\n{path}")
            return
        self._snapshot()
        self._add_layer(LayerObject(kind="image", name=Path(path).stem, x=x, y=y,
                                    width=min(image.width(), self.project.width * .45),
                                    height=min(image.height(), self.project.height * .45), asset_path=path))

    def import_audio(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Import audio tracks", "", "Audio (*.wav *.mp3 *.m4a *.aac *.ogg *.flac)")
        for path in paths:
            self._import_audio_path(path)

    def _import_audio_path(self, path: str) -> None:
        if not Path(path).is_file():
            QMessageBox.warning(self, "Audio import failed", f"Audio file not found: {path}")
            return
        self._snapshot()
        track = AudioTrack(name=Path(path).name, path=path)
        self.project.audio_tracks.append(track)
        self.selected_audio_id = track.id
        self._mark_dirty()
        self._refresh_audio()

    def record_audio(self) -> None:
        output, _ = QFileDialog.getSaveFileName(self, "Save voice-over", "voice-over.wav", "WAV audio (*.wav)")
        if not output:
            return
        if not output.lower().endswith(".wav"):
            output += ".wav"
        try:
            dialog = VoiceRecorderDialog(output, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and Path(output).is_file():
                self._import_audio_path(output)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Recording unavailable", str(exc))

    def text_to_speech(self) -> None:
        text, ok = QInputDialog.getMultiLineText(self, "Text to speech", "Narration")
        if not ok or not text.strip():
            return
        output, _ = QFileDialog.getSaveFileName(self, "Save narration", "narration.wav", "WAV audio (*.wav)")
        if not output:
            return
        if not output.lower().endswith(".wav"):
            output += ".wav"
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.save_to_file(text, output)
            engine.runAndWait()
            engine.stop()
            if not Path(output).is_file():
                raise RuntimeError("The speech engine did not create an audio file.")
            self._import_audio_path(output)
        except Exception as exc:
            QMessageBox.critical(self, "Text to speech failed", f"Could not generate narration: {exc}")

    def remove_audio(self) -> None:
        track = self._selected_audio()
        if track:
            self._snapshot()
            self.project.audio_tracks.remove(track)
            self.selected_audio_id = ""
            self._mark_dirty()
            self._refresh_audio()

    def add_scene(self) -> None:
        self._snapshot()
        self.project.scenes.append(Scene(name=f"Scene {len(self.project.scenes) + 1}"))
        self.scene_index = len(self.project.scenes) - 1
        self.frame = 0
        self._mark_dirty()
        self._refresh_all()

    def duplicate_scene(self) -> None:
        source = self.project.scenes[self.scene_index]
        clone = Scene.from_dict(json.loads(json.dumps(source, default=lambda value: value.__dict__)))
        clone.id = uuid4().hex
        for layer in clone.objects:
            layer.id = uuid4().hex
        clone.name = f"{source.name} copy"
        self._snapshot()
        self.project.scenes.insert(self.scene_index + 1, clone)
        self.scene_index += 1
        self._mark_dirty()
        self._refresh_all()

    def delete_scene(self) -> None:
        if len(self.project.scenes) <= 1:
            QMessageBox.information(self, "Delete scene", "A project must have at least one scene.")
            return
        self._snapshot()
        del self.project.scenes[self.scene_index]
        self.scene_index = max(0, self.scene_index - 1)
        self._mark_dirty()
        self._refresh_all()

    def move_scene(self, offset: int) -> None:
        destination = self.scene_index + offset
        if 0 <= destination < len(self.project.scenes):
            self._snapshot()
            self.project.scenes[self.scene_index], self.project.scenes[destination] = (
                self.project.scenes[destination], self.project.scenes[self.scene_index]
            )
            self.scene_index = destination
            self._mark_dirty()
            self._refresh_all()

    def _reorder_layers(self, *args) -> None:
        if self.layer_list.count() != len(self.project.scenes[self.scene_index].objects):
            return
        order = [self.layer_list.item(index).data(Qt.ItemDataRole.UserRole) for index in reversed(range(self.layer_list.count()))]
        layers = {layer.id: layer for layer in self.project.scenes[self.scene_index].objects}
        if set(order) == set(layers):
            self._snapshot()
            self.project.scenes[self.scene_index].objects = [layers[layer_id] for layer_id in order]
            self._mark_dirty()
            self._refresh_canvas()

    def new_project(self) -> None:
        if self.dirty and QMessageBox.question(self, "New project", "Discard unsaved project changes?") != QMessageBox.StandardButton.Yes:
            return
        self.project = Project()
        self.scene_index = self.frame = 0
        self.selected_id = self.selected_audio_id = ""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self._refresh_all()

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open AnimaTube project", "", "AnimaTube project (*.anima)")
        if not path:
            return
        try:
            project = load_project(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self.project = project
        self.scene_index = self.frame = 0
        self.selected_id = self.selected_audio_id = ""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self._refresh_all()
        self.statusBar().showMessage(f"Opened {path}", 4000)

    def save_project_dialog(self) -> bool:
        path = self.project.path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Save AnimaTube project", f"{self.project.name}.anima", "AnimaTube project (*.anima)")
        if not path:
            return False
        if not path.lower().endswith(".anima"):
            path += ".anima"
        try:
            save_project(self.project, path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        self.dirty = False
        self._update_title()
        self.statusBar().showMessage(f"Saved {path}", 4000)
        return True

    def _autosave(self) -> None:
        if not self.dirty:
            return
        path = Path.home() / ".animatube" / "autosave.anima"
        try:
            snapshot = Project.from_dict(self.project.to_dict())
            snapshot.path = self.project.path
            save_project(snapshot, path)
            self.statusBar().showMessage(f"Autosaved recovery copy: {path}", 5000)
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"Autosave failed: {exc}", 10000)

    def _rename_project(self) -> None:
        name = self.project_name.text().strip()
        if name and name != self.project.name:
            self._snapshot()
            self.project.name = name
            self._mark_dirty()

    def project_settings(self) -> None:
        dialog = ExportOptionsDialog(self, self.project)
        dialog.setWindowTitle("Project settings")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dimensions, fps = dialog.output_settings()
            self._snapshot()
            self.project.width, self.project.height = dimensions
            self.project.fps = fps
            self._mark_dirty()
            self._refresh_canvas()

    def toggle_playback(self) -> None:
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.play_button.setText("▶ Play")
        else:
            self.play_timer.start(round(1000 / self.project.fps))
            self.play_button.setText("⏸ Pause")

    def _tick(self) -> None:
        if self.frame + 1 >= self.project.scenes[self.scene_index].duration:
            self.frame = 0
        else:
            self.frame += 1
        self.frame_slider.setValue(self.frame)

    def export_video(self) -> None:
        dialog = ExportOptionsDialog(self, self.project)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dimensions, fps = dialog.output_settings()
        output, _ = QFileDialog.getSaveFileName(self, "Export MP4", f"{self.project.name}.mp4", "MP4 video (*.mp4)")
        if not output:
            return
        if not output.lower().endswith(".mp4"):
            output += ".mp4"
        snapshot = Project.from_dict(self.project.to_dict())
        snapshot.path = self.project.path
        self._run_task("Exporting video", lambda progress: render_project(snapshot, output, resolution=dimensions, fps=fps, progress=progress),
                       lambda result: self._export_done(output))

    def _export_done(self, output: str) -> None:
        self.last_export_path = output
        QMessageBox.information(self, "Export complete", f"Video exported successfully:\n{output}")

    def upload_video(self) -> None:
        dialog = UploadDialog(self, self.last_export_path)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.upload_values()
        if not values["title"] or not values["video_path"]:
            QMessageBox.warning(self, "Upload details", "A rendered video and title are required.")
            return
        def upload(progress):
            from animatube.youtube.uploader import authenticate, upload_video as send_video
            service = authenticate(values["oauth_path"])
            return send_video(service, values["video_path"], title=values["title"],
                              description=values["description"], tags=values["tags"],
                              category_id=values["category_id"], privacy=values["privacy"],
                              thumbnail_path=values["thumbnail_path"], publish_at=values["publish_at"],
                              progress=lambda percent: progress(percent, "Uploading to YouTube"))
        self._run_task("Uploading to YouTube", upload, self._upload_done)

    def _upload_done(self, url: str) -> None:
        QMessageBox.information(self, "Upload complete", f"Your video is available at:\n{url}")

    def _run_task(self, title: str, task: Callable, success: Callable) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Please wait", "Another export or upload is already in progress.")
            return
        self.busy_dialog = BusyDialog(title, self)
        self.worker = TaskWorker(task, self)
        self.worker.progress.connect(self.busy_dialog.update_progress)
        self.worker.succeeded.connect(lambda result: self._task_succeeded(success, result))
        self.worker.failed.connect(self._task_failed)
        self.worker.start()
        self.busy_dialog.show()

    def _task_succeeded(self, callback: Callable, result) -> None:
        if self.busy_dialog:
            self.busy_dialog.close()
        callback(result)

    def _task_failed(self, message: str) -> None:
        if self.busy_dialog:
            self.busy_dialog.close()
        QMessageBox.critical(self, "Operation failed", message)

    def closeEvent(self, event) -> None:
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Operation in progress", "Wait for the export or upload to finish before closing AnimaTube.")
            event.ignore()
            return
        if self.dirty and QMessageBox.question(self, "Unsaved changes", "Save the current project before closing?") == QMessageBox.StandardButton.Yes:
            if not self.save_project_dialog():
                event.ignore()
                return
        event.accept()


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AnimaTube")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    return app.exec()

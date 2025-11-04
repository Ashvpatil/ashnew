"""Reusable control panels for the GUI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..engine.game import Move


class AISettingsPanel(QGroupBox):
    engine_changed = Signal(str)
    settings_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Spoiler AI")
        layout = QFormLayout(self)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["Alpha-Beta", "MCTS", "Hybrid"])
        self.engine_combo.currentTextChanged.connect(self.engine_changed.emit)
        layout.addRow("Engine", self.engine_combo)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 8)
        self.depth_spin.setValue(4)
        self.depth_spin.valueChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addRow("Depth", self.depth_spin)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(500, 10000)
        self.time_spin.setSingleStep(250)
        self.time_spin.setValue(2500)
        self.time_spin.valueChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addRow("Iter ms", self.time_spin)

        self.rollout_spin = QSpinBox()
        self.rollout_spin.setRange(100, 5000)
        self.rollout_spin.setSingleStep(100)
        self.rollout_spin.setValue(800)
        self.rollout_spin.valueChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addRow("Rollouts", self.rollout_spin)

        self.playout_spin = QSpinBox()
        self.playout_spin.setRange(2, 30)
        self.playout_spin.setValue(10)
        self.playout_spin.valueChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addRow("Playout depth", self.playout_spin)

        self.c_puct_spin = QDoubleSpinBox()
        self.c_puct_spin.setRange(0.1, 5.0)
        self.c_puct_spin.setSingleStep(0.1)
        self.c_puct_spin.setValue(1.4)
        self.c_puct_spin.valueChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addRow("c_puct", self.c_puct_spin)

    def current_engine(self) -> str:
        return self.engine_combo.currentText()

    def current_settings(self) -> dict:
        return {
            "depth": self.depth_spin.value(),
            "iter_ms": self.time_spin.value(),
            "rollouts": self.rollout_spin.value(),
            "playout": self.playout_spin.value(),
            "c_puct": self.c_puct_spin.value(),
        }


class RulePanel(QGroupBox):
    rules_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Rules & Variants")
        layout = QFormLayout(self)
        self.backward_box = QCheckBox("Allow backward moves")
        self.backward_box.setChecked(True)
        self.backward_box.stateChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow(self.backward_box)

        self.jump_box = QCheckBox("Allow jump moves")
        self.jump_box.setChecked(True)
        self.jump_box.stateChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow(self.jump_box)

        self.force_combo = QComboBox()
        self.force_combo.addItems(["Free", "Graph A", "Graph B"])
        self.force_combo.currentTextChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow("Force side", self.force_combo)

        self.mirror_box = QCheckBox("Mirror mode (alternate sides)")
        self.mirror_box.stateChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow(self.mirror_box)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(0, 10)
        self.cooldown_spin.setValue(0)
        self.cooldown_spin.valueChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow("Jump cooldown", self.cooldown_spin)

        self.jump_limit_spin = QSpinBox()
        self.jump_limit_spin.setRange(0, 10)
        self.jump_limit_spin.setValue(0)
        self.jump_limit_spin.valueChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow("Jump limit", self.jump_limit_spin)

        self.jump_window_spin = QSpinBox()
        self.jump_window_spin.setRange(0, 10)
        self.jump_window_spin.setValue(0)
        self.jump_window_spin.valueChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow("Jump window", self.jump_window_spin)

        self.round_limit_spin = QSpinBox()
        self.round_limit_spin.setRange(0, 200)
        self.round_limit_spin.setValue(0)
        self.round_limit_spin.valueChanged.connect(lambda *_: self.rules_changed.emit())
        layout.addRow("Round limit", self.round_limit_spin)

    def current_rules(self) -> dict:
        force_map = {"Free": None, "Graph A": "A", "Graph B": "B"}
        return {
            "allow_backward": self.backward_box.isChecked(),
            "allow_jump": self.jump_box.isChecked(),
            "force_same_graph": force_map[self.force_combo.currentText()],
            "jump_cooldown": self.cooldown_spin.value(),
            "jump_limit": self.jump_limit_spin.value() or None,
            "jump_window": self.jump_window_spin.value(),
            "round_limit": self.round_limit_spin.value() or None,
            "mirror_mode": self.mirror_box.isChecked(),
        }


class OverlayPanel(QGroupBox):
    settings_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Overlays")
        layout = QVBoxLayout(self)
        self.pv_box = QCheckBox("Show principal variation")
        self.pv_box.setChecked(True)
        self.pv_box.stateChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addWidget(self.pv_box)

        self.heat_box = QCheckBox("Show MCTS heatmap")
        self.heat_box.setChecked(True)
        self.heat_box.stateChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addWidget(self.heat_box)

        self.high_contrast = QCheckBox("High contrast mode")
        self.high_contrast.stateChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addWidget(self.high_contrast)

        self.colorblind = QCheckBox("Colorblind-safe palette")
        self.colorblind.stateChanged.connect(lambda *_: self.settings_changed.emit())
        layout.addWidget(self.colorblind)

    def overlay_state(self) -> dict:
        return {
            "pv": self.pv_box.isChecked(),
            "heat": self.heat_box.isChecked(),
            "high_contrast": self.high_contrast.isChecked(),
            "colorblind": self.colorblind.isChecked(),
        }


class HintPanel(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("Legal replies")
        self.layout = QVBoxLayout(self)
        self.summary = QLabel("Spoiler to move")
        self.layout.addWidget(self.summary)
        self.button_container = QWidget()
        self.button_layout = QHBoxLayout(self.button_container)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(6)
        self.layout.addWidget(self.button_container)
        self.buttons: List[QPushButton] = []

    def update_hints(self, moves: Iterable[Move], callback: Callable[[Move], None]) -> None:
        for button in self.buttons:
            button.deleteLater()
        self.buttons.clear()
        moves = list(moves)
        if not moves:
            self.summary.setText("Duplicator has no replies")
            return
        self.summary.setText(f"{len(moves)} replies available")
        for index, move in enumerate(moves, start=1):
            text = f"{index}. {move.graph} {move.move_type} → {move.target}"
            button = QPushButton(text)
            button.clicked.connect(lambda _, m=move: callback(m))
            button.setCheckable(False)
            self.button_layout.addWidget(button)
            self.buttons.append(button)

    def clear(self) -> None:
        self.update_hints([], lambda _: None)

"""Main Qt application for the Two-Way Global Bisimulation Game."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..analysis import bisim
from ..analysis.witness import export_witness_trace
from ..engine.ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from ..engine.ai.mcts import MCTSSpoiler, MCTSConfig
from ..engine.ai.tablebase import Tablebase
from ..engine.game import Move, Position, RuleSet, legal_responses, spoiler_legal_moves, step
from ..engine.graphs import DiGraph, load_graph_pair
from .graphview import GraphView
from .themes import DARK_PALETTE, HIGH_CONTRAST_PALETTE


@dataclass
class GameState:
    graph_a: DiGraph
    graph_b: DiGraph
    position: Position
    history: List[Move] = field(default_factory=list)
    reply_history: List[Move] = field(default_factory=list)
    position_stack: List[Position] = field(default_factory=list)
    redo_stack: List[Position] = field(default_factory=list)

    def push(self, position: Position) -> None:
        self.position_stack.append(position)
        self.position = position
        self.redo_stack.clear()

    def undo(self) -> Optional[Position]:
        if len(self.position_stack) <= 1:
            return None
        self.redo_stack.append(self.position_stack.pop())
        self.position = self.position_stack[-1]
        if self.reply_history:
            self.reply_history.pop()
        if self.history:
            self.history.pop()
        return self.position

    def redo(self) -> Optional[Position]:
        if not self.redo_stack:
            return None
        pos = self.redo_stack.pop()
        self.position_stack.append(pos)
        self.position = pos
        # redo does not recover move history for simplicity
        return pos


class SpoilerWorker(QObject):
    finished = Signal(Move, list, dict)
    failed = Signal(str)

    def __init__(self, ai_type: str, state: GameState, rules: RuleSet, depth: int, iters: int) -> None:
        super().__init__()
        self.ai_type = ai_type
        self.state = state
        self.rules = rules
        self.depth = depth
        self.iters = iters

    def run(self) -> None:
        try:
            if self.ai_type == "Alpha-Beta":
                spoiler = AlphaBetaSpoiler(self.state.graph_a, self.state.graph_b, self.rules, config=SearchConfig(depth=self.depth))
                result = spoiler.search(self.state.position)
                if result.best_move is None:
                    raise RuntimeError("No move found")
                pv_vertices = [result.best_move.target]
                heat_map = {"A": {}, "B": {}}
                self.finished.emit(result.best_move, pv_vertices, heat_map)
            else:
                spoiler = MCTSSpoiler(self.state.graph_a, self.state.graph_b, self.rules, config=MCTSConfig(iterations=self.iters))
                move = spoiler.run(self.state.position)
                heat_map = {"A": {}, "B": {}}
                for (va, vb), count in spoiler.visit_heat.items():
                    heat_map["A"][va] = heat_map["A"].get(va, 0) + count
                    heat_map["B"][vb] = heat_map["B"].get(vb, 0) + count
                self.finished.emit(move, [], heat_map)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class PlayTab(QWidget):
    spoiler_move = Signal(Move)
    duplicator_move = Signal(Move)

    def __init__(self, state: GameState, rules: RuleSet, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.rules = rules
        self.current_hints: List[Move] = []
        self.ai_type = "Alpha-Beta"
        self.depth = 3
        self.iters = 400
        self.tablebase = Tablebase()
        self.tablebase.build(state.graph_a, state.graph_b, rules, max_depth=3)
        self.thread: Optional[QThread] = None
        self.pv_enabled = True
        self.heat_enabled = True
        self._build_ui()
        self.hint_list.itemDoubleClicked.connect(lambda item: self.duplicator_select(self.hint_list.row(item)))

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        splitter = QSplitter()
        self.view_a = GraphView(self.state.graph_a)
        self.view_b = GraphView(self.state.graph_b)
        splitter.addWidget(self.view_a)
        splitter.addWidget(self.view_b)
        splitter.setSizes([600, 600])

        layout.addWidget(splitter, 0, 0, 1, 2)

        control_box = QGroupBox("Spoiler AI")
        control_layout = QVBoxLayout(control_box)

        self.ai_combo = QComboBox()
        self.ai_combo.addItems(["Alpha-Beta", "MCTS"])
        self.ai_combo.currentTextChanged.connect(self._ai_changed)
        control_layout.addWidget(QLabel("Engine"))
        control_layout.addWidget(self.ai_combo)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 7)
        self.depth_spin.setValue(self.depth)
        self.depth_spin.valueChanged.connect(lambda v: setattr(self, "depth", v))
        control_layout.addWidget(QLabel("Depth"))
        control_layout.addWidget(self.depth_spin)

        self.iter_spin = QSpinBox()
        self.iter_spin.setRange(100, 8000)
        self.iter_spin.setSingleStep(100)
        self.iter_spin.setValue(self.iters)
        self.iter_spin.valueChanged.connect(lambda v: setattr(self, "iters", v))
        control_layout.addWidget(QLabel("Iterations"))
        control_layout.addWidget(self.iter_spin)

        toggle_row = QHBoxLayout()
        self.pv_toggle = QCheckBox("Show PV")
        self.pv_toggle.setChecked(True)
        self.pv_toggle.stateChanged.connect(lambda state: setattr(self, "pv_enabled", bool(state)))
        self.heat_toggle = QCheckBox("Heatmap")
        self.heat_toggle.setChecked(True)
        self.heat_toggle.stateChanged.connect(lambda state: setattr(self, "heat_enabled", bool(state)))
        toggle_row.addWidget(self.pv_toggle)
        toggle_row.addWidget(self.heat_toggle)
        control_layout.addLayout(toggle_row)

        self.move_button = QPushButton("Spoiler Move [Space]")
        self.move_button.clicked.connect(self.request_spoiler_move)
        control_layout.addWidget(self.move_button)

        self.replay_button = QPushButton("Replay [R]")
        self.replay_button.clicked.connect(self.replay)
        control_layout.addWidget(self.replay_button)

        self.hint_label = QLabel("Legal replies")
        control_layout.addWidget(self.hint_label)
        self.hint_list = QListWidget()
        control_layout.addWidget(self.hint_list)
        self.hint_list.itemClicked.connect(lambda item: self.duplicator_select(self.hint_list.row(item)))

        layout.addWidget(control_box, 0, 2)

        self.status = QLabel("Ready")
        layout.addWidget(self.status, 1, 0, 1, 3)
        
    # ------------------------------------------------------------------
    def _ai_changed(self, name: str) -> None:
        self.ai_type = name

    def request_spoiler_move(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        moves = spoiler_legal_moves(self.state.graph_a, self.state.graph_b, self.state.position, self.rules)
        if not moves:
            QMessageBox.information(self, "Spoiler", "Spoiler has no moves. Duplicator survives!")
            return
        worker = SpoilerWorker(self.ai_type, self.state, self.rules, self.depth, self.iters)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_spoiler_move)
        worker.finished.connect(lambda *_: thread.quit())
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(lambda msg: QMessageBox.critical(self, "Error", msg))
        worker.failed.connect(lambda *_: thread.quit())
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.thread = thread
        thread.start()

    def _on_spoiler_move(self, move: Move, pv_vertices: List[str], heat: Dict[str, Dict[str, int]]) -> None:
        self.state.history.append(move)
        self.status.setText(f"Spoiler plays {move}")
        target_view = self.view_b if move.graph == "A" else self.view_a
        other_view = self.view_a if move.graph == "A" else self.view_b
        target_view.animate_move(move)
        other_view.animate_move(move)
        responses = legal_responses(self.state.graph_a, self.state.graph_b, self.state.position, move, self.rules)
        self.current_hints = responses
        self.hint_list.clear()
        for reply in responses:
            item = QListWidgetItem(str(reply))
            self.hint_list.addItem(item)
        hint_vertices = [reply.target for reply in responses]
        self.view_a.clear_hints()
        self.view_b.clear_hints()
        target_view.show_hints(hint_vertices)
        if self.pv_enabled:
            path = pv_vertices or hint_vertices
            target_view.set_pv(path)
        else:
            target_view.set_pv([])
            other_view.set_pv([])
        if self.heat_enabled:
            target_view.set_heatmap(heat["A"] if move.graph == "A" else heat["B"])
        else:
            target_view.clear_heatmap()
        self.spoiler_move.emit(move)

    def duplicator_select(self, index: int) -> None:
        if index < 0 or index >= len(self.current_hints):
            return
        reply = self.current_hints[index]
        self.state.reply_history.append(reply)
        new_pos = step(self.state.graph_a, self.state.graph_b, self.state.position, self.state.history[-1], reply)
        self.state.push(new_pos)
        self.view_a.centre_on_vertex(self.state.position.vertex_a)
        self.view_b.centre_on_vertex(self.state.position.vertex_b)
        self.view_a.clear_hints()
        self.view_b.clear_hints()
        self.hint_list.clear()
        self.status.setText(f"Duplicator plays {reply}")
        self.duplicator_move.emit(reply)

    def replay(self) -> None:
        if not self.state.history:
            return
        base_position = self.state.position_stack[0]
        self.state.position = base_position
        self.state.position_stack = [base_position]
        self.view_a.centre_on_vertex(base_position.vertex_a)
        self.view_b.centre_on_vertex(base_position.vertex_b)

        sequence = list(zip(self.state.history, self.state.reply_history))

        def play_next(index: int = 0) -> None:
            if index >= len(sequence):
                return
            move, reply = sequence[index]
            self.state.position = step(self.state.graph_a, self.state.graph_b, self.state.position, move, reply)
            self.view_a.animate_move(move)
            self.view_b.animate_move(move)
            self.view_a.centre_on_vertex(self.state.position.vertex_a)
            self.view_b.centre_on_vertex(self.state.position.vertex_b)
            QTimer.singleShot(600, lambda: play_next(index + 1))

        from PySide6.QtCore import QTimer

        play_next(0)


class AnalysisTab(QWidget):
    def __init__(self, state: GameState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.explainer = QTextEdit()
        self.explainer.setReadOnly(True)
        layout.addWidget(QLabel("Coach commentary"))
        layout.addWidget(self.explainer)

        self.partition_text = QTextEdit()
        self.partition_text.setReadOnly(True)
        layout.addWidget(QLabel("Signature partitions"))
        layout.addWidget(self.partition_text)

        self.export_button = QPushButton("Export witness trace")
        self.export_button.clicked.connect(self.export_witness)
        layout.addWidget(self.export_button)

        self.update_partitions()

    def update_partitions(self) -> None:
        parts_a = bisim.signature_partition(self.state.graph_a)
        parts_b = bisim.signature_partition(self.state.graph_b)
        lines = ["Graph A"]
        for cls, vertices in parts_a.items():
            lines.append(f"  Class {cls}: {', '.join(vertices)}")
        lines.append("Graph B")
        for cls, vertices in parts_b.items():
            lines.append(f"  Class {cls}: {', '.join(vertices)}")
        self.partition_text.setPlainText("\n".join(lines))

    def set_commentary(self, text: str) -> None:
        self.explainer.setPlainText(text)

    def export_witness(self) -> None:
        if not self.state.history:
            QMessageBox.information(self, "Witness", "No moves to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export witness", filter="JSON (*.json)")
        if not path:
            return
        export_witness_trace(path, self.state.history)


class RulesTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setMarkdown(
            """
            # Two-Way Global Bisimulation Game

            Spoiler chooses a graph (A or B) and a move type:
            - **Forward** follows an outgoing edge.
            - **Backward** follows an incoming edge.
            - **Jump** teleports to any vertex.

            Duplicator must mirror the move type on the *other* graph. If they
            cannot respond the game ends immediately and Spoiler wins. If the
            game can continue forever Duplicator survives.
            """
        )
        layout.addWidget(text)


class ExperimentsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.run_button = QPushButton("Run experiment")
        self.run_button.clicked.connect(self.run_experiment)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.run_button)
        layout.addWidget(self.output)

    def run_experiment(self) -> None:
        from ..experiments.run import run_match

        graph_path = Path("twgbg/puzzles/preset_games/sample_pair.json")
        graph_a, graph_b = load_graph_pair(str(graph_path))
        result = run_match(graph_a, graph_b, RuleSet(), 2, 2)
        self.output.setPlainText(str(result))


class MainWindow(QMainWindow):
    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state
        self.rules = RuleSet()
        self.setWindowTitle("Two-Way Global Bisimulation Game")
        self.resize(1400, 900)
        self.tabs = QTabWidget()
        self.play_tab = PlayTab(state, self.rules)
        self.analysis_tab = AnalysisTab(state)
        self.rules_tab = RulesTab()
        self.experiments_tab = ExperimentsTab()
        self.tabs.addTab(self.play_tab, "Play")
        self.tabs.addTab(self.rules_tab, "Rules")
        self.tabs.addTab(self.analysis_tab, "Analysis & Coach")
        self.tabs.addTab(self.experiments_tab, "Experiments")
        self.setCentralWidget(self.tabs)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.play_tab.spoiler_move.connect(self._on_spoiler_move)
        self.play_tab.duplicator_move.connect(self._on_dup_move)
        self._build_actions()
        self.high_contrast = False

    def _build_actions(self) -> None:
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_session)
        load_action = QAction("Load", self)
        load_action.setShortcut(QKeySequence.Open)
        load_action.triggered.connect(self.load_session)
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)
        theme_action = QAction("High contrast", self)
        theme_action.setShortcut("Shift+H")
        theme_action.triggered.connect(self.toggle_contrast)
        self.addAction(save_action)
        self.addAction(load_action)
        self.addAction(undo_action)
        self.addAction(redo_action)
        self.addAction(theme_action)
        space_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        space_shortcut.activated.connect(self.play_tab.request_spoiler_move)
        hint_shortcut = QShortcut(QKeySequence("H"), self)
        hint_shortcut.activated.connect(self._show_hints)
        replay_shortcut = QShortcut(QKeySequence("R"), self)
        replay_shortcut.activated.connect(self.play_tab.replay)
        pv_shortcut = QShortcut(QKeySequence("P"), self)
        pv_shortcut.activated.connect(lambda: self.play_tab.pv_toggle.setChecked(not self.play_tab.pv_toggle.isChecked()))
        heat_shortcut = QShortcut(QKeySequence("M"), self)
        heat_shortcut.activated.connect(lambda: self.play_tab.heat_toggle.setChecked(not self.play_tab.heat_toggle.isChecked()))

    def _show_hints(self) -> None:
        vertices = [reply.target for reply in self.play_tab.current_hints]
        if self.play_tab.state.history and self.play_tab.state.history[-1].graph == "A":
            self.play_tab.view_b.show_hints(vertices)
        else:
            self.play_tab.view_a.show_hints(vertices)

    def toggle_contrast(self) -> None:
        self.high_contrast = not self.high_contrast
        palette = HIGH_CONTRAST_PALETTE if self.high_contrast else DARK_PALETTE
        for view in (self.play_tab.view_a, self.play_tab.view_b):
            view.scene.palette = palette
            view.scene.setBackgroundBrush(palette.background)
            view.scene.reset_colours()

    def _on_spoiler_move(self, move: Move) -> None:
        self.statusBar().showMessage(f"Spoiler move: {move}")
        commentary = f"Spoiler chose {move.move_type} on graph {move.graph}."
        self.analysis_tab.set_commentary(commentary)

    def _on_dup_move(self, move: Move) -> None:
        self.statusBar().showMessage(f"Duplicator move: {move}")

    # Session management -------------------------------------------------
    def save_session(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save session", filter="JSON (*.json)")
        if not path:
            return
        data = {
            "position": {
                "a": self.state.position.vertex_a,
                "b": self.state.position.vertex_b,
            },
            "history": [move.__dict__ for move in self.state.history],
            "reply_history": [move.__dict__ for move in self.state.reply_history],
        }
        with open(path, "w", encoding="utf8") as fh:
            json.dump(data, fh, indent=2)

    def load_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load session", filter="JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf8") as fh:
            data = json.load(fh)
        self.state.position = Position(data["position"]["a"], data["position"]["b"])
        self.state.history = [Move(**move) for move in data.get("history", [])]
        self.state.reply_history = [Move(**move) for move in data.get("reply_history", [])]
        self.state.position_stack = [self.state.position]
        self.state.redo_stack.clear()
        self.statusBar().showMessage("Session loaded")

    def undo(self) -> None:
        pos = self.state.undo()
        if pos:
            self.play_tab.view_a.centre_on_vertex(pos.vertex_a)
            self.play_tab.view_b.centre_on_vertex(pos.vertex_b)
            self.statusBar().showMessage("Undo")

    def redo(self) -> None:
        pos = self.state.redo()
        if pos:
            self.play_tab.view_a.centre_on_vertex(pos.vertex_a)
            self.play_tab.view_b.centre_on_vertex(pos.vertex_b)
            self.statusBar().showMessage("Redo")


def load_default_state() -> GameState:
    graph_a = DiGraph.path(4, name="Graph A")
    graph_b = DiGraph.path(4, name="Graph B")
    position = Position("0", "0")
    state = GameState(graph_a, graph_b, position)
    state.push(position)
    return state


def main() -> None:
    app = QApplication(sys.argv)
    state = load_default_state()
    window = MainWindow(state)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

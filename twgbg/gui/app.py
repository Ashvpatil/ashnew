"""Main PySide6 application entry point."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..analysis import signature_partition
from ..analysis.witness import export_witness_trace
from ..engine.ai import AlphaBetaSpoiler, HybridSpoiler, MCTSSpoiler, MCTSConfig, SearchConfig, Tablebase
from ..engine.ai.hybrid import HybridConfig
from ..engine.ai.mcts import MCTSResult
from ..engine.game import Move, Position, RuleSet, legal_responses, spoiler_legal_moves, step
from ..engine.graphs import DiGraph, load_graph_pair
from .exporter import export_scene_png, export_scene_svg
from .graphview import GraphView
from .panels import AISettingsPanel, HintPanel, OverlayPanel, RulePanel
from .tutorial import TutorialWidget


@dataclass
class GameState:
    graph_a: DiGraph
    graph_b: DiGraph
    position: Position
    rules: RuleSet
    history: List[Move] = field(default_factory=list)
    replies: List[Move] = field(default_factory=list)
    stack: List[Position] = field(default_factory=list)
    redo_stack: List[Position] = field(default_factory=list)

    def push(self, position: Position) -> None:
        self.stack.append(position)
        self.position = position
        self.redo_stack.clear()

    def undo(self) -> Optional[Position]:
        if len(self.stack) <= 1:
            return None
        self.redo_stack.append(self.stack.pop())
        self.position = self.stack[-1]
        if self.history:
            self.history.pop()
        if self.replies:
            self.replies.pop()
        return self.position

    def redo(self) -> Optional[Position]:
        if not self.redo_stack:
            return None
        position = self.redo_stack.pop()
        self.stack.append(position)
        self.position = position
        return position


class SpoilerWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        engine: str,
        state: GameState,
        ai_settings: dict,
        tablebase: Tablebase,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.state = state
        self.ai_settings = ai_settings
        self.tablebase = tablebase

    def run(self) -> None:
        try:
            position = self.state.position
            rules = self.state.rules
            if self.engine == "Alpha-Beta":
                config = SearchConfig(
                    depth=self.ai_settings["depth"],
                    time_budget_ms=self.ai_settings["iter_ms"],
                    iterative_deepening=True,
                )
                spoiler = AlphaBetaSpoiler(
                    self.state.graph_a,
                    self.state.graph_b,
                    rules,
                    tablebase=self.tablebase,
                    config=config,
                )
                result = spoiler.search(position)
                if result.best_move is None:
                    raise RuntimeError("Spoiler found no legal move")
                pv_vertices = [mv.target for mv in result.principal_variation if mv]
                data = {
                    "move": result.best_move,
                    "pv": pv_vertices,
                    "heat": {"A": {}, "B": {}},
                    "value": result.value,
                }
            elif self.engine == "MCTS":
                config = MCTSConfig(
                    rollouts=self.ai_settings["rollouts"],
                    playout_depth=self.ai_settings["playout"],
                    c_puct=self.ai_settings["c_puct"],
                )
                spoiler = MCTSSpoiler(self.state.graph_a, self.state.graph_b, rules, config=config)
                mcts_result: MCTSResult = spoiler.run(position)
                data = {
                    "move": mcts_result.best_move,
                    "pv": [mv.target for mv in mcts_result.principal_variation],
                    "heat": mcts_result.visit_heat,
                    "value": 0.0,
                }
            else:
                config = HybridConfig(
                    alphabeta_depth=self.ai_settings["depth"],
                    alphabeta_time_ms=self.ai_settings["iter_ms"],
                    mcts_rollouts=self.ai_settings["rollouts"],
                    mcts_playout_depth=self.ai_settings["playout"],
                    c_puct=self.ai_settings["c_puct"],
                )
                spoiler = HybridSpoiler(self.state.graph_a, self.state.graph_b, rules, config=config)
                result = spoiler.choose(position)
                data = {
                    "move": result.best_move,
                    "pv": [mv.target for mv in result.pv],
                    "heat": result.heat,
                    "value": result.value,
                }
            alternatives = self._alternatives(position, rules)
            data["alternatives"] = alternatives
            self.finished.emit(data)
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(str(exc))

    def _alternatives(self, position: Position, rules: RuleSet) -> List[str]:
        lines: List[str] = []
        moves = spoiler_legal_moves(self.state.graph_a, self.state.graph_b, position, rules)
        scored = []
        for move in moves:
            replies = legal_responses(self.state.graph_a, self.state.graph_b, position, move, rules)
            scored.append((len(replies), move))
        scored.sort(key=lambda item: item[0])
        for count, move in scored[:5]:
            lines.append(f"{move.move_type} on {move.graph}: {count} replies")
        return lines


class PlayTab(QWidget):
    spoiler_move = Signal(Move)
    duplicator_move = Signal(Move)
    commentary_ready = Signal(str, List[str])

    def __init__(self, state: GameState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self.tablebase = Tablebase()
        self.tablebase.build(state.graph_a, state.graph_b, state.rules, max_depth=3)
        self.thread: Optional[QThread] = None
        self.current_responses: List[Move] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        self.splitter = QSplitter()
        self.view_a = GraphView(self.state.graph_a)
        self.view_b = GraphView(self.state.graph_b)
        self.splitter.addWidget(self.view_a)
        self.splitter.addWidget(self.view_b)
        self.splitter.setSizes([600, 600])
        layout.addWidget(self.splitter, 0, 0)

        sidebar = QVBoxLayout()
        self.ai_panel = AISettingsPanel()
        self.rules_panel = RulePanel()
        self.overlay_panel = OverlayPanel()
        self.hint_panel = HintPanel()

        for panel in (self.ai_panel, self.rules_panel, self.overlay_panel, self.hint_panel):
            box = QGroupBox()
            box_layout = QVBoxLayout(box)
            box_layout.addWidget(panel)
            sidebar.addWidget(box)

        sidebar.addStretch(1)
        container = QWidget()
        container.setLayout(sidebar)
        layout.addWidget(container, 0, 1)

        self.move_button = QPushButton("Spoiler move [Space]")
        self.move_button.clicked.connect(self.request_spoiler_move)
        layout.addWidget(self.move_button, 1, 0)
        self.replay_button = QPushButton("Replay history [R]")
        layout.addWidget(self.replay_button, 1, 1)

        self.rules_panel.rules_changed.connect(self._update_rules)
        self.overlay_panel.settings_changed.connect(self._update_overlays)
        self.hint_panel.clear()

        self.replay_button.clicked.connect(self.replay)

    # ------------------------------------------------------------------
    def reset_graphs(self, graph_a: DiGraph, graph_b: DiGraph) -> None:
        self.state.graph_a = graph_a
        self.state.graph_b = graph_b
        self.splitter.widget(0).deleteLater()
        self.splitter.widget(0).deleteLater()
        self.view_a = GraphView(graph_a)
        self.view_b = GraphView(graph_b)
        self.splitter.insertWidget(0, self.view_a)
        self.splitter.insertWidget(1, self.view_b)
        self.hint_panel.clear()
        self.current_responses = []

    def request_spoiler_move(self) -> None:
        if self.thread and self.thread.isRunning():
            return
        worker = SpoilerWorker(
            self.ai_panel.current_engine(),
            self.state,
            self.ai_panel.current_settings(),
            self.tablebase,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_worker_done)
        worker.finished.connect(lambda *_: thread.quit())
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(self._on_worker_failed)
        worker.failed.connect(lambda *_: thread.quit())
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self.thread = thread
        thread.start()

    def _on_worker_done(self, payload: dict) -> None:
        move: Move = payload["move"]
        responses = legal_responses(self.state.graph_a, self.state.graph_b, self.state.position, move, self.state.rules)
        self.current_responses = responses
        self.state.history.append(move)
        self.view_a.animate_move(move)
        self.view_b.animate_move(move)
        self.view_a.centre_on(self.state.position.vertex_a)
        self.view_b.centre_on(self.state.position.vertex_b)
        if self.overlay_panel.overlay_state()["pv"]:
            target_view = self.view_a if move.graph == "A" else self.view_b
            target_view.set_pv([move.source] + payload["pv"])
        if self.overlay_panel.overlay_state()["heat"]:
            self.view_a.set_heatmap(payload["heat"].get("A", {}))
            self.view_b.set_heatmap(payload["heat"].get("B", {}))
        self.hint_panel.update_hints(responses, self.duplicator_select)
        hint_vertices = [reply.target for reply in responses]
        target_view = self.view_b if move.graph == "A" else self.view_a
        target_view.show_hints(hint_vertices)
        other_view = self.view_a if move.graph == "A" else self.view_b
        other_view.clear_hints()
        commentary = f"Spoiler plays {move.move_type} on graph {move.graph}, leaving {len(responses)} replies."
        self.commentary_ready.emit(commentary, payload.get("alternatives", []))
        self.spoiler_move.emit(move)

    def _on_worker_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Spoiler AI", message)

    def duplicator_select(self, move: Move) -> None:
        if move not in self.current_responses:
            return
        self.state.replies.append(move)
        new_position, alive, info = step(
            self.state.graph_a,
            self.state.graph_b,
            self.state.position,
            self.state.history[-1],
            move,
            self.state.rules,
        )
        self.state.push(new_position)
        self.view_a.centre_on(new_position.vertex_a)
        self.view_b.centre_on(new_position.vertex_b)
        self.view_a.clear_hints()
        self.view_b.clear_hints()
        self.hint_panel.clear()
        self.duplicator_move.emit(move)
        if not alive:
            if info.get("duplicator_survives"):
                QMessageBox.information(self, "Round limit", "Duplicator survives the set round limit!")
            else:
                QMessageBox.information(self, "Spoiler", "Spoiler wins the game.")

    def replay(self) -> None:
        if not self.state.history:
            return
        base = self.state.stack[0]
        self.state.position = base
        self.view_a.clear_hints()
        self.view_b.clear_hints()
        for move, reply in zip(self.state.history, self.state.replies):
            self.view_a.animate_move(move)
            self.view_b.animate_move(move)
            self.state.position = step(
                self.state.graph_a,
                self.state.graph_b,
                self.state.position,
                move,
                reply,
                self.state.rules,
            )[0]

    def _update_rules(self) -> None:
        settings = self.rules_panel.current_rules()
        self.state.rules = self.state.rules.with_toggle(**settings)

    def _update_overlays(self) -> None:
        state = self.overlay_panel.overlay_state()
        self.view_a.set_high_contrast(state["high_contrast"])
        self.view_b.set_high_contrast(state["high_contrast"])
        self.view_a.set_colorblind_safe(state["colorblind"])
        self.view_b.set_colorblind_safe(state["colorblind"])


class AnalysisTab(QWidget):
    def __init__(self, state: GameState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        layout = QVBoxLayout(self)
        self.commentary = QTextEdit()
        self.commentary.setReadOnly(True)
        layout.addWidget(QLabel("Coach commentary"))
        layout.addWidget(self.commentary)

        self.alternative_list = QTextEdit()
        self.alternative_list.setReadOnly(True)
        layout.addWidget(QLabel("Top alternatives"))
        layout.addWidget(self.alternative_list)

        self.partition = QTextEdit()
        self.partition.setReadOnly(True)
        layout.addWidget(QLabel("Signature partitions"))
        layout.addWidget(self.partition)
        self.update_partitions()

        self.export_button = QPushButton("Export witness trace")
        self.export_button.clicked.connect(self.export_witness)
        layout.addWidget(self.export_button)

    def set_commentary(self, text: str, alternatives: List[str]) -> None:
        self.commentary.setPlainText(text)
        self.alternative_list.setPlainText("\n".join(alternatives))

    def update_partitions(self) -> None:
        parts_a = signature_partition(self.state.graph_a)
        parts_b = signature_partition(self.state.graph_b)
        lines = ["Graph A"]
        for cluster, vertices in parts_a.items():
            lines.append(f"  Class {cluster}: {', '.join(vertices)}")
        lines.append("Graph B")
        for cluster, vertices in parts_b.items():
            lines.append(f"  Class {cluster}: {', '.join(vertices)}")
        self.partition.setPlainText("\n".join(lines))

    def export_witness(self) -> None:
        if not self.state.history:
            QMessageBox.information(self, "Witness", "No history to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export witness", filter="JSON (*.json)")
        if not path:
            return
        export_witness_trace(path, self.state.history)


class ExperimentsTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.run_button = QPushButton("Run hybrid 5-game experiment")
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.run_button)
        layout.addWidget(self.output)
        self.run_button.clicked.connect(self.run_experiment)

    def run_experiment(self) -> None:
        from ..experiments.run import main as run_main

        args = ["twgbg/puzzles/preset_games/sample_pair.json", "--games", "5", "--mode", "hybrid"]
        run_main(args)
        self.output.setPlainText("Experiment completed. Results saved to experiments.csv")


class MainWindow(QMainWindow):
    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state
        self.setWindowTitle("Two-Way Global Bisimulation Game")
        self.resize(1500, 950)
        self.tabs = QTabWidget()
        self.play_tab = PlayTab(state)
        self.analysis_tab = AnalysisTab(state)
        self.learn_tab = TutorialWidget()
        self.tabs.addTab(self.play_tab, "Play")
        self.tabs.addTab(self.learn_tab, "Learn")
        self.tabs.addTab(self.analysis_tab, "Analysis & Coach")
        self.tabs.addTab(ExperimentsTab(), "Experiments")
        self.setCentralWidget(self.tabs)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._build_toolbar()
        self.play_tab.commentary_ready.connect(self.analysis_tab.set_commentary)
        self.play_tab.spoiler_move.connect(lambda move: self.statusBar().showMessage(f"Spoiler played {move}"))
        self.play_tab.duplicator_move.connect(lambda move: self.statusBar().showMessage(f"Duplicator replied {move}"))

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction(QIcon.fromTheme("document-new"), "Load sample puzzle", self)
        new_action.triggered.connect(self.load_sample)
        toolbar.addAction(new_action)

        save_action = QAction(QIcon.fromTheme("document-save"), "Save session", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.save_session)
        toolbar.addAction(save_action)

        load_action = QAction(QIcon.fromTheme("document-open"), "Load session", self)
        load_action.setShortcut(QKeySequence.Open)
        load_action.triggered.connect(self.load_session)
        toolbar.addAction(load_action)

        export_png_action = QAction("Export PNG", self)
        export_png_action.triggered.connect(self.export_png)
        toolbar.addAction(export_png_action)

        export_svg_action = QAction("Export SVG", self)
        export_svg_action.triggered.connect(self.export_svg)
        toolbar.addAction(export_svg_action)

        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.undo)
        toolbar.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.redo)
        toolbar.addAction(redo_action)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.play_tab.request_spoiler_move)
        QShortcut(QKeySequence("H"), self, activated=lambda: self.play_tab.hint_panel.update_hints(self.play_tab.current_responses, self.play_tab.duplicator_select))
        QShortcut(QKeySequence("R"), self, activated=self.play_tab.replay)

    # ------------------------------------------------------------------
    def load_sample(self) -> None:
        graph_path = Path("twgbg/puzzles/preset_games/sample_pair.json")
        if not graph_path.exists():
            QMessageBox.warning(self, "Sample", "Sample puzzle missing")
            return
        self.state.graph_a, self.state.graph_b = load_graph_pair(str(graph_path))
        self.state.position = Position(self.state.graph_a.vertices()[0], self.state.graph_b.vertices()[0])
        self.state.stack = [self.state.position]
        self.state.history.clear()
        self.state.replies.clear()
        self.play_tab.reset_graphs(self.state.graph_a, self.state.graph_b)
        self.statusBar().showMessage("Loaded sample puzzle")

    def save_session(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save session", filter="JSON (*.json)")
        if not path:
            return
        data = {
            "position": {
                "vertex_a": self.state.position.vertex_a,
                "vertex_b": self.state.position.vertex_b,
            },
            "history": [move.__dict__ for move in self.state.history],
            "replies": [move.__dict__ for move in self.state.replies],
            "rules": self.state.rules.__dict__,
        }
        with open(path, "w", encoding="utf8") as handle:
            json.dump(data, handle, indent=2)
        self.statusBar().showMessage("Session saved")

    def load_session(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load session", filter="JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf8") as handle:
            data = json.load(handle)
        self.state.position = Position(data["position"]["vertex_a"], data["position"]["vertex_b"])
        self.state.history = [Move(**move) for move in data.get("history", [])]
        self.state.replies = [Move(**move) for move in data.get("replies", [])]
        self.state.rules = RuleSet(**data.get("rules", {}))
        self.state.stack = [self.state.position]
        self.state.redo_stack.clear()
        self.statusBar().showMessage("Session loaded")

    def export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", filter="PNG (*.png)")
        if not path:
            return
        export_scene_png(self.play_tab.view_a.scene, path)

    def export_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export SVG", filter="SVG (*.svg)")
        if not path:
            return
        export_scene_svg(self.play_tab.view_a.scene, path)

    def undo(self) -> None:
        pos = self.state.undo()
        if pos:
            self.statusBar().showMessage("Undo")
            self.play_tab.view_a.centre_on(pos.vertex_a)
            self.play_tab.view_b.centre_on(pos.vertex_b)

    def redo(self) -> None:
        pos = self.state.redo()
        if pos:
            self.statusBar().showMessage("Redo")
            self.play_tab.view_a.centre_on(pos.vertex_a)
            self.play_tab.view_b.centre_on(pos.vertex_b)


def load_default_state() -> GameState:
    graph_a = DiGraph.path(5, name="Graph A")
    graph_b = DiGraph.path(5, name="Graph B")
    position = Position(graph_a.vertices()[0], graph_b.vertices()[0])
    rules = RuleSet()
    state = GameState(graph_a, graph_b, position, rules)
    state.push(position)
    return state


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    state = load_default_state()
    window = MainWindow(state)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

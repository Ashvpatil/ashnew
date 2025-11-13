"""Onboarding tutorial for new players."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..engine.game import Position, RuleSet, legal_responses, spoiler_legal_moves
from ..engine.graphs import DiGraph
from .graphview import GraphView


@dataclass
class TutorialStage:
    title: str
    body: str
    setup: Callable[["TutorialStageWidget"], None] | None = None


class TutorialStageWidget(QWidget):
    def __init__(self, stage: TutorialStage, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel(stage.title)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        self.body.setMarkdown(stage.body)
        layout.addWidget(self.body)
        self.graph_container = QWidget()
        self.graph_layout = QVBoxLayout(self.graph_container)
        layout.addWidget(self.graph_container)
        if stage.setup:
            stage.setup(self)

    def add_graph_demo(self, graph_a: DiGraph, graph_b: DiGraph, rules: RuleSet) -> None:
        self.view_a = GraphView(graph_a)
        self.view_b = GraphView(graph_b)
        pair = QWidget()
        pair_layout = QHBoxLayout(pair)
        pair_layout.addWidget(self.view_a)
        pair_layout.addWidget(self.view_b)
        self.graph_layout.addWidget(pair)

        # Precompute a sample spoiler move
        position = Position(graph_a.vertices()[0], graph_b.vertices()[0])
        spoiler_move = spoiler_legal_moves(graph_a, graph_b, position, rules)[0]
        replies = legal_responses(graph_a, graph_b, position, spoiler_move, rules)
        self.view_a.show_hints([spoiler_move.target])
        self.view_b.show_hints([reply.target for reply in replies])
        hint = QLabel(
            "The glowing vertices indicate where Duplicator may respond."
        )
        hint.setAlignment(Qt.AlignCenter)
        self.graph_layout.addWidget(hint)


class TutorialWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.stack = QStackedWidget()
        self.stages = self._build_stages()
        for stage in self.stages:
            self.stack.addWidget(TutorialStageWidget(stage))
        controls = QHBoxLayout()
        self.prev_button = QPushButton("Back")
        self.next_button = QPushButton("Next")
        self.reset_button = QPushButton("Restart tutorial")
        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.reset_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)
        layout.addLayout(controls)

        self.prev_button.clicked.connect(self.prev_stage)
        self.next_button.clicked.connect(self.next_stage)
        self.reset_button.clicked.connect(self.reset)
        self.update_buttons()

    def _build_stages(self) -> List[TutorialStage]:
        simple_a = DiGraph.path(4, name="A")
        simple_b = DiGraph.path(4, name="B")
        rules = RuleSet()
        return [
            TutorialStage(
                "Welcome",
                """## Two-Way Global Bisimulation Game\n\nLearn how Spoiler tries to distinguish graph A from graph B while Duplicator mirrors moves to survive.""",
            ),
            TutorialStage(
                "Move types",
                """### Spoiler options\n\n- **Forward** follow outgoing edges\n- **Backward** retrace incoming edges\n- **Jump** teleport to any vertex""",
                setup=lambda widget: widget.add_graph_demo(simple_a, simple_b, rules),
            ),
            TutorialStage(
                "Mirroring replies",
                """### Duplicator must mirror the move type\n\nWhen Spoiler moves on one graph, you respond on the other. Try clicking the highlighted buttons during play!""",
            ),
            TutorialStage(
                "Strategies",
                """### Spoiler strategy hints\n\nThe Spoiler AI focuses on moves that leave few responses. Watch the coach panel for explanations.""",
            ),
            TutorialStage(
                "Challenges",
                """### Ready to practice?\n\nHead back to the *Play* tab and load a preset puzzle. Toggle hints with **H** if you get stuck.""",
            ),
        ]

    def next_stage(self) -> None:
        if self.stack.currentIndex() < self.stack.count() - 1:
            self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
        self.update_buttons()

    def prev_stage(self) -> None:
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self.update_buttons()

    def reset(self) -> None:
        self.stack.setCurrentIndex(0)
        self.update_buttons()

    def update_buttons(self) -> None:
        self.prev_button.setEnabled(self.stack.currentIndex() > 0)
        self.next_button.setEnabled(self.stack.currentIndex() < self.stack.count() - 1)

"""Tutorial manager providing staged onboarding."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class TutorialStage:
    title: str
    description: str


class TutorialManager:
    def __init__(self) -> None:
        self.stages: List[TutorialStage] = [
            TutorialStage("Basics", "Learn the objective and node highlighting."),
            TutorialStage("Move types", "Forward, backward and jump moves explained."),
            TutorialStage("Mirror replies", "Practice mirroring moves across graphs."),
            TutorialStage("Spoiler traps", "Recognise forcing tactics."),
            TutorialStage("Practice puzzles", "Solve curated training positions."),
        ]
        self.index = 0

    def current(self) -> TutorialStage:
        return self.stages[self.index]

    def next(self) -> TutorialStage:
        if self.index + 1 < len(self.stages):
            self.index += 1
        return self.current()

    def previous(self) -> TutorialStage:
        if self.index > 0:
            self.index -= 1
        return self.current()

    def reset(self) -> TutorialStage:
        self.index = 0
        return self.current()


__all__ = ["TutorialManager", "TutorialStage"]

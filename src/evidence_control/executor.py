"""Exact database decisions separated from language explanation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .representation import EvidencePacket


@dataclass(frozen=True)
class Constraint:
    predicate: str
    object_value: str


@dataclass(frozen=True)
class SelectionResult:
    selected_candidate_ids: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    rule: str = "exact predicate/object set intersection"


class ExactConstraintExecutor:
    def __init__(self, normalizer: Callable[[str], str] | None = None) -> None:
        self.normalize = normalizer or (lambda value: value)

    def select(
        self,
        candidate_ids: Iterable[str],
        constraints: Iterable[Constraint],
        packet: EvidencePacket,
    ) -> SelectionResult:
        required = {(self.normalize(item.predicate), self.normalize(item.object_value)) for item in constraints}
        selected: list[str] = []
        supporting: list[str] = []
        for candidate_id in candidate_ids:
            atoms = packet.for_subject(candidate_id)
            observed = {(self.normalize(atom.predicate), self.normalize(atom.object_value)) for atom in atoms}
            if required.issubset(observed):
                selected.append(candidate_id)
                supporting.extend(
                    atom.atom_id
                    for atom in atoms
                    if (self.normalize(atom.predicate), self.normalize(atom.object_value)) in required
                )
        return SelectionResult(tuple(selected), tuple(dict.fromkeys(supporting)))


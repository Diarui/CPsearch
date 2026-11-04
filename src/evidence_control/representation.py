"""Observation-preserving evidence representation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


class EvidenceClass(str, Enum):
    DIRECT = "direct_annotation"
    ASSAY = "assay_observation"
    COMPUTED = "computed_observation"
    SIMILARITY = "similarity_routing"
    STATUS = "database_status"


@dataclass(frozen=True)
class EvidenceAtom:
    """Smallest independently auditable unit supplied to a downstream consumer."""

    atom_id: str
    subject_id: str
    predicate: str
    object_value: str
    evidence_class: EvidenceClass
    source_ids: tuple[str, ...]
    observation_id: str = ""
    qualifiers: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "atom_id": self.atom_id,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")
        if not self.source_ids:
            raise ValueError("source_ids must contain at least one provenance identifier")
        if self.evidence_class == EvidenceClass.ASSAY and not self.observation_id:
            raise ValueError("assay evidence must retain observation_id")
        if self.evidence_class == EvidenceClass.COMPUTED and not self.qualifiers.get("derivation_method"):
            raise ValueError("computed evidence must disclose qualifiers.derivation_method")
        if self.evidence_class == EvidenceClass.SIMILARITY and not self.qualifiers.get("boundary"):
            raise ValueError("similarity evidence must disclose qualifiers.boundary")
        if self.evidence_class == EvidenceClass.STATUS:
            for key in ("attribute", "status", "snapshot"):
                if not self.qualifiers.get(key):
                    raise ValueError(f"database-status evidence requires qualifiers.{key}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_id": self.atom_id,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_value": self.object_value,
            "evidence_class": self.evidence_class.value,
            "source_ids": list(self.source_ids),
            "observation_id": self.observation_id,
            "qualifiers": dict(self.qualifiers),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceAtom":
        return cls(
            atom_id=str(value["atom_id"]),
            subject_id=str(value["subject_id"]),
            predicate=str(value["predicate"]),
            object_value=str(value.get("object_value", "")),
            evidence_class=EvidenceClass(value["evidence_class"]),
            source_ids=tuple(str(item) for item in value.get("source_ids", [])),
            observation_id=str(value.get("observation_id", "")),
            qualifiers=dict(value.get("qualifiers", {})),
        )


class EvidencePacket:
    """Ordered, atom-id-unique evidence collection."""

    def __init__(self, atoms: Iterable[EvidenceAtom] = ()) -> None:
        self._atoms: dict[str, EvidenceAtom] = {}
        self.extend(atoms)

    def __iter__(self) -> Iterator[EvidenceAtom]:
        return iter(self._atoms.values())

    def __len__(self) -> int:
        return len(self._atoms)

    def __getitem__(self, atom_id: str) -> EvidenceAtom:
        return self._atoms[atom_id]

    def add(self, atom: EvidenceAtom) -> None:
        previous = self._atoms.get(atom.atom_id)
        if previous is not None and previous != atom:
            raise ValueError(f"conflicting evidence atom id: {atom.atom_id}")
        self._atoms[atom.atom_id] = atom

    def extend(self, atoms: Iterable[EvidenceAtom]) -> None:
        for atom in atoms:
            self.add(atom)

    def for_subject(self, subject_id: str) -> tuple[EvidenceAtom, ...]:
        return tuple(atom for atom in self if atom.subject_id == subject_id)

    def to_list(self) -> list[dict[str, Any]]:
        return [atom.to_dict() for atom in self]

    @classmethod
    def from_jsonl(cls, path: str | Path) -> "EvidencePacket":
        with Path(path).open(encoding="utf-8") as handle:
            return cls(EvidenceAtom.from_dict(json.loads(line)) for line in handle if line.strip())

    def write_jsonl(self, path: str | Path) -> None:
        with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
            for atom in self:
                handle.write(json.dumps(atom.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


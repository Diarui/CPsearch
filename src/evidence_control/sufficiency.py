"""Deterministic requirement-coverage checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .representation import EvidenceAtom, EvidenceClass, EvidencePacket
from .requirements import QuestionRequirements, Requirement


class CoverageStatus(str, Enum):
    COVERED = "covered"
    COVERED_BY_STATUS = "covered_by_database_status"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class RequirementCoverage:
    requirement: str
    status: CoverageStatus
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class SufficiencyReport:
    sufficient: bool
    coverage: tuple[RequirementCoverage, ...]

    @property
    def covered(self) -> tuple[str, ...]:
        return tuple(item.requirement for item in self.coverage if item.status != CoverageStatus.UNRESOLVED)

    @property
    def unresolved(self) -> tuple[str, ...]:
        return tuple(item.requirement for item in self.coverage if item.status == CoverageStatus.UNRESOLVED)

    def to_dict(self) -> dict:
        return {
            "sufficient": self.sufficient,
            "covered": list(self.covered),
            "unresolved": list(self.unresolved),
            "coverage": [
                {"requirement": item.requirement, "status": item.status.value, "evidence_ids": list(item.evidence_ids)}
                for item in self.coverage
            ],
        }


def _matches(atom: EvidenceAtom, requirement: Requirement) -> bool:
    if not (requirement.predicates or requirement.evidence_classes or requirement.qualifier_keys):
        return False
    if requirement.predicates and atom.predicate not in requirement.predicates:
        return False
    if requirement.evidence_classes and atom.evidence_class not in requirement.evidence_classes:
        return False
    return all(key in atom.qualifiers and atom.qualifiers[key] not in (None, "") for key in requirement.qualifier_keys)


class SufficiencyChecker:
    def check(self, question: QuestionRequirements, packet: EvidencePacket) -> SufficiencyReport:
        items: list[RequirementCoverage] = []
        for requirement in question.requirements:
            matched = tuple(atom.atom_id for atom in packet if _matches(atom, requirement))
            if matched:
                items.append(RequirementCoverage(requirement.name, CoverageStatus.COVERED, matched))
                continue
            status_atoms = tuple(
                atom.atom_id
                for atom in packet
                if requirement.allow_database_status
                and atom.evidence_class == EvidenceClass.STATUS
                and atom.subject_id == question.entity_id
                and atom.qualifiers.get("attribute") == question.requested_attribute
            )
            status = CoverageStatus.COVERED_BY_STATUS if status_atoms else CoverageStatus.UNRESOLVED
            items.append(RequirementCoverage(requirement.name, status, status_atoms))
        return SufficiencyReport(all(item.status != CoverageStatus.UNRESOLVED for item in items), tuple(items))

"""Static, requirement-aware retrieval orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .representation import EvidenceAtom, EvidenceClass, EvidencePacket
from .requirements import ATTRIBUTE_PREDICATES, QuestionRequirements
from .sufficiency import SufficiencyChecker, SufficiencyReport


class EvidenceStore(Protocol):
    def fetch(self, operation: str, question: QuestionRequirements) -> Iterable[EvidenceAtom]: ...


class InMemoryEvidenceStore:
    """Reference store for tests and small analyses."""

    def __init__(self, atoms: Iterable[EvidenceAtom]) -> None:
        self.atoms = tuple(atoms)

    def fetch(self, operation: str, question: QuestionRequirements) -> tuple[EvidenceAtom, ...]:
        classes = {
            "direct": {EvidenceClass.DIRECT},
            "assay": {EvidenceClass.ASSAY},
            "support": {EvidenceClass.DIRECT, EvidenceClass.ASSAY},
            "observation": {EvidenceClass.COMPUTED},
            "similarity": {EvidenceClass.SIMILARITY},
            "status": {EvidenceClass.STATUS},
        }.get(operation)
        if classes is None:
            raise ValueError(f"unknown retrieval operation: {operation}")
        selected = [atom for atom in self.atoms if atom.subject_id == question.entity_id and atom.evidence_class in classes]
        if operation == "direct" and question.requested_attribute:
            predicate = ATTRIBUTE_PREDICATES.get(question.requested_attribute)
            selected = [atom for atom in selected if not predicate or atom.predicate == predicate]
        if operation == "assay" and question.assay_id:
            selected = [atom for atom in selected if str(atom.qualifiers.get("assay_id", "")) == question.assay_id]
        if operation == "support":
            selected = [atom for atom in selected if atom.qualifiers.get("support_id") or atom.qualifiers.get("publication")]
        if operation == "status" and question.requested_attribute:
            selected = [atom for atom in selected if atom.qualifiers.get("attribute") == question.requested_attribute]
        return tuple(selected)


@dataclass(frozen=True)
class RetrievalBudget:
    max_actions: int = 6
    max_atoms: int = 100


class StaticPlanner:
    OPERATION_REQUIREMENTS = {
        "direct": {"direct_fact", "biological_source", "structure_support", "permeability"},
        "assay": {"assay_value", "assay_target", "unit_status", "activity_qualification"},
        "support": {"statement_support", "publication"},
        "observation": {"observation", "derivation_disclosure"},
        "similarity": {"similarity", "indirect_evidence_boundary"},
        "status": {"knowledge_status"},
    }

    def plan(self, question: QuestionRequirements) -> tuple[str, ...]:
        required = set(question.names)
        operations = [name for name, names in self.OPERATION_REQUIREMENTS.items() if required & names]
        if any(requirement.allow_database_status for requirement in question.requirements):
            operations.append("status")
        return tuple(dict.fromkeys(operations))


@dataclass(frozen=True)
class RetrievalResult:
    packet: EvidencePacket
    operations: tuple[str, ...]
    sufficiency: SufficiencyReport
    stop_reason: str


class RequirementAwareRetriever:
    def __init__(
        self,
        store: EvidenceStore,
        planner: StaticPlanner | None = None,
        checker: SufficiencyChecker | None = None,
        budget: RetrievalBudget | None = None,
    ) -> None:
        self.store = store
        self.planner = planner or StaticPlanner()
        self.checker = checker or SufficiencyChecker()
        self.budget = budget or RetrievalBudget()

    def retrieve(self, question: QuestionRequirements) -> RetrievalResult:
        packet = EvidencePacket()
        executed: list[str] = []
        report = self.checker.check(question, packet)
        stop_reason = "retrieval_plan_exhausted"
        for operation in self.planner.plan(question):
            if len(executed) >= self.budget.max_actions:
                stop_reason = "action_budget_exhausted"
                break
            additions = tuple(self.store.fetch(operation, question))
            existing_ids = {atom.atom_id for atom in packet}
            new_ids = {atom.atom_id for atom in additions} - existing_ids
            if len(packet) + len(new_ids) > self.budget.max_atoms:
                stop_reason = "atom_budget_exhausted"
                break
            packet.extend(additions)
            executed.append(operation)
            report = self.checker.check(question, packet)
            if report.sufficient:
                stop_reason = "all_requirements_resolved"
                break
        return RetrievalResult(packet, tuple(executed), report, stop_reason)


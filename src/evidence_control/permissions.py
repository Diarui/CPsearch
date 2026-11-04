"""Evidence-class claim permissions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .representation import EvidenceClass, EvidencePacket


DEFAULT_PERMISSIONS: Mapping[EvidenceClass, frozenset[str]] = {
    EvidenceClass.DIRECT: frozenset({"database_fact"}),
    EvidenceClass.ASSAY: frozenset({"assay_context"}),
    EvidenceClass.COMPUTED: frozenset({"computed_observation"}),
    EvidenceClass.SIMILARITY: frozenset({"similarity_routing"}),
    EvidenceClass.STATUS: frozenset({"database_missingness"}),
}


@dataclass(frozen=True)
class Claim:
    claim_id: str
    subject_id: str
    predicate: str
    object_value: str
    evidence_ids: tuple[str, ...]
    claim_type: str = "database_fact"
    text: str = ""


@dataclass(frozen=True)
class PermissionDecision:
    claim_id: str
    allowed: bool
    reason: str
    supporting_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegulationResult:
    allowed_claims: tuple[Claim, ...]
    decisions: tuple[PermissionDecision, ...]


class ClaimPermissionChecker:
    def __init__(self, permissions: Mapping[EvidenceClass, Iterable[str]] = DEFAULT_PERMISSIONS) -> None:
        self.permissions = {key: frozenset(value) for key, value in permissions.items()}

    def check(self, claim: Claim, packet: EvidencePacket) -> PermissionDecision:
        if not claim.evidence_ids:
            return PermissionDecision(claim.claim_id, False, "no_evidence_cited")
        supplied_ids = {atom.atom_id for atom in packet}
        missing = tuple(atom_id for atom_id in claim.evidence_ids if atom_id not in supplied_ids)
        if missing:
            return PermissionDecision(claim.claim_id, False, "cited_evidence_not_supplied")
        matching = tuple(
            atom
            for atom_id in claim.evidence_ids
            for atom in (packet[atom_id],)
            if atom.subject_id == claim.subject_id
            and atom.predicate == claim.predicate
            and atom.object_value == claim.object_value
        )
        if not matching:
            return PermissionDecision(claim.claim_id, False, "no_exact_structured_support")
        if len(matching) != len(claim.evidence_ids):
            return PermissionDecision(claim.claim_id, False, "cited_evidence_not_exact_support")
        permitted = tuple(atom.atom_id for atom in matching if claim.claim_type in self.permissions.get(atom.evidence_class, frozenset()))
        if not permitted:
            return PermissionDecision(claim.claim_id, False, "evidence_class_does_not_permit_claim_type")
        return PermissionDecision(claim.claim_id, True, "permitted", permitted)

    def regulate(self, claims: Iterable[Claim], packet: EvidencePacket) -> RegulationResult:
        claims = tuple(claims)
        decisions = tuple(self.check(claim, packet) for claim in claims)
        allowed = tuple(claim for claim, decision in zip(claims, decisions) if decision.allowed)
        return RegulationResult(allowed, decisions)

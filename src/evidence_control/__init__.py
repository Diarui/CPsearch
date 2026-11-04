"""Deterministic evidence-control primitives."""

from .audit import AuditEvent, AuditTrail, stable_hash
from ._config import load_default_config
from .executor import Constraint, ExactConstraintExecutor, SelectionResult
from .permissions import Claim, ClaimPermissionChecker, PermissionDecision, RegulationResult
from .representation import EvidenceAtom, EvidenceClass, EvidencePacket
from .requirements import QuestionRequirements, Requirement, RuleBasedRequirementParser
from .retrieval import EvidenceStore, InMemoryEvidenceStore, RequirementAwareRetriever, RetrievalBudget, RetrievalResult, StaticPlanner
from .sufficiency import CoverageStatus, SufficiencyChecker, SufficiencyReport

__all__ = [
    "AuditEvent",
    "AuditTrail",
    "Claim",
    "ClaimPermissionChecker",
    "Constraint",
    "CoverageStatus",
    "EvidenceAtom",
    "EvidenceClass",
    "EvidencePacket",
    "EvidenceStore",
    "ExactConstraintExecutor",
    "InMemoryEvidenceStore",
    "PermissionDecision",
    "QuestionRequirements",
    "RegulationResult",
    "Requirement",
    "RequirementAwareRetriever",
    "RetrievalBudget",
    "RetrievalResult",
    "RuleBasedRequirementParser",
    "SelectionResult",
    "StaticPlanner",
    "SufficiencyChecker",
    "SufficiencyReport",
    "stable_hash",
    "load_default_config",
]

__version__ = "0.1.0"

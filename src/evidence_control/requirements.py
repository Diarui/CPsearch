"""Question-specific evidence requirements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

from .representation import EvidenceClass


@dataclass(frozen=True)
class Requirement:
    name: str
    predicates: tuple[str, ...] = ()
    evidence_classes: tuple[EvidenceClass, ...] = ()
    qualifier_keys: tuple[str, ...] = ()
    allow_database_status: bool = False


@dataclass(frozen=True)
class QuestionRequirements:
    question: str
    entity_id: str
    goal: str
    requirements: tuple[Requirement, ...]
    requested_attribute: str = ""
    assay_id: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(requirement.name for requirement in self.requirements)


DEFAULT_ATTRIBUTE_TERMS: Mapping[str, tuple[str, ...]] = {
    "function": ("function", "功能"),
    "target": ("target", "靶点"),
    "family": ("family", "家族"),
    "biological_source": ("biological source", "organism source", "生物来源"),
    "publication": ("publication", "pmid", "文献"),
}

ATTRIBUTE_PREDICATES = {
    "function": "HAS_FUNCTION",
    "target": "HAS_TARGET",
    "family": "HAS_FAMILY",
    "biological_source": "HAS_BIOLOGICAL_SOURCE",
    "publication": "HAS_ASSOCIATED_PUBLICATION",
}


def _requirement(name: str, attribute: str = "") -> Requirement:
    if name == "direct_fact":
        predicate = ATTRIBUTE_PREDICATES.get(attribute, "")
        return Requirement(name, (predicate,) if predicate else (), (EvidenceClass.DIRECT,), allow_database_status=True)
    if name == "statement_support":
        return Requirement(name, evidence_classes=(EvidenceClass.DIRECT,), qualifier_keys=("support_id",))
    if name in {"assay_value", "assay_target", "unit_status", "activity_qualification"}:
        key = {
            "assay_value": "measurement_type",
            "assay_target": "target",
            "unit_status": "unit_status",
            "activity_qualification": "activity_label",
        }[name]
        return Requirement(name, ("ASSAY_CONTEXT",), (EvidenceClass.ASSAY,), (key,))
    if name == "publication":
        return Requirement(name, evidence_classes=(EvidenceClass.ASSAY, EvidenceClass.DIRECT), qualifier_keys=("publication",))
    if name in {"observation", "derivation_disclosure"}:
        keys = ("derivation_method",) if name == "derivation_disclosure" else ()
        return Requirement(name, evidence_classes=(EvidenceClass.COMPUTED,), qualifier_keys=keys)
    if name in {"similarity", "indirect_evidence_boundary"}:
        keys = ("boundary",) if name == "indirect_evidence_boundary" else ()
        return Requirement(name, evidence_classes=(EvidenceClass.SIMILARITY,), qualifier_keys=keys)
    if name == "knowledge_status":
        return Requirement(name, evidence_classes=(EvidenceClass.STATUS,))
    return Requirement(name)


class RuleBasedRequirementParser:
    """Transparent parser for identifier-addressed database questions."""

    def __init__(
        self,
        identifier_pattern: str = r"\bCP\d{5}\b",
        entity_prefix: str = "PEPTIDE:CyclicPepedia:",
        attribute_terms: Mapping[str, Iterable[str]] = DEFAULT_ATTRIBUTE_TERMS,
    ) -> None:
        self.identifier = re.compile(identifier_pattern, flags=re.I)
        self.entity_prefix = entity_prefix
        self.attribute_terms = {key: tuple(value) for key, value in attribute_terms.items()}

    def parse(self, question: str) -> QuestionRequirements:
        lower = question.casefold()
        match = self.identifier.search(question)
        entity_id = self.entity_prefix + match.group(0).upper() if match else ""
        attribute = next(
            (key for key, terms in self.attribute_terms.items() if any(term.casefold() in lower for term in terms)),
            "",
        )
        assay_match = re.search(r"(?:aid|bioassay(?: id)?)\s*[=:：#]?\s*(\d+)", lower)
        assay_id = assay_match.group(1) if assay_match else ""
        has_assay = bool(assay_id) or any(term in lower for term in ("assay", "bioassay", "实验值", "测定值"))
        asks_value = any(term in lower for term in ("value", "实验值", "测定值"))
        asks_target = any(term in lower for term in ("target", "靶点"))
        asks_publication = any(term in lower for term in ("publication", "pmid", "文献", "citation"))
        asks_support = any(term in lower for term in ("supporting evidence", "evidence source", "支持来源", "证据"))
        asks_source = attribute == "biological_source"

        names: list[str]
        if has_assay and asks_source:
            goal = "assay_and_source"
            names = ["assay_value", "assay_target", "publication", "direct_fact", "statement_support"]
        elif has_assay:
            goal = "assay_context"
            names = []
            if asks_value:
                names.append("assay_value")
            if asks_target:
                names.append("assay_target")
            if asks_publication:
                names.append("publication")
            if not names:
                names.append("assay_value")
        else:
            goal = "direct_attribute"
            names = ["direct_fact"]
            if asks_support or asks_publication:
                names.append("statement_support")

        return QuestionRequirements(
            question=question,
            entity_id=entity_id,
            goal=goal,
            requirements=tuple(_requirement(name, attribute) for name in names),
            requested_attribute=attribute,
            assay_id=assay_id,
        )


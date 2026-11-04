from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evidence_control import load_default_config
from evidence_control.audit import AuditTrail, stable_hash
from evidence_control.executor import Constraint, ExactConstraintExecutor
from evidence_control.permissions import Claim, ClaimPermissionChecker
from evidence_control.representation import EvidenceAtom, EvidenceClass, EvidencePacket
from evidence_control.requirements import QuestionRequirements, Requirement, RuleBasedRequirementParser
from evidence_control.retrieval import InMemoryEvidenceStore, RequirementAwareRetriever
from evidence_control.sufficiency import CoverageStatus, SufficiencyChecker


def direct(atom_id: str, subject: str, predicate: str, value: str, **qualifiers) -> EvidenceAtom:
    return EvidenceAtom(atom_id, subject, predicate, value, EvidenceClass.DIRECT, (f"ROW:{atom_id}",), qualifiers=qualifiers)


class RepresentationTests(unittest.TestCase):
    def test_assay_requires_observation_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "observation_id"):
            EvidenceAtom("A", "P", "ASSAY_CONTEXT", "42", EvidenceClass.ASSAY, ("ROW:1",))

    def test_packet_rejects_conflicting_ids(self) -> None:
        packet = EvidencePacket([direct("A", "P", "HAS_TARGET", "T1")])
        with self.assertRaisesRegex(ValueError, "conflicting"):
            packet.add(direct("A", "P", "HAS_TARGET", "T2"))


class RequirementAndRetrievalTests(unittest.TestCase):
    def test_assay_requirements_use_observation_context(self) -> None:
        entity = "PEPTIDE:CyclicPepedia:CP00001"
        assay = EvidenceAtom(
            "ASSAY1",
            entity,
            "ASSAY_CONTEXT",
            "measurement=42; target=T1",
            EvidenceClass.ASSAY,
            ("ROW:assay:1",),
            observation_id="OBS:assay:1",
            qualifiers={"measurement_type": "activity", "target": "T1"},
        )
        question = QuestionRequirements(
            "q",
            entity,
            "assay_context",
            (
                Requirement("assay_value", ("ASSAY_CONTEXT",), (EvidenceClass.ASSAY,), ("measurement_type",)),
                Requirement("assay_target", ("ASSAY_CONTEXT",), (EvidenceClass.ASSAY,), ("target",)),
            ),
        )
        report = SufficiencyChecker().check(question, EvidencePacket([assay]))
        self.assertTrue(report.sufficient)
        self.assertEqual(report.covered, ("assay_value", "assay_target"))

    def test_parser_and_early_stop(self) -> None:
        parsed = RuleBasedRequirementParser().parse("What target is recorded for CP00001?")
        self.assertEqual(parsed.entity_id, "PEPTIDE:CyclicPepedia:CP00001")
        self.assertEqual(parsed.names, ("direct_fact",))
        result = RequirementAwareRetriever(
            InMemoryEvidenceStore([direct("A", parsed.entity_id, "HAS_TARGET", "T1")])
        ).retrieve(parsed)
        self.assertTrue(result.sufficiency.sufficient)
        self.assertEqual(result.operations, ("direct",))
        self.assertEqual(result.stop_reason, "all_requirements_resolved")

    def test_explicit_status_resolves_database_coverage(self) -> None:
        entity = "PEPTIDE:CyclicPepedia:CP00001"
        parsed = RuleBasedRequirementParser().parse("What family is recorded for CP00001?")
        status = EvidenceAtom(
            "S1",
            entity,
            "DATABASE_MISSINGNESS",
            "family not recorded",
            EvidenceClass.STATUS,
            ("STATUS:1",),
            qualifiers={"attribute": "family", "status": "not_recorded_in_snapshot", "snapshot": "2026-01-01"},
        )
        result = RequirementAwareRetriever(InMemoryEvidenceStore([status])).retrieve(parsed)
        self.assertTrue(result.sufficiency.sufficient)
        self.assertEqual(result.sufficiency.coverage[0].status, CoverageStatus.COVERED_BY_STATUS)

    def test_unresolved_is_visible(self) -> None:
        question = QuestionRequirements("q", "P", "custom", (Requirement("unit_status", qualifier_keys=("unit_status",)),))
        report = SufficiencyChecker().check(question, EvidencePacket())
        self.assertFalse(report.sufficient)
        self.assertEqual(report.unresolved, ("unit_status",))

    def test_unknown_requirement_is_not_satisfied_by_unrelated_atom(self) -> None:
        question = QuestionRequirements("q", "P", "custom", (Requirement("unknown"),))
        report = SufficiencyChecker().check(question, EvidencePacket([direct("A", "P", "HAS_TARGET", "T")]))
        self.assertFalse(report.sufficient)


class ExecutorAndPermissionTests(unittest.TestCase):
    def test_computed_evidence_cannot_be_relabelled_as_database_fact(self) -> None:
        computed = EvidenceAtom(
            "COMP1",
            "P1",
            "COMPUTED_OBSERVATION",
            "representation=demo",
            EvidenceClass.COMPUTED,
            ("ROW:computed:1",),
            qualifiers={"derivation_method": "documented conversion"},
        )
        packet = EvidencePacket([computed])
        checker = ClaimPermissionChecker()
        permitted = Claim("C1", "P1", "COMPUTED_OBSERVATION", "representation=demo", ("COMP1",), "computed_observation")
        relabelled = Claim("C2", "P1", "COMPUTED_OBSERVATION", "representation=demo", ("COMP1",), "database_fact")
        self.assertTrue(checker.check(permitted, packet).allowed)
        self.assertFalse(checker.check(relabelled, packet).allowed)

    def test_exact_intersection(self) -> None:
        packet = EvidencePacket([
            direct("A1", "P1", "HAS_TARGET", "T"),
            direct("A2", "P1", "HAS_FUNCTION", "F"),
            direct("A3", "P2", "HAS_TARGET", "T"),
        ])
        result = ExactConstraintExecutor().select(
            ("P1", "P2"), (Constraint("HAS_TARGET", "T"), Constraint("HAS_FUNCTION", "F")), packet
        )
        self.assertEqual(result.selected_candidate_ids, ("P1",))
        self.assertEqual(set(result.supporting_evidence_ids), {"A1", "A2"})

    def test_permission_boundaries(self) -> None:
        similarity = EvidenceAtom(
            "SIM1",
            "P1",
            "SEQUENCE_SIMILARITY_ROUTING",
            "neighbor=P2",
            EvidenceClass.SIMILARITY,
            ("OBS:1", "OBS:2"),
            qualifiers={"boundary": "routing_only"},
        )
        packet = EvidencePacket([similarity])
        checker = ClaimPermissionChecker()
        allowed = Claim("C1", "P1", "SEQUENCE_SIMILARITY_ROUTING", "neighbor=P2", ("SIM1",), "similarity_routing")
        transferred = Claim("C2", "P1", "SEQUENCE_SIMILARITY_ROUTING", "neighbor=P2", ("SIM1",), "database_fact")
        self.assertTrue(checker.check(allowed, packet).allowed)
        self.assertFalse(checker.check(transferred, packet).allowed)

    def test_regulate_accepts_one_pass_iterables(self) -> None:
        atom = direct("A1", "P1", "HAS_TARGET", "T")
        claim = Claim("C1", "P1", "HAS_TARGET", "T", ("A1",), "database_fact")
        result = ClaimPermissionChecker().regulate((item for item in [claim]), EvidencePacket([atom]))
        self.assertEqual(result.allowed_claims, (claim,))
        self.assertTrue(result.decisions[0].allowed)

    def test_irrelevant_extra_citation_is_rejected(self) -> None:
        packet = EvidencePacket([
            direct("A1", "P1", "HAS_TARGET", "T"),
            direct("A2", "P1", "HAS_FUNCTION", "F"),
        ])
        claim = Claim("C1", "P1", "HAS_TARGET", "T", ("A1", "A2"), "database_fact")
        decision = ClaimPermissionChecker().check(claim, packet)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "cited_evidence_not_exact_support")


class AuditTests(unittest.TestCase):
    def test_stable_hash_and_jsonl(self) -> None:
        self.assertEqual(stable_hash({"b": 2, "a": 1}), stable_hash({"a": 1, "b": 2}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            AuditTrail(path, "run-1").record("test", {"x": 1}, {"ok": True})
            row = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(row["run_id"], "run-1")
            self.assertEqual(row["event_type"], "test")

    def test_packaged_configuration_loads(self) -> None:
        config = load_default_config()
        self.assertEqual(config["retrieval_budget"]["max_actions"], 6)
        self.assertIn("database_status", config["claim_type_permissions"])


if __name__ == "__main__":
    unittest.main()

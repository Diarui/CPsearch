"""Figure 4 record and API smoke checks, not biological experiments."""
import sys
import unittest
from pathlib import Path

from evidence_control import Claim, ClaimPermissionChecker, EvidencePacket

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples'))
from core_workflow import run


class Figure4Tests(unittest.TestCase):
    def test_examples_and_missing_target(self):
        rows = run()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r['claim_allowed'] for r in rows))
        unresolved = [r for r in rows if not r['sufficiency']['sufficient']]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]['evidence'][0]['atom_id'], 'ASSAY:CyclicPepedia:64')
        self.assertEqual(unresolved[0]['sufficiency']['unresolved'], ['assay_target'])

    def test_assay_records_keep_source_context(self):
        atoms = [r['evidence'][0] for r in run() if r['evidence'][0]['evidence_class'] == 'assay_observation']
        self.assertEqual({a['observation_id'] for a in atoms}, {
            'ASSAY:CyclicPepedia:64', 'ASSAY:CyclicPepedia:2',
            'ASSAY:CyclicPepedia:833', 'ASSAY:CyclicPepedia:883'})
        self.assertEqual({a['qualifiers']['aid'] for a in atoms}, {'1346987', '1347411', '217086', '549467'})
        self.assertTrue(all(a['qualifiers']['unit'] == '' for a in atoms))

    def test_deliberately_unsupported_structured_claim_is_filtered(self):
        # Deliberate test input, not an LLM output or biological assertion.
        row = run()[0]
        packet = EvidencePacket()
        from evidence_control import EvidenceAtom
        packet.extend(EvidenceAtom.from_dict(a) for a in row['evidence'])
        atom = next(iter(packet))
        supported = Claim('supported', atom.subject_id, atom.predicate, atom.object_value, (atom.atom_id,))
        invalid = Claim('invalid-test-input', atom.subject_id, atom.predicate, '__UNSUPPORTED_TEST_VALUE__', (atom.atom_id,))
        result = ClaimPermissionChecker().regulate([supported, invalid], packet)
        self.assertEqual(result.allowed_claims, (supported,))


if __name__ == '__main__':
    unittest.main()

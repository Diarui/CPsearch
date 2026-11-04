"""Offline API demonstration over existing Figure 4 records; no model calls."""
import json
from pathlib import Path

from evidence_control import (
    Claim, ClaimPermissionChecker, EvidenceClass, EvidencePacket,
    InMemoryEvidenceStore, RequirementAwareRetriever, RuleBasedRequirementParser,
)


def run():
    outputs = []
    for filename in ('actinomycin_d.jsonl', 'oxytocin.jsonl'):
        packet = EvidencePacket.from_jsonl(Path(__file__).parent / 'data' / filename)
        for atom in packet:
            cpid = atom.subject_id.rsplit(':', 1)[-1]
            assay = atom.evidence_class == EvidenceClass.ASSAY
            question = (f'What assay value target publication is recorded for {cpid} AID {atom.qualifiers["aid"]}?'
                        if assay else f'What function is recorded for {cpid}?')
            frame = RuleBasedRequirementParser().parse(question)
            # Scope each request to one existing observation. Never combine contexts.
            result = RequirementAwareRetriever(InMemoryEvidenceStore([atom])).retrieve(frame)
            claim = Claim('exact-record', atom.subject_id, atom.predicate, atom.object_value,
                          (atom.atom_id,), 'assay_context' if assay else 'database_fact')
            permission = ClaimPermissionChecker().check(claim, result.packet)
            outputs.append({
                'example': filename, 'question': question,
                'semantic_frame': {'entity_id': frame.entity_id, 'goal': frame.goal,
                                   'assay_id': frame.assay_id, 'requirements': frame.names},
                'operations': result.operations, 'stop_reason': result.stop_reason,
                'sufficiency': result.sufficiency.to_dict(),
                'claim_allowed': permission.allowed, 'permission_reason': permission.reason,
                'evidence': result.packet.to_list(),
            })
    return outputs


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))

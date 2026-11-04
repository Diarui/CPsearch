# CPsearch

CPsearch supports auditable analysis of cyclic peptide database records by keeping
scientific conclusions connected to the observations that support them. It links
measurements to their experimental context, retrieves evidence according to the
question, computes exact candidate decisions and checks structured claims against
supplied evidence.

This repository provides CPsearch's core method reference implementation.
Author and maintainer: **Aiting Wang**.

## Four evidence controls

| Module | Role | Main interfaces |
| --- | --- | --- |
| Observation identity | Preserve independent observations, experimental qualifiers and provenance | `EvidenceAtom`, `EvidencePacket` |
| Question-specific evidence requirements and retrieval | Parse identifier/keyword questions, plan evidence retrieval and report covered or unresolved requirements | `RuleBasedRequirementParser.parse`, `StaticPlanner.plan`, `RequirementAwareRetriever.retrieve`, `SufficiencyChecker.check` |
| Deterministic constraint execution | Select candidates satisfying the intersection of explicit predicate/value constraints and return supporting evidence IDs | `ExactConstraintExecutor.select` |
| Claim permissions | Check cited IDs, exact structured support and evidence-class permissions; retain supported claims | `ClaimPermissionChecker.check`, `ClaimPermissionChecker.regulate` |

Observation-qualified atoms form the shared evidence layer. Question requirements
guide retrieval into a packet and make evidence gaps explicit. The packet supports
both deterministic candidate selection and claim checking, connecting decisions
and interpretations to their supporting records. Coverage and claim permission
are reported separately.

## Data structures

| Structure | Contents |
| --- | --- |
| `EvidenceAtom` | `atom_id`, `subject_id`, `predicate`, `object_value`, `evidence_class`, `source_ids`, `observation_id`, `qualifiers` |
| `EvidencePacket` | Ordered evidence atoms with unique IDs; rejects conflicting IDs and supports JSONL reading and writing |
| `RetrievalResult` | Retrieved `packet`, executed `operations`, `sufficiency` report and `stop_reason` |
| `SelectionResult` | `selected_candidate_ids`, `supporting_evidence_ids` and the selection `rule` |
| `RegulationResult` | Retained `allowed_claims` and permission `decisions` |

Each JSONL line is one evidence atom. `source_ids` records provenance identifiers;
`observation_id` identifies an independent observation and is required for assay
atoms. `qualifiers` retains source-table/row identifiers and available measurement,
unit, target, publication and assay context. Missing source values remain missing.

Evidence classes distinguish direct annotations, assay observations, computed
representations, similarity routing and database status. Their qualifiers retain
computational derivation, similarity boundaries or snapshot-specific coverage as
appropriate. `Claim` carries the subject, predicate, value, cited evidence IDs and
claim type for exact structured matching and permission checks.

## Examples

Actinomycin D and Oxytocin each include one recorded function annotation and two
independent assay observations in `examples/data`.

| Peptide | Recorded measurement | PMID / AID |
| --- | --- | --- |
| Actinomycin D / CP00001 | Potency 0.1865, P-glycoprotein substrate screen | 31515284 / 1346987 |
| Actinomycin D / CP00001 | Potency 0.1139, IFNB1 assay | 32459468 / 1347411 |
| Oxytocin / CP00290 | Ki 0.12, AVPR1A binding | 12036367 / 217086 |
| Oxytocin / CP00290 | EC50 0.015, OXTR activity in COS1 cells | 21117646 / 549467 |

The example queries each observation separately and outputs its evidence context,
coverage and claim permission. Units remain empty as recorded; the P-glycoprotein
record's missing target is reported as unresolved.

## Installation and use

Requires Python >=3.10. Runtime and tests use the standard library; building uses
setuptools>=68. From the repository root:

```sh
python -m pip install .
python examples/core_workflow.py
python -m unittest discover -s tests -v
```

A basic retrieval and claim check:

```python
from evidence_control import (
    Claim, ClaimPermissionChecker, EvidencePacket, InMemoryEvidenceStore,
    RequirementAwareRetriever, RuleBasedRequirementParser,
)

packet = EvidencePacket.from_jsonl("examples/data/oxytocin.jsonl")
question = RuleBasedRequirementParser().parse("What function is recorded for CP00290?")
result = RequirementAwareRetriever(InMemoryEvidenceStore(packet)).retrieve(question)

atom = next(iter(result.packet))
claim = Claim(
    claim_id="function-1",
    subject_id=atom.subject_id,
    predicate=atom.predicate,
    object_value=atom.object_value,
    evidence_ids=(atom.atom_id,),
    claim_type="database_fact",
)
regulated = ClaimPermissionChecker().regulate([claim], result.packet)
print(result.sufficiency.to_dict())
print(regulated.allowed_claims)
```

For source execution, set `PYTHONPATH=src` before running the example or tests
(PowerShell: `$env:PYTHONPATH = 'src'`). The offline examples use the packaged
records and require no model or network connection.

The implementation is in `src/evidence_control`; examples and lightweight tests
are in `examples` and `tests`. The Python import namespace is `evidence_control`
and the package name is `evidence-control-toolkit`.

Software licensing and example-data redistribution remain subject to approval by
Aiting Wang. See `LICENSE` and `CITATION.cff` for the current drafts.

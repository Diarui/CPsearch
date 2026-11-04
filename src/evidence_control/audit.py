"""Append-only audit records with stable content hashes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    run_id: str
    timestamp: str
    input_hash: str
    output_hash: str
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditTrail:
    def __init__(self, path: str | Path, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id

    def record(
        self,
        event_type: str,
        inputs: Any,
        outputs: Any,
        details: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            run_id=self.run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            input_hash=stable_hash(inputs),
            output_hash=stable_hash(outputs),
            details=dict(details or {}),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        return event


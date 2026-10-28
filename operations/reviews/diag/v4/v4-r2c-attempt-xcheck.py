#!/usr/bin/env python3
"""Independent §6.3 ⑤ attempt_count on existing v3 ledger (no v4 ledger)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.eval.common import C1_SHADOW_ARM, EXPLORATION_TRIALS, ORCHESTRATOR_DIAGNOSTIC_TRIALS
from src.v3.engine.spec import LEDGER
from src.v4.scorecard.gate import attempt_count

_OFFSET = EXPLORATION_TRIALS + ORCHESTRATOR_DIAGNOSTIC_TRIALS


def _deduped(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen = set()
    kept = []
    for row in rows:
        key = (row.get("arm") or "", row.get("params") or "", row.get("segment") or "")
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def independent_count(v3_path: Path) -> int:
    rows = _deduped(v3_path)
    shadow = sum(1 for row in rows if (row.get("arm") or "") == C1_SHADOW_ARM)
    return len(rows) - shadow + _OFFSET


def main() -> int:
    v3 = LEDGER
    dev = attempt_count(v3, Path("/tmp/v4-ledger-missing-r2c-review.csv"))
    ind = independent_count(v3)
    out = {
        "v3_ledger": str(v3),
        "deduped_rows": len(_deduped(v3)),
        "c1_shadow_rows": sum(1 for r in _deduped(v3) if (r.get("arm") or "") == C1_SHADOW_ARM),
        "offset_28_35": _OFFSET,
        "dev_attempt_count": dev,
        "independent_attempt_count": ind,
        "matches_a3_73": dev == 73 and ind == 73 and dev == ind,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["matches_a3_73"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

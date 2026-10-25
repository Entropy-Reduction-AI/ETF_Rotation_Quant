#!/usr/bin/env python3
"""L1 rework: merged-container inventory, counts, uniqueness (Reviewer)."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
UNIVERSE = ROOT / "config" / "v3" / "universe.toml"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.data.universe import containers, duplicate_execution_errors, validate


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    rows = containers()
    code_map: dict[str, list[dict]] = defaultdict(list)
    inventory = []
    for row in rows:
        cid = row["id"]
        arm = row.get("arm") or "main"
        execs = []
        for ex in row.get("execution") or []:
            code = str(ex.get("code") or "")
            if code and code not in {"取不到", "TBD"}:
                execs.append(
                    {
                        "code": code,
                        "list_date": ex.get("list_date"),
                        "track": ex.get("track"),
                    }
                )
                code_map[code].append({"container": cid, "arm": arm})
        research = row.get("research") or {}
        inventory.append(
            {
                "id": cid,
                "arm": arm,
                "asset_class": row.get("asset_class"),
                "name": row.get("name"),
                "research_index_code": research.get("index_code"),
                "research_publish_date": research.get("publish_date"),
                "execution": execs,
                "execution_primary_code": execs[0]["code"] if execs else None,
            }
        )

    by_class = Counter(r.get("asset_class") or "?" for r in rows)
    by_arm = Counter(r.get("arm") or "main" for r in rows)
    file_dups = {c: locs for c, locs in code_map.items() if len(locs) > 1}
    main_codes: dict[str, str] = {}
    main_cross_dup: list[dict] = []
    for code, locs in code_map.items():
        mains = [x for x in locs if x["arm"] == "main"]
        if len(mains) > 1:
            main_cross_dup.append({"code": code, "containers": mains})
        elif len(mains) == 1:
            prev = main_codes.get(code)
            if prev:
                main_cross_dup.append(
                    {
                        "code": code,
                        "containers": [{"container": prev, "arm": "main"}, mains[0]],
                    }
                )
            else:
                main_codes[code] = mains[0]["container"]

    missing_ld_rows = 0
    missing_ld_codes: set[str] = set()
    for row in rows:
        for ex in row.get("execution") or []:
            if ex.get("list_date") in ("取不到", "TBD", None, ""):
                missing_ld_rows += 1
                c = ex.get("code")
                if c:
                    missing_ld_codes.add(str(c))

    spot_expected = {
        "159741": "hstech",
        "513130": "hstech",
        "158042": "hstech",
        "513260": "hstech",
        "164705": "hsi",
        "159660": "ndx100",
        "160213": "ndx100",
        "513870": "ndx100",
    }
    spot = {}
    for code, want in spot_expected.items():
        got = [x["container"] for x in code_map.get(code, [])]
        spot[code] = {"expected": want, "containers": got, "ok": got == [want]}

    out = {
        "universe_sha256": sha256_file(UNIVERSE),
        "n_containers": len(rows),
        "counts_by_asset_class": dict(sorted(by_class.items())),
        "counts_by_arm": dict(by_arm),
        "main_arm_containers": by_arm.get("main", 0),
        "s2_containers": by_arm.get("S2", 0),
        "validate_errors": validate(),
        "duplicate_main_errors": duplicate_execution_errors(rows),
        "execution_rows": sum(len(r.get("execution") or []) for r in rows),
        "unique_execution_codes": len(code_map),
        "file_level_duplicate_codes": file_dups,
        "main_arm_cross_container_duplicates": main_cross_dup,
        "list_date_missing_execution_rows": missing_ld_rows,
        "list_date_missing_unique_codes": len(missing_ld_codes),
        "spot_check_orchestrator_examples": spot,
        "qdii_dash_code_containers": [r["id"] for r in rows if str(r["id"]).startswith("qdii-")],
        "inventory": inventory,
    }
    out_path = Path(__file__).with_suffix(".json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "inventory"}, indent=2, ensure_ascii=False))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

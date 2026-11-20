#!/usr/bin/env python3
"""D38 r46–47：独立重跑四个 preflight JSON 并与 HEAD committed 对照。"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
FFP = CACHE / "49_Industry_Portfolios.csv"
DTB3 = ROOT / "results/v5/other-market/raw/DTB3.csv"
OUT = HERE / "d38-r4647-recalc.json"
PY = ROOT / ".venv/bin/python"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_committed(rel: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=ROOT)


def deep_diff(a, b, path: str = "") -> list[dict]:
    diffs: list[dict] = []
    if type(a) is not type(b):
        diffs.append({"path": path, "kind": "type", "committed": type(b).__name__, "rerun": type(a).__name__})
        return diffs
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else k
            if k not in a:
                diffs.append({"path": p, "kind": "missing_rerun"})
            elif k not in b:
                diffs.append({"path": p, "kind": "missing_committed"})
            else:
                diffs.extend(deep_diff(a[k], b[k], p))
        return diffs
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if float(a) != float(b):
            diffs.append({"path": path, "kind": "numeric", "committed": b, "rerun": a})
        return diffs
    if a != b:
        diffs.append({"path": path, "kind": "value", "committed": b, "rerun": a})
    return diffs


def run_script(module: str, *extra: str) -> None:
    cmd = [str(PY), "-I", str(ROOT / f"scripts/preflight/{module}.py"), str(FFP), str(DTB3), *extra]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


def main() -> int:
    if not FFP.exists():
        print(f"Missing French CSV: {FFP}", file=sys.stderr)
        return 2
    targets = [
        ("topn_dedupe", [], "results/v6-preflight/topn-dedupe.json"),
        ("a_official", [], "results/v6-preflight/a-official.json"),
        ("exec_example", ["2015-08-31", "2013-04-26"], "results/v6-preflight/exec-example.json"),
        ("topn_speed", [], "results/v6-preflight/topn-speed.json"),
    ]
    market_sha = sha256(ROOT / "data/market.sqlite")
    inputs = {
        "market_sqlite_sha256": market_sha,
        "french_49_csv": str(FFP),
        "french_sha256": sha256(FFP),
        "dtb3": str(DTB3),
        "dtb3_sha256": sha256(DTB3),
        "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    pre_r6 = json.loads(
        subprocess.check_output(["git", "show", "b1fde39:results/v6-preflight/a-official.json"], text=True)
    )
    results = {"inputs": inputs, "reruns": {}, "drift_note2": {}}

    for mod, args, rel in targets:
        run_script(mod, *args)
        rerun_path = ROOT / rel
        rerun_bytes = rerun_path.read_bytes()
        committed_bytes = load_committed(rel)
        byte_identical = rerun_bytes == committed_bytes
        rerun = json.loads(rerun_bytes)
        committed = json.loads(committed_bytes)
        diffs = [] if byte_identical else deep_diff(rerun, committed)
        copy = HERE / f"rerun-{Path(rel).name}"
        copy.write_bytes(rerun_bytes)
        results["reruns"][rel] = {
            "byte_identical": byte_identical,
            "diff_count": len(diffs),
            "diffs_sample": diffs[:25],
            "artifact": str(copy.relative_to(ROOT)),
        }
        subprocess.run(["git", "checkout", "--", rel], cwd=ROOT, check=True)

    # Row 39 note 2 drift vs main b1fde39
    run_script("a_official")
    post = json.loads((ROOT / "results/v6-preflight/a-official.json").read_text(encoding="utf-8"))
    subprocess.run(["git", "checkout", "--", "results/v6-preflight/a-official.json"], cwd=ROOT, check=True)
    key = ["R1 设计期整套系统（A 股按发布日校正）", "前3 按把握调节，美股 60%"]
    pre_block = pre_r6
    for k in key:
        pre_block = pre_block[k]
    post_block = post
    for k in key:
        post_block = post_block[k]
    exec_comm = json.loads(load_committed("results/v6-preflight/exec-example.json"))
    results["drift_note2"] = {
        "pre_r6_ref": "b1fde39",
        "design_前3_美股60_pre": pre_block,
        "design_前3_美股60_post": post_block,
        "dev_claimed_design": "12.63% / 71.1 → 13.03% / 71.2",
        "reviewer_derived_pre": {"年化": pre_block["年化"], "最低剩": pre_block["最低剩"]},
        "reviewer_derived_post": {"年化": post_block["年化"], "最低剩": post_block["最低剩"]},
        "a_share_p_2015_08_pre": None,
        "a_share_p_2015_08_post": exec_comm["A 股名额（40%）"]["2015-08-31"]["把握p"],
        "dev_claimed_p": "0.30 → 0.265",
    }
    pre_exec = json.loads(
        subprocess.check_output(["git", "show", "b1fde39:results/v6-preflight/exec-example.json"], text=True)
    )
    results["drift_note2"]["a_share_p_2015_08_pre"] = pre_exec["A 股名额（40%）"]["2015-08-31"]["把握p"]

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    all_ok = all(v["byte_identical"] for v in results["reruns"].values())
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
#!/usr/bin/env python3
"""Reviewer spot-check: Bailey & López de Prado (2014) paper example vs src.v3.eval.sharpe."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.eval.sharpe import deflated_sharpe_ratio


def paper(n_trials: int, skew: float, kurtosis: float) -> dict:
    sr = 2.5 / math.sqrt(250.0)
    variance = 0.5 / 250.0
    return deflated_sharpe_ratio(sr, variance, n_trials, 1250, skew, kurtosis)


def main() -> int:
    main_case = paper(100, -3.0, 10.0)
    out = {
        "source": "Bailey & López de Prado (2014) A Numerical Example",
        "sr0": {"computed": main_case["sr0"], "published": 0.1132},
        "dsr_n100": {"computed": main_case["probability"], "published": 0.9004},
        "dsr_n46": {"computed": paper(46, -3.0, 10.0)["probability"], "published": 0.9505},
        "dsr_normal_n88": {"computed": paper(88, 0.0, 3.0)["probability"], "published": 0.9505},
        "pass": all(
            abs(main_case["sr0"] - 0.1132) < 1e-3
            and abs(main_case["probability"] - 0.9004) < 1e-3
            and abs(paper(46, -3.0, 10.0)["probability"] - 0.9505) < 1e-3
            and abs(paper(88, 0.0, 3.0)["probability"] - 0.9505) < 1e-3
        ),
    }
    print(json.dumps(out, indent=2))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

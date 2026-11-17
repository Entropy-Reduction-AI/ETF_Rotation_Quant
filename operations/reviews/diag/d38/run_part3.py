#!/usr/bin/env python3
"""Reviewer 第 3 部分：R12/R13 压力测试复算并对照 stress.json。"""
from pathlib import Path

from compare_targets import main_part3
from review_stress import run_stress_review

OUT = Path(__file__).parent / "out"


def main():
    run_stress_review(OUT)
    main_part3()
    print("part3 done:", OUT)


if __name__ == "__main__":
    main()
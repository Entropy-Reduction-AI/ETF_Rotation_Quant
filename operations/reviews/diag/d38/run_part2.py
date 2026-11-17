#!/usr/bin/env python3
"""Reviewer 第 2 部分一键复算 R7–R9 并更新对照 JSON。"""
from pathlib import Path

from compare_targets import main_part2
from review_csi300 import run_csi300_review
from review_engine import main_review_r7, main_review_r8

OUT = Path(__file__).parent / "out"


def main():
    main_review_r7(OUT)
    main_review_r8(OUT)
    run_csi300_review(OUT)
    main_part2()
    print("part2 done:", OUT)


if __name__ == "__main__":
    main()
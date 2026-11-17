#!/usr/bin/env python3
"""Reviewer 一键复算 R1–R3 并生成对照 JSON。"""
from pathlib import Path

from compare_targets import main as compare_main
from review_engine import main_review_r1
from review_ic import run_ic_review
from review_longhist import run_longhist_review

OUT = Path(__file__).parent / "out"


def main():
    main_review_r1(OUT)
    run_longhist_review(OUT)
    run_ic_review(OUT)
    compare_main()
    print("done:", OUT)


if __name__ == "__main__":
    main()
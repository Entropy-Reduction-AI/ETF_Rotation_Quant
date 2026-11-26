"""导出 1000 条同结构随机路径的年化。不覆盖已签收的汇总文件。"""

from __future__ import annotations

import json

from src.v6.health_random import export_paths


def main() -> None:
    print(json.dumps(export_paths(), ensure_ascii=False))


if __name__ == "__main__":
    main()

"""config/v3/universe.toml：每个 §3.2 容器都要有这些字段。"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UNIVERSE = ROOT / "config" / "v3" / "universe.toml"

RESEARCH_FIELDS = (
    "index_code",
    "index_name",
    "return_basis",
    "publish_date",
    "publish_date_source",
    "base_date",
    "base_date_source",
    "series_code",
    "series_source",
    "series_status",
    "source_url",
    "note",
)
EXEC_FIELDS = (
    "code",
    "name",
    "list_date",
    "list_date_source",
    "bars_status",
    "track",
    "track_source",
    "note",
)
CONTAINER_FIELDS = (
    "id",
    "asset_class",
    "name",
    "in_pool_index",
    "in_pool_tradable",
)
GAP_STATUS = {"取不到", "TBD"}


def load(path: Path = UNIVERSE) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def containers(doc: dict | None = None) -> list[dict]:
    doc = load() if doc is None else doc
    return list(doc.get("container") or [])


def _block(text: str, container_id: str) -> tuple[int, int]:
    marker = f'id = "{container_id}"'
    start = text.find(marker)
    if start < 0:
        raise KeyError(container_id)
    start = text.rfind("[[container]]", 0, start)
    nxt = text.find("\n[[container]]", start + 1)
    gen = text.find("\n# BEGIN GENERATED", start + 1)
    ends = [n for n in (nxt, gen) if n >= 0]
    end = min(ends) if ends else len(text)
    return start, end


def patch_field(container_id: str, key: str, value: str, *, section: str = "research", path: Path = UNIVERSE) -> None:
    """只改某个容器的一行。不改预注册，不改别的容器。"""
    text = path.read_text(encoding="utf-8")
    start, end = _block(text, container_id)
    block = text[start:end]
    if section == "research":
        sec = block.find("[container.research]")
        if sec < 0:
            raise KeyError(f"{container_id} research")
        region_s = sec
        region_e = len(block)
    else:
        raise ValueError(section)
    region = block[region_s:region_e]
    safe = value.replace('"', "'")
    updated, n = re_sub_line(region, key, f'{key} = "{safe}"')
    if n != 1:
        raise KeyError(f"{container_id} {key} ({n})")
    path.write_text(text[:start] + block[:region_s] + updated + block[region_e:] + text[end:], encoding="utf-8")


def re_sub_line(region: str, key: str, line: str) -> tuple[str, int]:
    pattern = re.compile(rf'(?m)^{re.escape(key)} = ".*"\s*$')
    return pattern.subn(line, region, count=1)


def patch_exec(container_id: str, code: str, key: str, value: str, path: Path = UNIVERSE) -> None:
    """改某一只执行基金的一行。code 必须已经写在该容器下。"""
    text = path.read_text(encoding="utf-8")
    start, end = _block(text, container_id)
    block = text[start:end]
    needle = f'code = "{code}"'
    at = block.find(needle)
    if at < 0:
        raise KeyError(f"{container_id} {code}")
    nxt = block.find("\n[[", at + 1)
    region_e = nxt if nxt >= 0 else len(block)
    region = block[at:region_e]
    safe = value.replace('"', "'")
    updated, n = re_sub_line(region, key, f'{key} = "{safe}"')
    if n != 1:
        raise KeyError(f"{container_id} {code} {key}")
    path.write_text(text[:start] + block[:at] + updated + block[region_e:] + text[end:], encoding="utf-8")


def insert_execution(container_id: str, toml_block: str, path: Path = UNIVERSE) -> None:
    """插到该容器的 `# executions` 注释后面。"""
    text = path.read_text(encoding="utf-8")
    start, end = _block(text, container_id)
    block = text[start:end]
    anchor = "# executions\n"
    at = block.find(anchor)
    if at < 0:
        raise KeyError(f"{container_id} executions")
    path.write_text(text[:start] + block[:at + len(anchor)] + toml_block + block[at + len(anchor):] + text[end:], encoding="utf-8")


def replace_generated(body: str, path: Path = UNIVERSE) -> None:
    text = path.read_text(encoding="utf-8")
    begin = "# BEGIN GENERATED QDII\n"
    end = "# END GENERATED QDII\n"
    i = text.find(begin)
    j = text.find(end)
    if i < 0 or j < 0 or j < i:
        raise RuntimeError("universe.toml 缺少 GENERATED 标记")
    path.write_text(text[:i + len(begin)] + body + text[j:], encoding="utf-8")


def _execution_codes(row: dict) -> list[str]:
    codes = []
    for ex in row.get("execution") or []:
        code = str(ex.get("code") or "")
        if code and code not in {"取不到", "TBD"}:
            codes.append(code)
    return codes


def duplicate_execution_errors(rows: list[dict]) -> list[str]:
    """主臂里同一执行代码只能出现一次。附录 2 的 S2 与主臂不在同一个池，不在这里报。"""
    errors = []
    seen: dict[str, str] = {}
    for row in rows:
        cid = str(row.get("id") or "")
        local: set[str] = set()
        for code in _execution_codes(row):
            if code in local:
                errors.append(f"{cid}: 执行代码 {code} 在本容器重复")
            local.add(code)
            if str(row.get("arm") or "main") != "main":
                continue
            prev = seen.get(code)
            if prev and prev != cid:
                errors.append(f"{code}: 同时出现在主臂容器 {prev} 和 {cid}")
            else:
                seen[code] = cid
    return errors


def validate(doc: dict | None = None) -> list[str]:
    """缺字段才报。取不到 / TBD 是合法取值，不算缺。"""
    doc = load() if doc is None else doc
    errors = []
    seen = set()
    rows = list(doc.get("container") or [])
    for i, row in enumerate(rows):
        cid = row.get("id") or f"#{i}"
        if cid in seen:
            errors.append(f"{cid}: id 重复")
        seen.add(cid)
        for key in CONTAINER_FIELDS:
            if key not in row:
                errors.append(f"{cid}: 缺 {key}")
        research = row.get("research")
        if not isinstance(research, dict):
            errors.append(f"{cid}: 缺 research")
            continue
        for key in RESEARCH_FIELDS:
            if key not in research or research.get(key) is None:
                errors.append(f"{cid}: research 缺 {key}")
        for j, ex in enumerate(row.get("execution") or []):
            for key in EXEC_FIELDS:
                if key not in ex or ex.get(key) is None:
                    errors.append(f"{cid}: execution[{j}] 缺 {key}")
    errors.extend(duplicate_execution_errors(rows))
    return errors

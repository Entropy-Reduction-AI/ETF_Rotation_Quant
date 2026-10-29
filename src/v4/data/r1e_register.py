"""把 v4-R1e 的分组写回登记表。只动被点名的执行代码和因此空掉的主题容器。

不手改别的容器。重跑同一份动作得到同一份文本。
"""
from __future__ import annotations

import re

from src.v3.data.emit_universe import _q

HEADER_LINE = "# v4-R1e：场内 QDII、LOF 的纳入和分组由 python -m src.v4.data r1e 机械写入。\n"
V4_MARKER = "# D19-4 v4-R1e 场内 QDII、LOF"


def split_containers(text: str, footer_mark: str = "\n# 附录 1 排除") -> tuple[str, list[str], str]:
    at = text.find(footer_mark)
    if at < 0:
        body, footer = text, ""
    else:
        body, footer = text[:at + 1], text[at + 1:]
    parts = re.split(r"(?=^\[\[container\]\]$)", body, flags=re.M)
    return parts[0], [part for part in parts[1:] if part.strip()], footer


def container_id(block: str) -> str:
    match = re.search(r'(?m)^id = "([^"]+)"', block)
    return match.group(1) if match else ""


def split_executions(block: str) -> tuple[str, list[tuple[str, str]]]:
    parts = re.split(r"(?=^\[\[container\.execution\]\]$)", block, flags=re.M)
    head, execs = parts[0], []
    for part in parts[1:]:
        match = re.search(r'(?m)^code = "(\d{6})"', part)
        if not match:
            head += part
            continue
        if not part.endswith("\n"):
            part += "\n"
        execs.append((match.group(1), part))
    return head, execs


def _note_append(block: str, sentence: str) -> str:
    sentence = sentence.strip()
    if not sentence or sentence in block:
        return block

    def repl(match: re.Match) -> str:
        current = match.group(1)
        if sentence in current:
            return match.group(0)
        return f'note = "{current} {sentence}"'

    return re.sub(r'(?m)^note = "(.*)"\s*$', repl, block, count=1)


def render_execution(action: dict) -> str:
    fields = (
        ("code", action["code"]),
        ("name", action.get("name") or ""),
        ("list_date", action.get("list_date") or "取不到"),
        ("list_date_source", action.get("list_date_source") or ""),
        ("bars_status", action.get("bars_status") or "取不到"),
        ("track", action.get("track") or "取不到"),
        ("track_source", action.get("track_source") or ""),
        ("note", action.get("note") or ""),
    )
    lines = ["[[container.execution]]"]
    lines.extend(f'{key} = "{_q(str(value))}"' for key, value in fields)
    return "\n".join(lines) + "\n"


def render_container(action: dict) -> str:
    research = action["research"]
    lines = [
        "[[container]]",
        f'id = "{_q(action["target_id"])}"',
        f'asset_class = "{_q(action.get("asset_class") or "美股和全球主题")}"',
        f'name = "{_q(action.get("target_name") or action["target_id"])}"',
        'arm = "main"',
        "in_pool_index = true",
        "in_pool_tradable = true",
        "",
        "[container.research]",
    ]
    for key in (
        "index_code", "index_name", "return_basis", "publish_date", "publish_date_source",
        "base_date", "base_date_source", "series_code", "series_source", "series_status",
        "source_url", "note",
    ):
        lines.append(f'{key} = "{_q(str(research.get(key) or ""))}"')
    lines.append("")
    return "\n".join(lines) + "\n"


def _refresh_execution(chunk: str, action: dict) -> str:
    listed = action.get("list_date") or ""
    if listed and listed != "取不到" and 'list_date = "取不到"' in chunk:
        chunk = chunk.replace('list_date = "取不到"', f'list_date = "{listed}"', 1)
        source = action.get("list_date_source") or ""
        if source:
            chunk = re.sub(
                r'(?m)^list_date_source = ".*"\s*$',
                f'list_date_source = "{_q(source)}"',
                chunk,
                count=1,
            )
    sentence = f"D19 分组：{action.get('group_key') or ''}（{action.get('group_rule') or ''}）。"
    return _note_append(chunk, sentence)


def apply_register(text: str, actions: list[dict]) -> str:
    """actions 里每只基金一条。target_id 已决定。create 为真时连容器头一起写。"""
    if HEADER_LINE.strip() not in text:
        text = text.replace("\n", "\n" + HEADER_LINE, 1) if text.startswith("#") else HEADER_LINE + text
    header, blocks, footer = split_containers(text)
    order: list[str] = []
    parsed: dict[str, list] = {}
    nonempty: set[str] = set()
    for block in blocks:
        cid = container_id(block)
        if not cid or cid in parsed:
            raise RuntimeError(f"登记表容器 id 无法拆开：{cid or '空'}")
        head, execs = split_executions(block)
        parsed[cid] = [head, execs]
        order.append(cid)
        if execs:
            nonempty.add(cid)
    for action in actions:
        code = str(action["code"])
        target = action["target_id"]
        if target not in parsed:
            if not action.get("create"):
                raise RuntimeError(f"{code} 要并入不存在的容器 {target}")
            parsed[target] = [render_container(action), []]
            order.append(target)
        current = next((cid for cid, (_head, execs) in ((cid, parsed[cid]) for cid in order) if any(item[0] == code for item in execs)), "")
        if current == target:
            parsed[target][1] = [
                (item_code, _refresh_execution(chunk, action) if item_code == code else chunk)
                for item_code, chunk in parsed[target][1]
            ]
            parsed[target][0] = _note_append(
                parsed[target][0],
                f"D19 分组：{action.get('group_key') or ''}（{action.get('group_rule') or ''}）。",
            )
            continue
        if current:
            parsed[current][1] = [item for item in parsed[current][1] if item[0] != code]
        chunk = _refresh_execution(render_execution(action), action)
        parsed[target][1].append((code, chunk))
        parsed[target][0] = _note_append(
            parsed[target][0],
            f"D19 分组：{action.get('group_key') or ''}（{action.get('group_rule') or ''}）。",
        )
    kept = []
    for cid in order:
        head, execs = parsed[cid]
        if cid in nonempty and not execs and cid.startswith("theme-"):
            continue
        body = head.rstrip() + "\n"
        for _code, chunk in execs:
            if not body.endswith("\n\n"):
                body += "\n"
            body += chunk if chunk.endswith("\n") else chunk + "\n"
        if not body.endswith("\n"):
            body += "\n"
        kept.append(body)
    included = {str(action["code"]) for action in actions}
    foot_lines = []
    for line in footer.splitlines(keepends=True):
        match = re.match(r"# (\d{6}) ", line)
        if match and match.group(1) in included and "exclude:" in line:
            continue
        foot_lines.append(line)
    return header + "".join(kept) + "".join(foot_lines)


def _v4_block(record: dict) -> str:
    lines = [
        "[[container]]",
        f'id = "qdii-{record["code"]}"',
        'market = "CN"',
        'instrument_type = "qdii_etf"',
        f'name = "{_q(record.get("name") or "")}"',
        f'code = "{record["code"]}"',
        f'maps_to = "{_q(record.get("maps_to") or "")}"',
        f'tracked_index = "{_q(record.get("tracked_index") or "")}"',
        'return_basis = "unit_nav"',
        'currency = "CNY"',
        f'source = "{_q(record.get("source") or "")}"',
        f'source_url = "{_q(record.get("source_url") or "")}"',
        f'status = "{_q(record.get("status") or "取不到")}"',
        f'official_launch = "{_q(record.get("official_launch") or "取不到")}"',
        f'first_date = "{_q(record.get("first_date") or "")}"',
        f'last_date = "{_q(record.get("last_date") or "")}"',
        f'rows = "{record.get("rows") or 0}"',
        f'sha256 = "{_q(record.get("sha256") or "")}"',
        'note = "D19-4 场内 QDII、LOF 普查机械纳入。本行只同步名单。不计算收益。"',
        "",
    ]
    return "\n".join(lines)


def apply_v4(text: str, records: list[dict]) -> str:
    """已有 qdii-代码 只改 maps_to 和 tracked_index。没有的追加到文末标记段，重跑替换这一段。"""
    if V4_MARKER in text:
        text = text[:text.index(V4_MARKER)].rstrip() + "\n"
    header, blocks, footer = split_containers(text, footer_mark="\n__no_such_footer__")
    by_code = {row["code"]: row for row in records}
    rewritten = []
    seen = set()
    for block in blocks:
        match = re.search(r'(?m)^id = "qdii-(\d{6})"', block)
        code = match.group(1) if match else ""
        if code and code in by_code:
            row = by_code[code]
            block = re.sub(r'(?m)^maps_to = ".*"\s*$', f'maps_to = "{_q(row.get("maps_to") or "")}"', block, count=1)
            if re.search(r'(?m)^tracked_index = ', block):
                block = re.sub(
                    r'(?m)^tracked_index = ".*"\s*$',
                    f'tracked_index = "{_q(row.get("tracked_index") or "")}"',
                    block,
                    count=1,
                )
            seen.add(code)
        rewritten.append(block if block.endswith("\n") else block + "\n")
    extra = [row for row in records if row["code"] not in seen]
    tail = ""
    if extra:
        tail = "\n" + V4_MARKER + "\n# 普查新纳入的场内代码。重跑只替换这一段。没有组合收益。\n\n"
        tail += "\n".join(_v4_block(row) for row in extra)
    return header + "".join(rewritten) + footer + tail

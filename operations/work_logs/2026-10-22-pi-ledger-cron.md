# 旧台账 cron 停用核实

## Metadata

- Project: ETF_Rotation_Quant
- Task: 核实旧台账两条 cron 已停用
- Timestamp (UTC): 2026-10-22T09:47:04Z
- Owner: project owner
- Route: direct-execute
- Source of truth: Owner 本次 cron 核实指令

## 结果与范围

- 服务器：`anolis`；当前用户：`levi_luo`。核实范围为该用户的 `crontab -l`，不扩展到其他用户或系统调度。
- 旧台账两行原来均不在，现在也均不在。现有两条任务属于另一项目，未改动。
- 因目标任务已不存在，跳过 `crontab -e`；未执行任何 crontab 写入命令，未使用文件覆盖整表。
- 未重启任何服务，未读取或修改旧仓库 ETF_Opportunity_Ledger。
- 在本仓库执行 `git pull --ff-only origin main` 成功，快进至 `3e1a6670d320e21bec9596777c610f2cbf12fa61`；未合并或 rebase。拉取后工作区干净，本次仅新增本记录，不改其他文件。

## 执行前 crontab 原文

命令：`crontab -l > /tmp/cron-before.txt`，退出码 0。

```text
# BEGIN teardown-ingest (physical-first)
CRON_TZ=Asia/Shanghai
35 15 * * 1-5 cd /project/data_science/serenity_quant_research/api && (set -a; . /home/levi_luo/.config/teardown/runtime.env; set +a; /usr/bin/flock -n /project/data_science/serenity_quant_research/artifacts/runtime/ingest.lock /project/data_science/serenity_quant_research/api/.venv/bin/python -u -m app.ingest daily) >> /project/data_science/serenity_quant_research/artifacts/runtime/teardown-ingest.log 2>&1
15 */3 * * * cd /project/data_science/serenity_quant_research/api && (set -a; . /home/levi_luo/.config/teardown/runtime.env; set +a; /usr/bin/flock -n /project/data_science/serenity_quant_research/artifacts/runtime/ingest.lock /project/data_science/serenity_quant_research/api/.venv/bin/python -u -m app.ingest news) >> /project/data_science/serenity_quant_research/artifacts/runtime/teardown-ingest.log 2>&1
# END teardown-ingest

```

## 执行后 crontab 原文

命令：`crontab -l > /tmp/cron-after.txt`，退出码 0。

```text
# BEGIN teardown-ingest (physical-first)
CRON_TZ=Asia/Shanghai
35 15 * * 1-5 cd /project/data_science/serenity_quant_research/api && (set -a; . /home/levi_luo/.config/teardown/runtime.env; set +a; /usr/bin/flock -n /project/data_science/serenity_quant_research/artifacts/runtime/ingest.lock /project/data_science/serenity_quant_research/api/.venv/bin/python -u -m app.ingest daily) >> /project/data_science/serenity_quant_research/artifacts/runtime/teardown-ingest.log 2>&1
15 */3 * * * cd /project/data_science/serenity_quant_research/api && (set -a; . /home/levi_luo/.config/teardown/runtime.env; set +a; /usr/bin/flock -n /project/data_science/serenity_quant_research/artifacts/runtime/ingest.lock /project/data_science/serenity_quant_research/api/.venv/bin/python -u -m app.ingest news) >> /project/data_science/serenity_quant_research/artifacts/runtime/teardown-ingest.log 2>&1
# END teardown-ingest

```

## diff 输出

命令：`diff /tmp/cron-before.txt /tmp/cron-after.txt`。
退出码 0；标准输出、标准错误均为空，前后完全一致。以下为空的实际标准输出：

```text
```

## 交付

仅提交本文件至 main，普通推送，不 force push。快进拉取带来的既有项目内容不属于本次改动；本次不运行代码、研究或依赖安装。

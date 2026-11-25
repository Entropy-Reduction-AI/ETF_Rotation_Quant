# PR339 R1b reproducible commands (Reviewer 2026-11-24)
# overlay: /tmp/v6-r1b-overlay ; data: main LFS 02458762… copied to overlay/data/market.sqlite

sha256sum /tmp/market-r1b-main.sqlite
sqlite3 /tmp/market-r1b-main.sqlite "SELECT code, MAX(date) FROM bars WHERE adj='raw' AND code IN ('DJIA','DWRTF') GROUP BY code; SELECT COUNT(*) FROM bars WHERE date='2024-12-25' AND code IN ('DJIA','DWRTF');"

cd /tmp/v6-r1b-overlay
/agent/repos/ETF_Rotation_Quant/.venv/bin/python -I scripts/preflight/v6_appendix_a.py
cmp /tmp/v6-r1b-appendix-a-subject.csv /tmp/v6-r1b-appendix-a-rerun.csv || true

/agent/repos/ETF_Rotation_Quant/.venv/bin/python -I scripts/preflight/v6_appendix_b.py \
  operations/reviews/diag/v6-r1b-cache/49_Industry_Portfolios.csv \
  results/v5/other-market/raw/DTB3.csv
sha256sum results/v6-preflight/v6-appendix-b.json

/agent/repos/ETF_Rotation_Quant/.venv/bin/python scripts/owner_page_lint.py docs/artifact/v6-prereg/index.html
/agent/repos/ETF_Rotation_Quant/.venv/bin/python scripts/owner_pages/story_check.py docs/artifact/v6-prereg/index.html

/agent/repos/ETF_Rotation_Quant/.venv/bin/python /agent/repos/ETF_Rotation_Quant/operations/reviews/pr339-r1b-audit.py
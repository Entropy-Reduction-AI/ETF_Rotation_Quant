# 期权日线完全重复行

统计对象是既有 `data/options/raw/sse/ohlcv` 与 `data/options/raw/szse/ohlcv`，本轮没有改这些文件。

完全重复指同一个 `(contract_id, date)` 出现多行，且 `security_id, open, high, low, close, volume` 全部相同。多出来的那些行（每个键保留第一行之后的行数）如下。

| 文件 | 完全相同的多余行 | 内容不同的多余行 | 唯一键 |
| --- | ---: | ---: | ---: |
| `data/options/raw/sse/ohlcv/510050.csv` | 18812 | 0 | 354538 |
| `data/options/raw/sse/ohlcv/510300.csv` | 4802 | 0 | 193198 |
| `data/options/raw/sse/ohlcv/510500.csv` | 3644 | 0 | 112156 |
| `data/options/raw/sse/ohlcv/588000.csv` | 3169 | 0 | 87585 |
| `data/options/raw/sse/ohlcv/588080.csv` | 3101 | 0 | 85391 |
| `data/options/raw/sse/ohlcv/unmapped.csv` | 7 | 14050 | 162 |
| `data/options/raw/szse/ohlcv/159901.csv` | 4051 | 0 | 97354 |
| `data/options/raw/szse/ohlcv/159915.csv` | 4462 | 0 | 118087 |
| `data/options/raw/szse/ohlcv/159919.csv` | 3600 | 0 | 100521 |
| `data/options/raw/szse/ohlcv/159922.csv` | 3381 | 0 | 102674 |
| `data/options/raw/szse/ohlcv/unmapped.csv` | 2 | 7956 | 53 |

完全相同的多余行合计 **49031**。其中上交所 510050 单文件就是大约 1.9 万行，和事先说的约 1.9 万同一量级；六份标的文件加在一起比这个数大。

内容不同的多余行合计 **22006**，集中在 `unmapped.csv`。这些不是完全重复，清洗时不能按完全重复直接删掉。

清洗会去掉完全相同的多余行。原始文件保持不动，去重放在以后的清洗步骤，不在本轮改 raw。

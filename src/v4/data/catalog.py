"""v4-R1 要登记的容器。数字只写已经核对过的官方日期。"""
from __future__ import annotations

from datetime import date

# 与库内研究序列同一截止日。不把 2026-10 写进库。
END = date(2026, 9, 30)

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TENCENT = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
CHINAMONEY = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-ccpr/CcprHisNew"
CATALOGUE = "https://www.hsi.com.hk/static/uploads/contents/en/dl_centre/index_catalogue/index_catalogue.pdf"
GICS_RE = "https://www.msci.com/documents/10199/6aac98e5-a0f6-485c-ad7c-20394024e07f"
GICS_COMM = (
    "https://www.msci.com/documents/1296102/1339060/"
    "GICS-S%26P-Dow+Jones-Indices+and-MSCI-announce-updates-to+list-of-companies-changing-due-to-revisions-to-the-GICS-structure-September-2018.pdf"
)

# 房地产：GICS 在美东 2016-08-31 收盘后独立。通信服务：GICS Direct 在美东 2018-09-28 收盘后生效；
# 标普指数在 2018-09-24 开盘实施。见上面两份 MSCI/S&P 公告。
RE_EFFECTIVE = "2016-08-31"
COMM_EFFECTIVE = "2018-09-28"

ETFS = (
    {"container_id": "us-xlb", "code": "XLB", "gics": "15", "sector": "Materials", "gics_effective": "",
     "inception": "1998-12-16", "name": "Materials Select Sector SPDR"},
    {"container_id": "us-xle", "code": "XLE", "gics": "10", "sector": "Energy", "gics_effective": "",
     "inception": "1998-12-16", "name": "Energy Select Sector SPDR"},
    {"container_id": "us-xlf", "code": "XLF", "gics": "40", "sector": "Financials", "gics_effective": RE_EFFECTIVE,
     "inception": "1998-12-16", "name": "Financial Select Sector SPDR"},
    {"container_id": "us-xli", "code": "XLI", "gics": "20", "sector": "Industrials", "gics_effective": "",
     "inception": "1998-12-16", "name": "Industrial Select Sector SPDR"},
    {"container_id": "us-xlk", "code": "XLK", "gics": "45", "sector": "Information Technology", "gics_effective": COMM_EFFECTIVE,
     "inception": "1998-12-16", "name": "Technology Select Sector SPDR"},
    {"container_id": "us-xlp", "code": "XLP", "gics": "30", "sector": "Consumer Staples", "gics_effective": "",
     "inception": "1998-12-16", "name": "Consumer Staples Select Sector SPDR"},
    {"container_id": "us-xlu", "code": "XLU", "gics": "55", "sector": "Utilities", "gics_effective": "",
     "inception": "1998-12-16", "name": "Utilities Select Sector SPDR"},
    {"container_id": "us-xlv", "code": "XLV", "gics": "35", "sector": "Health Care", "gics_effective": "",
     "inception": "1998-12-16", "name": "Health Care Select Sector SPDR"},
    {"container_id": "us-xly", "code": "XLY", "gics": "25", "sector": "Consumer Discretionary", "gics_effective": COMM_EFFECTIVE,
     "inception": "1998-12-16", "name": "Consumer Discretionary Select Sector SPDR"},
    {"container_id": "us-xlre", "code": "XLRE", "gics": "60", "sector": "Real Estate", "gics_effective": RE_EFFECTIVE,
     "inception": "2015-10-07", "name": "Real Estate Select Sector SPDR"},
    {"container_id": "us-xlc", "code": "XLC", "gics": "50", "sector": "Communication Services", "gics_effective": COMM_EFFECTIVE,
     "inception": "2018-06-18", "name": "Communication Services Select Sector SPDR"},
)

# Yahoo 有全收益符号，但 chart 的 validRanges 只有 1d/5d，按日期拉取没有日线。
# 能源价格指数符号是 ^GSPE；^SP500-10 返回 404。全收益符号仍是 ^SP500-10TR。
SP_TR = (
    {"container_id": "sp500-tr-10", "code": "SP500-10TR", "yahoo": "^SP500-10TR", "gics": "10", "sector": "Energy", "gics_effective": ""},
    {"container_id": "sp500-tr-15", "code": "SP500-15TR", "yahoo": "^SP500-15TR", "gics": "15", "sector": "Materials", "gics_effective": ""},
    {"container_id": "sp500-tr-20", "code": "SP500-20TR", "yahoo": "^SP500-20TR", "gics": "20", "sector": "Industrials", "gics_effective": ""},
    {"container_id": "sp500-tr-25", "code": "SP500-25TR", "yahoo": "^SP500-25TR", "gics": "25", "sector": "Consumer Discretionary", "gics_effective": COMM_EFFECTIVE},
    {"container_id": "sp500-tr-30", "code": "SP500-30TR", "yahoo": "^SP500-30TR", "gics": "30", "sector": "Consumer Staples", "gics_effective": ""},
    {"container_id": "sp500-tr-35", "code": "SP500-35TR", "yahoo": "^SP500-35TR", "gics": "35", "sector": "Health Care", "gics_effective": ""},
    {"container_id": "sp500-tr-40", "code": "SP500-40TR", "yahoo": "^SP500-40TR", "gics": "40", "sector": "Financials", "gics_effective": RE_EFFECTIVE},
    {"container_id": "sp500-tr-45", "code": "SP500-45TR", "yahoo": "^SP500-45TR", "gics": "45", "sector": "Information Technology", "gics_effective": COMM_EFFECTIVE},
    {"container_id": "sp500-tr-50", "code": "SP500-50TR", "yahoo": "^SP500-50TR", "gics": "50", "sector": "Communication Services", "gics_effective": COMM_EFFECTIVE},
    {"container_id": "sp500-tr-55", "code": "SP500-55TR", "yahoo": "^SP500-55TR", "gics": "55", "sector": "Utilities", "gics_effective": ""},
    {"container_id": "sp500-tr-60", "code": "SP500-60TR", "yahoo": "^SP500-60TR", "gics": "60", "sector": "Real Estate", "gics_effective": RE_EFFECTIVE},
)

# 唯一能按日取到的是房地产价格指数，不是全收益。
SP_PRICE_AVAILABLE = {
    "container_id": "sp500-60",
    "code": "SP500-60",
    "yahoo": "^SP500-60",
    "gics": "60",
    "sector": "Real Estate",
    "gics_effective": RE_EFFECTIVE,
    "name": "S&P 500 Real Estate (Sector)",
}

# 恒生指数四个分类指数。指数目录 2026-03-31：首个指数点 1984-01-13，发布 1985-01-02。
# 恒生综合行业指数 12 个在目录里有代码，腾讯和 Yahoo 没有日线。
HSI_SUB = (
    {"container_id": "hk-hsf", "code": "HSF", "tr_code": "HSFGTR", "tencent": "hkHSF", "tr_tencent": "hkHSFGTR",
     "name": "恒生金融分类指数", "tr_name": "恒生金融分类指数（总收益）"},
    {"container_id": "hk-hsu", "code": "HSU", "tr_code": "HSUGTR", "tencent": "hkHSU", "tr_tencent": "hkHSUGTR",
     "name": "恒生公用事业分类指数", "tr_name": "恒生公用事业分类指数（总收益）"},
    {"container_id": "hk-hsp", "code": "HSP", "tr_code": "HSPGTR", "tencent": "hkHSP", "tr_tencent": "hkHSPGTR",
     "name": "恒生地产分类指数", "tr_name": "恒生地产分类指数（总收益）"},
    {"container_id": "hk-hsc", "code": "HSC", "tr_code": "HSCGTR", "tencent": "hkHSC", "tr_tencent": "hkHSCGTR",
     "name": "恒生工商分类指数", "tr_name": "恒生工商分类指数（总收益）"},
)
HSI_FIRST_VALUE = "1984-01-13"
HSI_LAUNCH = "1985-01-02"

# 指数目录 2026-03-31。发布日与 2006-09-11 的行业指数总述、以及数据产品手册里
# 可选消费/必需消费/医疗 2019-09-09 的说法不一致，这里只登记目录上的日期。
HSCI = (
    {"code": "HSCIE", "name": "恒生综合行业指数-能源业", "launch": "2006-09-11"},
    {"code": "HSCIM", "name": "恒生综合行业指数-原材料业", "launch": "2006-09-11"},
    {"code": "HSCIIG", "name": "恒生综合行业指数-工业", "launch": "2006-09-11"},
    {"code": "HSCICD", "name": "恒生综合行业指数-非必需性消费", "launch": "2001-10-03"},
    {"code": "HSCICS", "name": "恒生综合行业指数-必需性消费", "launch": "2001-10-03"},
    {"code": "HSCIH", "name": "恒生综合行业指数-医疗保健业", "launch": "2001-10-03"},
    {"code": "HSCIT", "name": "恒生综合行业指数-电讯业", "launch": "2006-09-11"},
    {"code": "HSCIU", "name": "恒生综合行业指数-公用事业", "launch": "2001-10-03"},
    {"code": "HSCIF", "name": "恒生综合行业指数-金融业", "launch": "2001-10-03"},
    {"code": "HSCIPC", "name": "恒生综合行业指数-地产建筑业", "launch": "2001-10-03"},
    {"code": "HSCIIT", "name": "恒生综合行业指数-资讯科技业", "launch": "2001-10-03"},
    {"code": "HSCIC", "name": "恒生综合行业指数-综合企业", "launch": "2001-10-03"},
)
HSCI_BASE = "2000-01-03"

SENTINELS = ("H00300", "USDCNY", "510300", "HSI", "^SP500TR")

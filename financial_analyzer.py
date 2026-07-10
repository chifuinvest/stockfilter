# -*- coding: utf-8 -*-
"""
财报分析模块
- 估值指标：PE(TTM)、PB、PS(TTM)、股息率
- 盈利能力：ROE、ROA、毛利率、净利率
- 成长能力：营收同比、净利润同比
- 财务健康：资产负债率、流动比率
- 输出：分项得分（0-100）+ 财报综合分（0-100）

数据源：
  - A/H 股：Tushare (daily_basic + fina_indicator) + Yahoo info 兜底
  - 美股：Yahoo Finance info

免责声明：本系统输出仅供研究和学习使用，不构成任何投资建议。
          市场有风险，投资需谨慎，实盘盈亏自负，版权方不承担法律责任。
版权所有 (c) 2025 Bart · 联系方式：yanying76@gmail.com
"""
import os
import sys
import time
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("financial_analyzer")

_BASE_DIR = Path(__file__).resolve().parent
_CACHE_DIR = _BASE_DIR / "data_cache" / "financial_v1"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_HOURS = 12


# ============ 复用 data_fetcher_v2 的 Tushare / Yahoo 初始化 ============
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

_TS_OK = False
_ts_pro = None
_YF_OK = False
yf = None


def _ensure_backend():
    global _TS_OK, _ts_pro, _YF_OK, yf
    if _TS_OK or _YF_OK:
        return
    try:
        import data_fetcher_v2 as dfv2
        _TS_OK = getattr(dfv2, "_TS_OK", False)
        _ts_pro = getattr(dfv2, "_ts_pro", None)
        _YF_OK = getattr(dfv2, "_YF_OK", False)
        yf = getattr(dfv2, "yf", None)
    except Exception as e:
        logger.warning(f"复用 data_fetcher_v2 后端失败: {e}，尝试独立初始化...")
    # 兜底：自己初始化一次
    if not _YF_OK:
        try:
            import yfinance as _yf
            yf = _yf
            _YF_OK = True
        except Exception:
            pass
    if not _TS_OK:
        try:
            from data_fetcher_v2 import _init_tushare, _TS_OK as t_ok, _ts_pro as t_p
            _init_tushare()
            _TS_OK = t_ok
            _ts_pro = t_p
        except Exception:
            pass


# ============ 缓存 ============
def _cache_path(yf_code: str) -> Path:
    safe = yf_code.replace("/", "_").replace(":", "_")
    return _CACHE_DIR / f"{safe}.pkl"


def _cache_valid(p: Path) -> bool:
    if not p.exists():
        return False
    try:
        age = time.time() - p.stat().st_mtime
        return age < _CACHE_TTL_HOURS * 3600
    except Exception:
        return False


def _read_cache(yf_code: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(yf_code)
    if not _cache_valid(p):
        return None
    try:
        with open(p, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        logger.warning(f"读取财报缓存失败 {yf_code}: {e}")
    return None


def _write_cache(yf_code: str, data: Dict[str, Any]) -> None:
    try:
        with open(_cache_path(yf_code), "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        logger.warning(f"写入财报缓存失败 {yf_code}: {e}")


# ============ 代码转换 ============
def _market_of(yf_code: str) -> str:
    c = yf_code.upper()
    if c.endswith(".SS") or c.endswith(".SZ"):
        return "CN"
    if c.endswith(".HK"):
        return "HK"
    if c.endswith(".KS") or c.endswith(".KQ"):
        return "KR"
    return "US"


def _yf_to_ts_code(yf_code: str) -> Optional[str]:
    c = yf_code.strip()
    up = c.upper()
    if up.endswith(".SS"):
        return up.replace(".SS", ".SH")
    if up.endswith(".SZ"):
        return up
    if up.endswith(".HK"):
        num_part = c[:-3]
        try:
            num = int(num_part)
            return f"{num:05d}.HK"
        except Exception:
            return up
    return None


# ============ Yahoo Finance info 字段解析 ============
_YF_INFO_KEYS = {
    "pe_ttm": ["trailingPE", "trailingPE", "peTrailing"],
    "pe_fwd": ["forwardPE"],
    "pb": ["priceToBook", "bookValuePerShare"],
    "ps_ttm": ["priceToSalesTrailing12Months", "priceToSales"],
    "div_yield": ["dividendYield", "yield"],
    "roe": ["returnOnEquity"],
    "roa": ["returnOnAssets"],
    "gross_margin": ["grossMargins", "grossProfitMargins"],
    "net_margin": ["profitMargins", "netIncomeToCommon"],
    "revenue_yoy": ["revenueGrowth"],
    "earnings_yoy": ["earningsGrowth"],
    "debt_ratio": ["debtToEquity", "debtToAssets"],
    "current_ratio": ["currentRatio"],
    "market_cap": ["marketCap"],
    "total_revenue": ["totalRevenue"],
    "net_income": ["netIncomeToCommon"],
    "total_cash": ["totalCash"],
    "total_debt": ["totalDebt"],
}


def _from_info(info: Dict[str, Any], key: str) -> Optional[float]:
    if not info or not isinstance(info, dict):
        return None
    for alias in _YF_INFO_KEYS.get(key, []):
        v = info.get(alias)
        if v is not None and v != "N/A":
            try:
                f = float(v)
                if np.isfinite(f):
                    if key in ("roe", "roa", "gross_margin", "net_margin",
                               "revenue_yoy", "earnings_yoy", "div_yield"):
                        if -5.0 <= f <= 5.0:
                            f = f * 100.0
                    if key == "debt_ratio":
                        if 0 <= f <= 10:
                            f = f * 10.0
                    return f
            except Exception:
                continue
    return None


# ============ Tushare 财报拉取 ============
def _fetch_via_tushare(yf_code: str) -> Optional[Dict[str, Any]]:
    """通过 Tushare 获取 A/H 股每日指标 + 财务指标"""
    _ensure_backend()
    if not _TS_OK or _ts_pro is None:
        return None
    mkt = _market_of(yf_code)
    if mkt not in ("CN", "HK"):
        return None
    ts_code = _yf_to_ts_code(yf_code)
    if not ts_code:
        return None

    out: Dict[str, Any] = {}
    _now = datetime.now()
    end_date = _now.strftime("%Y%m%d")
    # --- 修复：原只查半年，现扩展到 2.5 年前覆盖 8 个季度 + 2 个完整年度
    start_date = (_now.replace(year=_now.year - 2) if _now.month * 100 + _now.day <= 630
                  else _now.replace(year=_now.year - 3)).strftime("%Y%m%d")

    # 1) daily_basic (估值 + 换手率 + 市值)
    try:
        if mkt == "CN":
            db = _ts_pro.daily_basic(ts_code=ts_code, end_date=end_date,
                                     fields="ts_code,trade_date,pe,pe_ttm,pb,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv,turnover_rate",
                                     limit=80)
        else:
            db = _ts_pro.hk_dailybasic(ts_code=ts_code, end_date=end_date,
                                        fields="ts_code,trade_date,pe,pb,total_mv,turnover_ratio",
                                        limit=80)
        if isinstance(db, pd.DataFrame) and len(db) > 0:
            row = db.iloc[0]
            if "pe_ttm" in row:
                out["pe_ttm"] = float(row["pe_ttm"]) if pd.notna(row["pe_ttm"]) else None
            if "pe" in row:
                out.setdefault("pe_ttm", float(row["pe"]) if pd.notna(row["pe"]) else None)
            if "pb" in row and pd.notna(row["pb"]):
                out["pb"] = float(row["pb"])
            if "ps_ttm" in row and pd.notna(row["ps_ttm"]):
                out["ps_ttm"] = float(row["ps_ttm"])
            if "dv_ratio" in row and pd.notna(row["dv_ratio"]):
                out["div_yield"] = float(row["dv_ratio"])
            elif "dv_ttm" in row and pd.notna(row["dv_ttm"]):
                out.setdefault("div_yield", float(row["dv_ttm"]))
            if "total_mv" in row and pd.notna(row["total_mv"]):
                out["market_cap"] = float(row["total_mv"]) * 10000.0  # 万元 → 元
    except Exception as e:
        logger.info(f"[Tushare daily_basic] {yf_code} 失败: {e}")

    # 2) fina_indicator (ROE/ROA/毛利率/成长等) — 最近 8 个报告期
    #    修复：每个字段独立遍历取「按报告期倒序后第一个非空值」，避免单期缺字段漏数据
    try:
        if mkt == "CN":
            fi = _ts_pro.fina_indicator(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                         fields="ts_code,end_date,roe,roe_dt,roa,grossprofit_margin,netprofit_margin,"
                                                "revenue_yoy,profit_yoy,debt_to_assets,current_ratio")
        else:
            fi = _ts_pro.hk_finindicator(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                          fields="ts_code,end_date,roe,roa,gross_profit_margin,"
                                                 "net_profit_margin,revenue_yoy,net_profit_yoy,debt_ratio,current_ratio",
                                          limit=16)
        if isinstance(fi, pd.DataFrame) and len(fi) > 0:
            fi = fi.drop_duplicates(subset=["end_date"], keep="first")
            fi = fi.sort_values("end_date", ascending=False).reset_index(drop=True)
            key_map = {
                "roe": ["roe", "roe_dt"],
                "roa": ["roa"],
                "gross_margin": ["grossprofit_margin", "gross_profit_margin"],
                "net_margin": ["netprofit_margin", "net_profit_margin"],
                "revenue_yoy": ["revenue_yoy"],
                "earnings_yoy": ["profit_yoy", "net_profit_yoy"],
                "debt_ratio": ["debt_to_assets", "debt_ratio"],
                "current_ratio": ["current_ratio"],
            }
            # --- 每个 out_key 独立遍历所有行：第一个非空就是最新披露值
            for out_key, aliases in key_map.items():
                for ak in aliases:
                    if ak not in fi.columns:
                        continue
                    col = fi[ak]
                    good = col[pd.notna(col)]
                    if len(good) > 0:
                        try:
                            out[out_key] = float(good.iloc[0])
                            break
                        except Exception:
                            continue
    except Exception as e:
        logger.info(f"[Tushare fina_indicator] {yf_code} 失败: {e}")

    return out if out else None


# ============ Yahoo Finance 三表自算（兜底） ============
def _first(df: pd.DataFrame, index_names, col_ordered):
    """按列日期倒序取第一个非空单元格；index_names 为候选行名（任一命中即可）"""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None, None
    cols = sorted(df.columns.tolist(), reverse=True)
    if not cols:
        return None, None
    row_idx = None
    for nm in index_names:
        if nm in df.index:
            row_idx = nm
            break
    if row_idx is None:
        return None, cols[0] if len(cols) else None
    for c in col_ordered if col_ordered else cols:
        try:
            v = df.at[row_idx, c]
        except Exception:
            continue
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            continue
        try:
            f = float(v)
            if np.isfinite(f):
                return f, c
        except Exception:
            continue
    return None, cols[0]


def _fetch_via_yf_statements(yf_code: str) -> Optional[Dict[str, Any]]:
    """
    Yahoo Finance 三表自算：从 income_stmt / balance_sheet 计算 8 项核心财务指标（%）。
    当 ticker.info 限流/缺字段时作为兜底，覆盖：
      gross_margin, net_margin, revenue_yoy, earnings_yoy,
      debt_ratio, current_ratio, roe, roa
    """
    _ensure_backend()
    if not _YF_OK or yf is None:
        return None
    try:
        ticker = yf.Ticker(yf_code)
    except Exception as e:
        logger.info(f"[YF statements] {yf_code} 创建 Ticker 失败: {e}")
        return None

    def _safe_df(attr: str) -> Optional[pd.DataFrame]:
        try:
            df = getattr(ticker, attr, None)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except Exception:
            pass
        try:
            q = getattr(ticker, f"quarterly_{attr}", None)
            if isinstance(q, pd.DataFrame) and not q.empty:
                return q
        except Exception:
            pass
        return None

    inc = _safe_df("income_stmt")
    bs = _safe_df("balance_sheet")
    if inc is None and bs is None:
        return None

    out: Dict[str, Any] = {}

    # ======== 利润表相关 ========
    if inc is not None:
        rev_cols = sorted(inc.columns.tolist(), reverse=True)
        r0, c0 = _first(inc, ["Total Revenue", "Revenue", "Total Revenue (Video)", "Revenues"], rev_cols)
        gp0, _  = _first(inc, ["Gross Profit"],                          rev_cols)
        ni0, _  = _first(inc, ["Net Income", "Net Income Common Stockholders",
                                "Net Income Available To Common Shareholders", "Net Income (Including Minority Interest)"], rev_cols)
        # 同比：需要两期
        r1, _ = (None, None)
        n1, _ = (None, None)
        if len(rev_cols) >= 2:
            later_cols = rev_cols[1:]
            r1, _ = _first(inc, ["Total Revenue", "Revenue", "Revenues"], later_cols)
            n1, _ = _first(inc, ["Net Income", "Net Income Common Stockholders",
                                  "Net Income (Including Minority Interest)"], later_cols)
        if r0 and r0 != 0:
            if gp0 is not None:
                out["gross_margin"] = round(100.0 * gp0 / r0, 3)
            if ni0 is not None:
                out["net_margin"] = round(100.0 * ni0 / r0, 3)
        if r1 is not None and r1 != 0 and r0 is not None:
            out["revenue_yoy"] = round(100.0 * (r0 - r1) / abs(r1), 3)
        if n1 is not None and n1 != 0 and ni0 is not None:
            out["earnings_yoy"] = round(100.0 * (ni0 - n1) / abs(n1), 3)
        out["_yf_rev_cur"] = r0
        out["_yf_ni_cur"] = ni0
        out["_yf_rev_prev"] = r1
        out["_yf_ni_prev"] = n1

    # ======== 资产负债表 + ROE/ROA/负债率/流动比 ========
    if bs is not None:
        bs_cols = sorted(bs.columns.tolist(), reverse=True)
        ta0, _   = _first(bs, ["Total Assets"],                                                bs_cols)
        tl0, _   = _first(bs, ["Total Liabilities Net Minority Interest", "Total Liabilities",
                                "Total Liab"],                                                   bs_cols)
        eq0, _   = _first(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest",
                                "Common Stock Equity", "Stockholders' Equity",
                                "Total Stockholders' Equity"],                                    bs_cols)
        ca0, _   = _first(bs, ["Current Assets", "Total Current Assets"],                         bs_cols)
        cl0, _   = _first(bs, ["Current Liabilities", "Total Current Liabilities"],                bs_cols)
        td0, _   = _first(bs, ["Total Debt", "Net Debt"],                                          bs_cols)

        if ta0 and ta0 != 0:
            # 资产负债率：优先总负债/总资产，若缺则用总债务/总资产
            if tl0 is not None:
                out["debt_ratio"] = round(100.0 * tl0 / ta0, 3)
            elif td0 is not None:
                out["debt_ratio"] = round(100.0 * td0 / ta0, 3)
            # ROA：用最近一期 NI / TA
            ni_cur = out.get("_yf_ni_cur")
            if ni_cur is not None:
                out["roa"] = round(100.0 * ni_cur / ta0, 3)
        # ROE：NI / 权益
        if eq0 and eq0 != 0:
            ni_cur = out.get("_yf_ni_cur")
            if ni_cur is not None:
                out["roe"] = round(100.0 * ni_cur / eq0, 3)
        # 流动比率
        if ca0 is not None and cl0 is not None and cl0 != 0:
            out["current_ratio"] = round(float(ca0) / float(cl0), 3)

    # 清理内部临时字段
    for k in list(out.keys()):
        if str(k).startswith("_yf_"):
            out.pop(k, None)
    return out if out else None


# ============ Yahoo Finance info 拉取 ============
def _fetch_via_yf_info(yf_code: str) -> Optional[Dict[str, Any]]:
    _ensure_backend()
    if not _YF_OK or yf is None:
        return None
    mkt = _market_of(yf_code)
    if mkt in ("US", "KR"):
        time.sleep(0.5)
    try:
        ticker = yf.Ticker(yf_code)
        info = ticker.info or {}
    except Exception as e:
        logger.info(f"[YF info] {yf_code} 拉取失败: {e}")
        return None
    if not isinstance(info, dict) or len(info) == 0:
        return None

    out: Dict[str, Any] = {}
    for k in _YF_INFO_KEYS.keys():
        v = _from_info(info, k)
        if v is not None:
            out[k] = v
    return out if out else None


# ============ 对外：拉取财报原始指标 ============
def fetch_financial(yf_code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    拉取一只股票的财报关键指标，返回字段字典：
      pe_ttm, pb, ps_ttm, div_yield,
      roe, roa, gross_margin, net_margin,
      revenue_yoy, earnings_yoy, debt_ratio, current_ratio,
      market_cap
    所有百分比类字段单位是 **%**（例如 roe=15.3 表示 15.3%）
    """
    if not force_refresh:
        cached = _read_cache(yf_code)
        if cached is not None:
            return cached

    mkt = _market_of(yf_code)
    ts_res = None
    yf_info_res = None
    yf_stmt_res = None

    if mkt in ("CN", "HK"):
        ts_res = _fetch_via_tushare(yf_code)
    yf_info_res = _fetch_via_yf_info(yf_code)
    # --- 兜底第三层：Yahoo 三表自算（当 info 限流/缺字段时仍能拿到真实数据）
    try:
        yf_stmt_res = _fetch_via_yf_statements(yf_code)
    except Exception as e:
        logger.info(f"[YF statements] {yf_code} 兜底失败: {e}")
        yf_stmt_res = None

    merged: Dict[str, Any] = {}
    # 优先级：Tushare → YF info → YF statements 兜底；market_cap 取最大
    for d in [ts_res or {}, yf_info_res or {}, yf_stmt_res or {}]:
        for k, v in d.items():
            if v is None:
                continue
            if k == "market_cap":
                if (merged.get(k) or 0) < v:
                    merged[k] = v
                continue
            if merged.get(k) is None:
                merged[k] = v

    if not merged:
        logger.info(f"[财报] {yf_code} 未拉到任何数据，返回空字典")
    merged["_fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    merged["_market"] = mkt
    _write_cache(yf_code, merged)
    return merged


# =============================================================================
# 财报分项打分 + 综合分
# 四个维度：估值 30% / 盈利 30% / 成长 20% / 财务健康 20%
# =============================================================================

def _clip_score(s: float) -> float:
    return round(max(0.0, min(100.0, float(s))), 1)


def _score_valuation(fin: Dict[str, Any]) -> Dict[str, Any]:
    """估值评分（满分100，权重30%）：PE、PB、PS、股息率"""
    pe = fin.get("pe_ttm")
    pb = fin.get("pb")
    ps = fin.get("ps_ttm")
    div = fin.get("div_yield")
    items: Dict[str, float] = {}
    details: Dict[str, str] = {}

    # PE (0-40 分)
    pe_score = 50.0
    if pe is None or not np.isfinite(pe) or pe <= 0:
        pe_score = 40.0
        details["pe"] = f"PE=未披露/亏损 → 40分"
    elif pe < 10:
        pe_score = 100.0
        details["pe"] = f"PE={pe:.1f}（极度低估）→ 100分"
    elif pe < 20:
        pe_score = 85.0 + (20 - pe) / 10 * 15
        details["pe"] = f"PE={pe:.1f}（低估）→ {pe_score:.0f}分"
    elif pe < 35:
        pe_score = 50.0 + (35 - pe) / 15 * 35
        details["pe"] = f"PE={pe:.1f}（合理）→ {pe_score:.0f}分"
    elif pe < 60:
        pe_score = 25.0 + (60 - pe) / 25 * 25
        details["pe"] = f"PE={pe:.1f}（偏高）→ {pe_score:.0f}分"
    else:
        pe_score = max(0.0, 25.0 - (pe - 60) * 0.5)
        details["pe"] = f"PE={pe:.1f}（高估/泡沫）→ {pe_score:.0f}分"
    items["pe"] = round(pe_score, 1)

    # PB (0-30 分)
    pb_score = 50.0
    if pb is None or not np.isfinite(pb):
        pb_score = 50.0
        details["pb"] = "PB=未披露 → 50分"
    elif pb < 0.8:
        pb_score = 100.0
        details["pb"] = f"PB={pb:.2f}（破净，安全边际高）→ 100分"
    elif pb < 1.5:
        pb_score = 80.0 + (1.5 - pb) / 0.7 * 20
        details["pb"] = f"PB={pb:.2f}（低估值）→ {pb_score:.0f}分"
    elif pb < 3.0:
        pb_score = 50.0 + (3.0 - pb) / 1.5 * 30
        details["pb"] = f"PB={pb:.2f}（合理）→ {pb_score:.0f}分"
    elif pb < 6.0:
        pb_score = 25.0 + (6.0 - pb) / 3.0 * 25
        details["pb"] = f"PB={pb:.2f}（偏高）→ {pb_score:.0f}分"
    else:
        pb_score = max(0.0, 25.0 - (pb - 6.0) * 3)
        details["pb"] = f"PB={pb:.2f}（高估）→ {pb_score:.0f}分"
    items["pb"] = round(pb_score, 1)

    # PS (0-15 分)
    ps_score = 50.0
    if ps is None or not np.isfinite(ps):
        ps_score = 50.0
        details["ps"] = "PS=未披露 → 50分"
    elif ps < 1:
        ps_score = 100.0
        details["ps"] = f"PS={ps:.2f}（极低）→ 100分"
    elif ps < 3:
        ps_score = 75.0 + (3 - ps) / 2 * 25
        details["ps"] = f"PS={ps:.2f}（偏低）→ {ps_score:.0f}分"
    elif ps < 8:
        ps_score = 45.0 + (8 - ps) / 5 * 30
        details["ps"] = f"PS={ps:.2f}（合理）→ {ps_score:.0f}分"
    elif ps < 15:
        ps_score = 20.0 + (15 - ps) / 7 * 25
        details["ps"] = f"PS={ps:.2f}（偏高）→ {ps_score:.0f}分"
    else:
        ps_score = max(0.0, 20.0 - (ps - 15) * 1.5)
        details["ps"] = f"PS={ps:.2f}（高估）→ {ps_score:.0f}分"
    items["ps"] = round(ps_score, 1)

    # 股息率 (0-15 分)
    div_score = 50.0
    if div is None or not np.isfinite(div):
        div_score = 50.0
        details["div"] = "股息率=未披露 → 50分"
    elif div >= 5:
        div_score = 100.0
        details["div"] = f"股息率={div:.2f}%（高分红）→ 100分"
    elif div >= 3:
        div_score = 75.0 + (div - 3) / 2 * 25
        details["div"] = f"股息率={div:.2f}%（良好）→ {div_score:.0f}分"
    elif div >= 1:
        div_score = 50.0 + (div - 1) / 2 * 25
        details["div"] = f"股息率={div:.2f}%（一般）→ {div_score:.0f}分"
    elif div > 0:
        div_score = 35.0 + div * 15
        details["div"] = f"股息率={div:.2f}%（较低）→ {div_score:.0f}分"
    else:
        div_score = 25.0
        details["div"] = "股息率=0%（无分红）→ 25分"
    items["div"] = round(div_score, 1)

    weighted = (pe_score * 0.40 + pb_score * 0.30 + ps_score * 0.15 + div_score * 0.15)
    return {
        "sub_items": items,
        "details": details,
        "score": _clip_score(weighted),
    }


def _score_profitability(fin: Dict[str, Any]) -> Dict[str, Any]:
    """盈利能力评分（满分100，权重30%）：ROE、ROA、毛利率、净利率"""
    roe = fin.get("roe")
    roa = fin.get("roa")
    gm = fin.get("gross_margin")
    nm = fin.get("net_margin")
    items: Dict[str, float] = {}
    details: Dict[str, str] = {}

    def _pct_score(val: Optional[float], good: float, ok: float, bad: float, name: str) -> float:
        if val is None or not np.isfinite(val):
            details[name] = f"{name.upper()}=未披露 → 50分"
            return 50.0
        if val >= good:
            s = min(100.0, 80.0 + (val - good) * 1.5)
        elif val >= ok:
            s = 60.0 + (val - ok) / (good - ok) * 20
        elif val >= bad:
            s = 30.0 + (val - bad) / (ok - bad) * 30
        else:
            s = max(0.0, 30.0 + val * 1.0)
        details[name] = f"{name.upper()}={val:.2f}% → {s:.0f}分"
        return s

    items["roe"] = round(_pct_score(roe, 20.0, 12.0, 5.0, "roe"), 1)
    items["roa"] = round(_pct_score(roa, 12.0, 6.0, 2.0, "roa"), 1)
    items["gross_margin"] = round(_pct_score(gm, 50.0, 30.0, 15.0, "gross_margin"), 1)
    items["net_margin"] = round(_pct_score(nm, 25.0, 12.0, 3.0, "net_margin"), 1)

    weighted = (items["roe"] * 0.40 + items["roa"] * 0.20
                + items["gross_margin"] * 0.20 + items["net_margin"] * 0.20)
    return {
        "sub_items": items,
        "details": details,
        "score": _clip_score(weighted),
    }


def _score_growth(fin: Dict[str, Any]) -> Dict[str, Any]:
    """成长能力评分（满分100，权重20%）：营收同比、净利润同比"""
    rev = fin.get("revenue_yoy")
    earn = fin.get("earnings_yoy")
    items: Dict[str, float] = {}
    details: Dict[str, str] = {}

    for name, val in (("revenue", rev), ("earnings", earn)):
        cn = "营收同比" if name == "revenue" else "净利润同比"
        if val is None or not np.isfinite(val):
            items[name] = 50.0
            details[name] = f"{cn}=未披露 → 50分"
            continue
        if val >= 50:
            s = 100.0
        elif val >= 30:
            s = 80.0 + (val - 30) / 20 * 20
        elif val >= 15:
            s = 60.0 + (val - 15) / 15 * 20
        elif val >= 5:
            s = 40.0 + (val - 5) / 10 * 20
        elif val >= 0:
            s = 25.0 + val / 5 * 15
        elif val >= -10:
            s = 10.0 + (val + 10) / 10 * 15
        else:
            s = max(0.0, 10.0 + (val + 10) * 0.5)
        items[name] = round(s, 1)
        details[name] = f"{cn}={val:.2f}% → {s:.0f}分"

    weighted = items["revenue"] * 0.45 + items["earnings"] * 0.55
    return {
        "sub_items": items,
        "details": details,
        "score": _clip_score(weighted),
    }


def _score_health(fin: Dict[str, Any]) -> Dict[str, Any]:
    """财务健康评分（满分100，权重20%）：资产负债率、流动比率"""
    debt = fin.get("debt_ratio")
    curr = fin.get("current_ratio")
    items: Dict[str, float] = {}
    details: Dict[str, str] = {}

    # 资产负债率（越低越安全，但过低也说明经营保守）
    if debt is None or not np.isfinite(debt):
        items["debt"] = 50.0
        details["debt"] = "资产负债率=未披露 → 50分"
    else:
        if 30 <= debt <= 50:
            s = 100.0
        elif 20 <= debt < 30:
            s = 85.0 + (30 - debt) / 10 * 15
        elif 50 < debt <= 65:
            s = 70.0 + (65 - debt) / 15 * 30
        elif 10 <= debt < 20:
            s = 70.0 + (20 - debt) / 10 * 15
        elif 65 < debt <= 80:
            s = 30.0 + (80 - debt) / 15 * 40
        elif debt < 10:
            s = 55.0 + debt * 1.5
        else:
            s = max(0.0, 30.0 - (debt - 80) * 1.5)
        items["debt"] = round(s, 1)
        details["debt"] = f"资产负债率={debt:.2f}% → {s:.0f}分"

    # 流动比率（>2 安全，<1 危险）
    if curr is None or not np.isfinite(curr):
        items["current"] = 50.0
        details["current"] = "流动比率=未披露 → 50分"
    else:
        if 2.0 <= curr <= 3.5:
            s = 100.0
        elif 1.5 <= curr < 2.0:
            s = 75.0 + (curr - 1.5) / 0.5 * 25
        elif 3.5 < curr <= 5.0:
            s = 80.0 + (5.0 - curr) / 1.5 * 20
        elif 1.0 <= curr < 1.5:
            s = 45.0 + (curr - 1.0) / 0.5 * 30
        elif 0.5 <= curr < 1.0:
            s = 20.0 + (curr - 0.5) / 0.5 * 25
        elif curr > 5:
            s = 60.0 + max(0.0, (10 - curr) * 4)
        else:
            s = max(0.0, 20.0 + curr * 20)
        items["current"] = round(s, 1)
        details["current"] = f"流动比率={curr:.2f} → {s:.0f}分"

    weighted = items["debt"] * 0.60 + items["current"] * 0.40
    return {
        "sub_items": items,
        "details": details,
        "score": _clip_score(weighted),
    }


FIN_WEIGHTS = {
    "valuation": 0.30,
    "profitability": 0.30,
    "growth": 0.20,
    "health": 0.20,
}


def score_financial(yf_code: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    财报总评分入口。返回：
    {
      "raw": 原始指标字典,
      "valuation": {sub_items, details, score},
      "profitability": {...},
      "growth": {...},
      "health": {...},
      "total_score": 0~100（综合财报分）
    }
    """
    raw = fetch_financial(yf_code, force_refresh=force_refresh)
    val = _score_valuation(raw)
    prof = _score_profitability(raw)
    growth = _score_growth(raw)
    health = _score_health(raw)

    total = (val["score"] * FIN_WEIGHTS["valuation"]
             + prof["score"] * FIN_WEIGHTS["profitability"]
             + growth["score"] * FIN_WEIGHTS["growth"]
             + health["score"] * FIN_WEIGHTS["health"])

    return {
        "raw": raw,
        "valuation": val,
        "profitability": prof,
        "growth": growth,
        "health": health,
        "total_score": _clip_score(total),
    }

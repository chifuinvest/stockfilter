# -*- coding: utf-8 -*-
"""
单股票综合分析工具
整合：财报分析（financial_analyzer） + 技术面评分（scoring_engine）
最终输出：六级评级（强烈买入/买入/持有/观望/卖出/强烈卖出）

免责声明：本系统输出仅供研究和学习使用，不构成任何投资建议。
          市场有风险，投资需谨慎，实盘盈亏自负，版权方不承担法律责任。
版权所有 (c) 2025 Bart · 联系方式：yanying76@gmail.com
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("stock_analyzer")

_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

import financial_analyzer as fa
import scoring_engine as se
import data_fetcher_v2 as fetcher


# ============ 市场 / 代码智能识别 ============

MARKET_LABEL: Dict[str, str] = {
    "US": "🇺🇸 美股",
    "CN": "🇨🇳 A股",
    "HK": "🇭🇰 港股",
    "KR": "🇰🇷 韩股",
}


def _market_of(yf_code: str) -> str:
    c = yf_code.upper()
    if c.endswith(".SS") or c.endswith(".SZ"):
        return "CN"
    if c.endswith(".HK"):
        return "HK"
    if c.endswith(".KS") or c.endswith(".KQ"):
        return "KR"
    return "US"


def normalize_code(raw: str, market_hint: Optional[str] = None) -> Tuple[str, str]:
    """
    智能识别并规范化用户输入的股票代码。
    输入：
      raw: 任意格式代码（688256 / 600519.SH / AAPL / 00700 / 腾讯）
      market_hint: 可选市场（CN/HK/US/KR），用于纯数字代码的二义性
    返回：(yf_code, market)
    """
    if not raw:
        raise ValueError("股票代码不能为空")
    code = raw.strip().upper()

    # 情况 1：已经带后缀 → 直接用
    for suf in (".SS", ".SZ", ".SH", ".HK", ".KS", ".KQ"):
        if code.endswith(suf):
            if suf == ".SH":
                code = code[:-3] + ".SS"
            return code, _market_of(code)

    # 情况 2：纯数字
    if code.isdigit():
        n = len(code)
        if n == 6:
            # A 股 / 港股 二义性
            if market_hint == "HK":
                # 港股不足 5 位补前导零
                num = int(code)
                return f"{num:05d}.HK", "HK"
            if code.startswith(("6", "9")):
                return f"{code}.SS", "CN"
            if code.startswith(("0", "2", "3")):
                return f"{code}.SZ", "CN"
            # 其余默认 A 股沪市
            return f"{code}.SS", "CN"
        if n == 5 or n == 4:
            num = int(code)
            return f"{num:05d}.HK", "HK"
        if n <= 3:
            num = int(code)
            return f"{num:05d}.HK", "HK"

    # 情况 3：字母开头 → 默认为美股
    if code[0].isalpha():
        return code, "US"

    # 兜底：原样返回
    return raw.strip(), (market_hint or _market_of(raw.strip()))


# ============ 六级评级映射 ============

def get_rating(total_score: float) -> Dict[str, Any]:
    """
    0~100 综合分 → 六级评级
    档位：
      ≥ 85  强烈买入 STRONG_BUY
      ≥ 70  买入      BUY
      ≥ 55  持有      HOLD
      ≥ 40  观望      WATCH
      ≥ 25  卖出      SELL
      < 25  强烈卖出 STRONG_SELL
    """
    if total_score >= 85:
        level, label, emoji, color = "STRONG_BUY", "强烈买入", "🟢🟢", "#14532d"
        meaning = "财报优异 + 技术面共振，多维度强烈看多，建议积极布局"
    elif total_score >= 70:
        level, label, emoji, color = "BUY", "买入", "🟢", "#16a34a"
        meaning = "财报基本面良好 + 技术面偏多，可考虑逢低建仓"
    elif total_score >= 55:
        level, label, emoji, color = "HOLD", "持有", "🔵", "#2563eb"
        meaning = "基本面中性偏好，技术面无明显卖点，已有仓位可继续持有"
    elif total_score >= 40:
        level, label, emoji, color = "WATCH", "观望", "🟡", "#ca8a04"
        meaning = "多空因素交织，方向不明朗，建议等待更明确的信号"
    elif total_score >= 25:
        level, label, emoji, color = "SELL", "卖出", "🔴", "#dc2626"
        meaning = "基本面或技术面出现明显转弱信号，可考虑减仓或离场"
    else:
        level, label, emoji, color = "STRONG_SELL", "强烈卖出", "🔴🔴", "#7f1d1d"
        meaning = "财报走弱 + 技术面全面空头，建议回避或果断清仓"
    return {
        "level": level,
        "label": label,
        "emoji": emoji,
        "color": color,
        "meaning": meaning,
    }


def get_rating_css(level: str) -> Dict[str, str]:
    """给 Streamlit UI 使用的配色"""
    return {
        "STRONG_BUY": {"bg": "#dcfce7", "fg": "#14532d", "border": "#16a34a"},
        "BUY":       {"bg": "#dcfce7", "fg": "#166534", "border": "#22c55e"},
        "HOLD":      {"bg": "#dbeafe", "fg": "#1e40af", "border": "#3b82f6"},
        "WATCH":     {"bg": "#fef9c3", "fg": "#854d0e", "border": "#eab308"},
        "SELL":      {"bg": "#fee2e2", "fg": "#991b1b", "border": "#ef4444"},
        "STRONG_SELL": {"bg": "#fecaca", "fg": "#7f1d1d", "border": "#dc2626"},
    }.get(level, {"bg": "#f3f4f6", "fg": "#1f2937", "border": "#9ca3af"})


# ============ 权重分配 ============
# 综合分 = 财报分 * FW + 技术分 * TW，可根据风格调整
DEFAULT_WEIGHTS: Dict[str, float] = {
    "financial": 0.50,  # 财报 50%
    "technical": 0.50,  # 技术面 50%
}


# ============ 核心：综合分析 ============

def analyze_stock(
    raw_code: str,
    market_hint: Optional[str] = None,
    force_refresh: bool = False,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    单股票综合分析入口。

    返回结构：
    {
      "yf_code": "AAPL" / "688256.SS" / "00700.HK",
      "market": "US" / "CN" / "HK",
      "market_label": "🇺🇸 美股",
      "price": 最新价,
      "pct_1d / pct_7d / pct_30d / pct_1y": 涨跌幅,

      "financial_score": 0~100,
      "financial": {   # 来自 financial_analyzer.score_financial()
          "raw": {...},
          "valuation": {sub_items, details, score},
          "profitability": {...},
          "growth": {...},
          "health": {...},
          "total_score": xx
      },

      "technical_score": 0~100,
      "technical": {   # 来自 scoring_engine.score_single()
          "total_score": xx,
          "score_ma" ... 各子项分,
          "signal": "BUY/HOLD/...",
          "rsi_value": ...,
          ...
      },

      "total_score": 0~100（综合分）,
      "rating": {level, label, emoji, color, meaning},
      "weights_used": {"financial": 0.5, "technical": 0.5},

      "highlights": [
          "财报亮点1", "财报风险1", "技术面亮点", "技术面风险"
      ],
      "summary": "一段自然语言结论摘要"
    }
    """
    # 1) 规范化代码
    yf_code, market = normalize_code(raw_code, market_hint=market_hint)
    market_label = MARKET_LABEL.get(market, market)
    w = weights or DEFAULT_WEIGHTS
    fw = float(w.get("financial", 0.5))
    tw = float(w.get("technical", 0.5))
    total_w = fw + tw
    if total_w <= 0:
        fw, tw = 0.5, 0.5
    else:
        fw, tw = fw / total_w, tw / total_w

    result: Dict[str, Any] = {
        "yf_code": yf_code,
        "market": market,
        "market_label": market_label,
        "weights_used": {"financial": round(fw, 3), "technical": round(tw, 3)},
    }

    # 2) 拉取价格并做技术评分
    price_df = fetcher.fetch_single_price(yf_code, force_refresh=force_refresh)
    if price_df is None or len(price_df) < 60:
        result["error"] = f"价格数据不足（{len(price_df) if price_df is not None else 0} 条，至少需60条），请检查代码或稍后重试"
        result["technical"] = None
        result["technical_score"] = 50.0
        result["price"] = None
        result["pct_1d"] = result["pct_7d"] = result["pct_30d"] = result["pct_1y"] = None
    else:
        tech = se.score_single(price_df) or {}
        result["technical"] = tech
        result["technical_score"] = float(tech.get("total_score", 50.0) or 50.0)
        result["price"] = tech.get("price")
        result["pct_1d"] = tech.get("pct_1d")
        result["pct_7d"] = tech.get("pct_7d")
        result["pct_30d"] = tech.get("pct_30d")
        result["pct_1y"] = tech.get("pct_1y")

    # 3) 财报评分
    try:
        fin = fa.score_financial(yf_code, force_refresh=force_refresh)
    except Exception as e:
        logger.warning(f"财报评分异常 {yf_code}: {e}")
        fin = {
            "raw": {},
            "valuation": {"sub_items": {}, "details": {}, "score": 50.0},
            "profitability": {"sub_items": {}, "details": {}, "score": 50.0},
            "growth": {"sub_items": {}, "details": {}, "score": 50.0},
            "health": {"sub_items": {}, "details": {}, "score": 50.0},
            "total_score": 50.0,
        }
    result["financial"] = fin
    result["financial_score"] = float(fin.get("total_score", 50.0) or 50.0)

    # 4) 综合分
    fs = result["financial_score"]
    ts = result["technical_score"]
    total = round(fs * fw + ts * tw, 2)
    result["total_score"] = total
    result["rating"] = get_rating(total)

    # 5) 生成亮点/风险 + 文字摘要
    result["highlights"] = _gen_highlights(fin, result.get("technical") or {})
    result["summary"] = _gen_summary(result)

    return result


# ============ 亮点/风险提炼 ============

def _gen_highlights(fin: Dict[str, Any], tech: Dict[str, Any]) -> List[Dict[str, str]]:
    """提炼 4~6 条亮点/风险，每条: {type: 'pro'|'con', dim: '估值'|'盈利'|'成长'|'健康'|'技术', text: '...'}"""
    out: List[Dict[str, str]] = []
    raw = fin.get("raw", {}) or {}

    # ---- 财报维度 ----
    # 估值
    val_score = float(fin.get("valuation", {}).get("score", 50) or 50)
    if val_score >= 75:
        pe = raw.get("pe_ttm")
        pb = raw.get("pb")
        pe_txt = f"PE={pe:.1f}" if pe else ""
        pb_txt = f"PB={pb:.2f}" if pb else ""
        txt = "估值具备吸引力"
        if pe_txt or pb_txt:
            txt += f"（{'/'.join(filter(None, [pe_txt, pb_txt]))}）"
        out.append({"type": "pro", "dim": "估值", "text": txt})
    elif val_score <= 35:
        out.append({"type": "con", "dim": "估值", "text": "估值偏高，安全边际不足"})

    # 盈利
    prof_score = float(fin.get("profitability", {}).get("score", 50) or 50)
    if prof_score >= 75:
        roe = raw.get("roe")
        gm = raw.get("gross_margin")
        parts = []
        if roe: parts.append(f"ROE={roe:.1f}%")
        if gm: parts.append(f"毛利率={gm:.1f}%")
        txt = "盈利能力突出" + (f"（{'/'.join(parts)}）" if parts else "")
        out.append({"type": "pro", "dim": "盈利", "text": txt})
    elif prof_score <= 35:
        out.append({"type": "con", "dim": "盈利", "text": "盈利能力偏弱，ROE/毛利率不佳"})

    # 成长
    gr_score = float(fin.get("growth", {}).get("score", 50) or 50)
    if gr_score >= 75:
        rev = raw.get("revenue_yoy")
        earn = raw.get("earnings_yoy")
        parts = []
        if rev is not None: parts.append(f"营收+{rev:.1f}%")
        if earn is not None: parts.append(f"净利+{earn:.1f}%")
        txt = "成长动能强劲" + (f"（{'/'.join(parts)}）" if parts else "")
        out.append({"type": "pro", "dim": "成长", "text": txt})
    elif gr_score <= 35:
        out.append({"type": "con", "dim": "成长", "text": "增长失速，营收或净利润同比承压"})

    # 财务健康
    hl_score = float(fin.get("health", {}).get("score", 50) or 50)
    if hl_score >= 75:
        out.append({"type": "pro", "dim": "健康", "text": "资产负债结构稳健，偿债能力良好"})
    elif hl_score <= 35:
        out.append({"type": "con", "dim": "健康", "text": "财务杠杆偏高，需关注偿债风险"})

    # ---- 技术面维度 ----
    ts_total = float(tech.get("total_score", 50) or 50)
    rsi = tech.get("rsi_value")
    signal = (tech.get("signal") or "").upper()

    if ts_total >= 70:
        parts = []
        ma_s = tech.get("score_ma")
        macd_s = tech.get("score_macd")
        if ma_s and float(ma_s) >= 25: parts.append("均线多头")
        if macd_s and float(macd_s) >= 17: parts.append("MACD向好")
        txt = "技术面偏强" + (f"（{'/'.join(parts)}）" if parts else "")
        out.append({"type": "pro", "dim": "技术", "text": txt})
    elif ts_total <= 35:
        out.append({"type": "con", "dim": "技术", "text": "技术面趋弱，空头信号明显"})

    if rsi is not None:
        if rsi >= 80:
            out.append({"type": "con", "dim": "技术", "text": f"RSI={rsi:.0f}，进入超买区，短期有回调风险"})
        elif rsi <= 20:
            out.append({"type": "pro", "dim": "技术", "text": f"RSI={rsi:.0f}，进入超卖区，或存在反弹机会"})

    if signal == "BUY":
        out.append({"type": "pro", "dim": "技术", "text": "综合技术信号为「买入」"})
    elif signal in ("REDUCE", "AVOID"):
        out.append({"type": "con", "dim": "技术", "text": "综合技术信号为「减仓/回避」"})

    return out


def _gen_summary(r: Dict[str, Any]) -> str:
    """生成一段自然语言结论（150~250 字左右）"""
    rating = r.get("rating") or {}
    label = rating.get("label", "观望")
    meaning = rating.get("meaning", "")
    total = r.get("total_score", 50)
    fs = r.get("financial_score", 50)
    ts = r.get("technical_score", 50)
    mkt = r.get("market_label", "")
    code = r.get("yf_code", "")
    price = r.get("price")
    pct_30d = r.get("pct_30d")
    pct_1y = r.get("pct_1y")

    lines = []
    header = f"【{mkt} {code}】综合评分 {total}/100，评级「{label}」。"
    if price is not None:
        header += f"当前价 {price:.4f}"
        if pct_30d is not None:
            header += f"，近1月{'+' if pct_30d >= 0 else ''}{pct_30d:.1f}%"
        if pct_1y is not None:
            header += f"，近1年{'+' if pct_1y >= 0 else ''}{pct_1y:.1f}%"
    lines.append(header + "。")

    lines.append(
        f"其中 财报基本面 {fs:.1f} 分（权重 {r['weights_used']['financial']*100:.0f}%），"
        f"技术面 {ts:.1f} 分（权重 {r['weights_used']['technical']*100:.0f}%）。"
    )

    # 亮点/风险汇总
    pros = [h["text"] for h in r.get("highlights", []) if h.get("type") == "pro"]
    cons = [h["text"] for h in r.get("highlights", []) if h.get("type") == "con"]
    if pros:
        lines.append("主要看点：" + "；".join(pros[:3]) + "。")
    if cons:
        lines.append("主要风险：" + "；".join(cons[:3]) + "。")

    lines.append(f"操作建议：{meaning}。")
    lines.append("⚠️ 免责声明：以上分析仅供研究参考，不构成任何投资建议，市场有风险，投资需谨慎。")
    return "\n".join(lines)

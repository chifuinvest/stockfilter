# -*- coding: utf-8 -*-
"""
评分引擎
- 6 个技术指标：MA / MACD / RSI / 布林带 / 成交量 / KDJ
- 加权总分 0~100
- 信号判定 + 多周期涨跌幅

免责声明：本系统输出仅供研究和学习使用，不构成任何投资建议。
          市场有风险，投资需谨慎，实盘盈亏自负，版权方不承担法律责任。
版权所有 (c) 2025 Bart · 联系方式：yanying76@gmail.com
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("scoring_engine")


# ===================== 工具函数 =====================

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=max(2, period // 2)).mean()


def _last(v: pd.Series) -> float:
    try:
        s = v.dropna()
        if len(s) == 0:
            return np.nan
        return float(s.iloc[-1])
    except Exception:
        return np.nan


def _pct_change(df: pd.DataFrame, offset: int) -> Optional[float]:
    """计算收盘价 offset 个交易日前的涨跌幅（百分比）"""
    try:
        close = df["Close"].dropna()
        if len(close) <= offset:
            return None
        cur = float(close.iloc[-1])
        prev = float(close.iloc[-(offset + 1)])
        if prev == 0 or not np.isfinite(prev):
            return None
        return round((cur - prev) / prev * 100, 2)
    except Exception:
        return None


# ===================== 指标计算 =====================

def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    输入：日线 OHLCV DataFrame（日期升序）
    输出：各指标最新值字典
    """
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)

    ma5 = _sma(close, 5)
    ma10 = _sma(close, 10)
    ma20 = _sma(close, 20)
    ma60 = _sma(close, 60)

    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    dif = ema12 - ema26
    dea = _ema(dif, 9)
    macd_hist = (dif - dea) * 2

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    bb_mid = _sma(close, 20)
    bb_std = close.rolling(window=20, min_periods=10).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    vol_ma5 = _sma(volume, 5)
    vol_ratio = volume / vol_ma5.replace(0, np.nan)

    low9 = low.rolling(window=9, min_periods=5).min()
    high9 = high.rolling(window=9, min_periods=5).max()
    rsv = (close - low9) / (high9 - low9).replace(0, np.nan) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d

    return {
        "ma5": _last(ma5), "ma10": _last(ma10), "ma20": _last(ma20), "ma60": _last(ma60),
        "price": _last(close),
        "dif": _last(dif), "dea": _last(dea), "macd_hist": _last(macd_hist),
        "macd_hist_prev": float(macd_hist.dropna().iloc[-2]) if len(macd_hist.dropna()) >= 2 else np.nan,
        "dif_prev": float(dif.dropna().iloc[-2]) if len(dif.dropna()) >= 2 else np.nan,
        "dea_prev": float(dea.dropna().iloc[-2]) if len(dea.dropna()) >= 2 else np.nan,
        "rsi": _last(rsi),
        "bb_upper": _last(bb_upper), "bb_mid": _last(bb_mid), "bb_lower": _last(bb_lower),
        "vol_ma5": _last(vol_ma5), "vol_ratio": _last(vol_ratio),
        "volume_last": _last(volume),
        "k": _last(k), "d": _last(d), "j": _last(j),
        "j_prev": float(j.dropna().iloc[-2]) if len(j.dropna()) >= 2 else np.nan,
        "k_prev": float(k.dropna().iloc[-2]) if len(k.dropna()) >= 2 else np.nan,
        "d_prev": float(d.dropna().iloc[-2]) if len(d.dropna()) >= 2 else np.nan,
        "close_prev": float(close.dropna().iloc[-2]) if len(close.dropna()) >= 2 else np.nan,
    }


# ===================== 子项打分（0~100 → 按权重缩分） =====================

def _score_ma(ind: Dict[str, Any]) -> float:
    """均线趋势（满分30，子打分0~100）"""
    ma5, ma10, ma20, ma60, price = (ind.get("ma5"), ind.get("ma10"),
                                    ind.get("ma20"), ind.get("ma60"), ind.get("price"))
    for v in [ma5, ma10, ma20, ma60, price]:
        if v is None or not np.isfinite(v):
            return 50.0

    score = 50.0
    if ma5 > ma10 > ma20 > ma60:
        score = 100.0
    elif ma5 > ma10 > ma20:
        score = 88.0
    elif ma5 > ma10 and price > ma20:
        score = 75.0
    elif price > ma60 and ma10 > ma20:
        score = 65.0
    elif price > ma20:
        score = 58.0
    elif price > ma60:
        score = 42.0
    elif price < ma60 and ma5 < ma10 < ma20:
        score = 15.0
    elif price < ma60:
        score = 25.0
    else:
        score = 45.0
    return score


def _score_macd(ind: Dict[str, Any]) -> float:
    """MACD（满分20，子打分0~100）"""
    dif, dea = ind.get("dif"), ind.get("dea")
    h, h_prev = ind.get("macd_hist"), ind.get("macd_hist_prev")
    for v in [dif, dea, h]:
        if v is None or not np.isfinite(v):
            return 50.0

    score = 50.0
    if dif > dea and (h_prev is None or not np.isfinite(h_prev) or h > h_prev):
        score = 100.0
    elif dif > dea:
        score = 70.0
    elif (dif is not None and dea is not None and dif < dea
          and h_prev is not None and np.isfinite(h_prev) and h < h_prev):
        score = 10.0
    elif dif < dea:
        score = 35.0
    else:
        score = 50.0
    return score


def _score_rsi(ind: Dict[str, Any]) -> float:
    """RSI（满分15，子打分0~100）"""
    rsi = ind.get("rsi")
    if rsi is None or not np.isfinite(rsi):
        return 50.0

    if 30 <= rsi <= 50:
        return 100.0
    elif 50 < rsi <= 65:
        return 78.0
    elif 65 < rsi <= 75:
        return 60.0
    elif 20 <= rsi < 30:
        return 65.0
    elif 75 < rsi <= 80:
        return 35.0
    elif rsi > 80:
        return 15.0
    elif rsi < 20:
        return 30.0
    return 50.0


def _score_boll(ind: Dict[str, Any]) -> float:
    """布林带位置（满分10，子打分0~100）"""
    up, mid, low, price = (ind.get("bb_upper"), ind.get("bb_mid"),
                           ind.get("bb_lower"), ind.get("price"))
    for v in [up, mid, low, price]:
        if v is None or not np.isfinite(v):
            return 50.0
    if up == low:
        return 50.0

    if low <= price <= mid:
        pct = (price - low) / (mid - low) if mid != low else 0.5
        return round(85 + 15 * (1 - pct), 1)
    elif mid < price <= up:
        pct = (price - mid) / (up - mid)
        return round(70 - 30 * pct, 1)
    elif price < low:
        return 40.0
    else:
        return 15.0


def _score_volume(ind: Dict[str, Any]) -> float:
    """量能配合（满分15，子打分0~100）"""
    vr = ind.get("vol_ratio")
    price = ind.get("price")
    prev = ind.get("close_prev")
    if vr is None or not np.isfinite(vr):
        return 50.0

    up_day = (price is not None and prev is not None
              and np.isfinite(price) and np.isfinite(prev) and price > prev)

    if up_day:
        if 1.2 <= vr <= 2.0:
            return 100.0
        elif 1.0 <= vr < 1.2:
            return 80.0
        elif 2.0 < vr <= 3.0:
            return 65.0
        elif 0.7 <= vr < 1.0:
            return 60.0
        elif vr > 3.0:
            return 30.0
        else:
            return 45.0
    else:
        if vr <= 0.7:
            return 85.0
        elif 0.7 < vr <= 1.0:
            return 70.0
        elif 1.0 < vr <= 1.5:
            return 50.0
        elif 1.5 < vr <= 2.5:
            return 25.0
        else:
            return 10.0


def _score_kdj(ind: Dict[str, Any]) -> float:
    """KDJ（满分10，子打分0~100）"""
    j = ind.get("j")
    j_prev = ind.get("j_prev")
    k = ind.get("k")
    d = ind.get("d")
    k_prev = ind.get("k_prev")
    d_prev = ind.get("d_prev")
    if j is None or not np.isfinite(j):
        return 50.0

    turning_up = (j_prev is not None and np.isfinite(j_prev) and j > j_prev)
    turning_down = (j_prev is not None and np.isfinite(j_prev) and j < j_prev)
    kdj_death = False
    if (k is not None and d is not None and k_prev is not None and d_prev is not None
            and np.isfinite(k) and np.isfinite(d) and np.isfinite(k_prev) and np.isfinite(d_prev)):
        kdj_death = (k_prev > d_prev) and (k < d)

    if j < 20 and turning_up:
        return 100.0
    elif 20 <= j <= 80:
        if turning_up:
            return 78.0
        elif turning_down:
            return 55.0
        else:
            return 68.0
    elif j > 80 and (turning_down or kdj_death):
        return 15.0
    elif j > 80:
        return 45.0
    elif j < 20:
        return 50.0
    return 50.0


# ===================== 信号判定 =====================

WEIGHTS = {
    "ma": 30.0,
    "macd": 20.0,
    "rsi": 15.0,
    "boll": 10.0,
    "volume": 15.0,
    "kdj": 10.0,
}


def signal_of(total: float) -> Dict[str, str]:
    if total >= 80:
        return {"level": "BUY", "label": "🟢 买入", "meaning": "多指标共振，趋势明确",
                "badge": "bg-success text-white"}
    elif total >= 65:
        return {"level": "HOLD", "label": "🟡 持有", "meaning": "趋势偏多，但不建议追高",
                "badge": "bg-warning text-dark"}
    elif total >= 45:
        return {"level": "WATCH", "label": "⚠️ 观望", "meaning": "中性偏弱，等待确认",
                "badge": "bg-secondary text-white"}
    elif total >= 30:
        return {"level": "REDUCE", "label": "🔴 减仓", "meaning": "多个维度转弱",
                "badge": "bg-danger text-white"}
    else:
        return {"level": "AVOID", "label": "⛔ 回避", "meaning": "全面空头，不宜介入",
                "badge": "bg-dark text-white"}


# ===================== 对外入口 =====================

def score_single(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    对单只股票打分。
    输入：OHLCV DataFrame
    输出：包含总分、各子项分、信号、涨跌幅的字典
    """
    try:
        if df is None or len(df) < 60:
            return None
        ind = compute_indicators(df)

        sub_ma = _score_ma(ind)
        sub_macd = _score_macd(ind)
        sub_rsi = _score_rsi(ind)
        sub_boll = _score_boll(ind)
        sub_vol = _score_volume(ind)
        sub_kdj = _score_kdj(ind)

        s_ma = round(sub_ma * WEIGHTS["ma"] / 100, 2)
        s_macd = round(sub_macd * WEIGHTS["macd"] / 100, 2)
        s_rsi = round(sub_rsi * WEIGHTS["rsi"] / 100, 2)
        s_boll = round(sub_boll * WEIGHTS["boll"] / 100, 2)
        s_vol = round(sub_vol * WEIGHTS["volume"] / 100, 2)
        s_kdj = round(sub_kdj * WEIGHTS["kdj"] / 100, 2)
        total = round(s_ma + s_macd + s_rsi + s_boll + s_vol + s_kdj, 2)

        sig = signal_of(total)

        pct_1d = _pct_change(df, 1)
        pct_7d = _pct_change(df, 5)
        pct_30d = _pct_change(df, 21)
        pct_1y = _pct_change(df, 252)

        return {
            "total_score": total,
            "score_ma": s_ma, "score_macd": s_macd, "score_rsi": s_rsi,
            "score_boll": s_boll, "score_volume": s_vol, "score_kdj": s_kdj,
            "ma_score": s_ma, "macd_score": s_macd, "rsi_score": s_rsi,
            "boll_score": s_boll, "vol_score": s_vol, "kdj_score": s_kdj,
            "sub_ma": round(sub_ma, 1), "sub_macd": round(sub_macd, 1),
            "sub_rsi": round(sub_rsi, 1), "sub_boll": round(sub_boll, 1),
            "sub_volume": round(sub_vol, 1), "sub_kdj": round(sub_kdj, 1),
            **sig,
            "signal": sig.get("level", "WATCH"),
            "price": round(ind["price"], 4) if np.isfinite(ind["price"]) else None,
            "rsi_value": round(ind["rsi"], 2) if np.isfinite(ind["rsi"]) else None,
            "dif_value": round(ind["dif"], 4) if np.isfinite(ind["dif"]) else None,
            "dea_value": round(ind["dea"], 4) if np.isfinite(ind["dea"]) else None,
            "macd_hist_value": round(ind["macd_hist"], 4) if np.isfinite(ind["macd_hist"]) else None,
            "j_value": round(ind["j"], 2) if np.isfinite(ind["j"]) else None,
            "k_value": round(ind["k"], 2) if np.isfinite(ind["k"]) else None,
            "d_value": round(ind["d"], 2) if np.isfinite(ind["d"]) else None,
            "vol_ratio_value": round(ind["vol_ratio"], 2) if np.isfinite(ind["vol_ratio"]) else None,
            "ma5": round(ind["ma5"], 4) if np.isfinite(ind["ma5"]) else None,
            "ma10": round(ind["ma10"], 4) if np.isfinite(ind["ma10"]) else None,
            "ma20": round(ind["ma20"], 4) if np.isfinite(ind["ma20"]) else None,
            "ma60": round(ind["ma60"], 4) if np.isfinite(ind["ma60"]) else None,
            "bb_upper": round(ind["bb_upper"], 4) if np.isfinite(ind["bb_upper"]) else None,
            "bb_mid": round(ind["bb_mid"], 4) if np.isfinite(ind["bb_mid"]) else None,
            "bb_lower": round(ind["bb_lower"], 4) if np.isfinite(ind["bb_lower"]) else None,
            "pct_1d": pct_1d, "pct_7d": pct_7d,
            "pct_30d": pct_30d, "pct_1y": pct_1y,
            "pct_change": pct_1d if pct_1d is not None else (pct_7d if pct_7d is not None else 0),
        }
    except Exception as e:
        logger.exception(f"评分异常: {e}")
        return None

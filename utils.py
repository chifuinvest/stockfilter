import os
import pickle
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


def save_cache(data, file_path, duration=3600):
    cache_data = {
        'timestamp': time.time(),
        'duration': duration,
        'data': data
    }
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        pickle.dump(cache_data, f)


def load_cache(file_path):
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, 'rb') as f:
            cache_data = pickle.load(f)
        if time.time() - cache_data['timestamp'] < cache_data['duration']:
            return cache_data['data']
        return None
    except Exception:
        return None


def get_trade_date(days_ago=0):
    now = datetime.now() - timedelta(days=days_ago)
    return now.strftime('%Y%m%d')


def safe_float(value, default=None):
    try:
        if pd.isna(value) or value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=None):
    try:
        if pd.isna(value) or value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def calc_ma(close_prices, period):
    if len(close_prices) < period:
        return None
    return round(np.mean(close_prices[-period:]), 2)


def calc_macd(close_prices, fast=12, slow=26, signal=9):
    if len(close_prices) < slow + signal:
        return None, None, None
    closes = pd.Series(close_prices)
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_bar = 2 * (dif - dea)
    return (
        round(float(dif.iloc[-1]), 4),
        round(float(dea.iloc[-1]), 4),
        round(float(macd_bar.iloc[-1]), 4)
    )


def calc_rsi(close_prices, period=14):
    if len(close_prices) < period + 1:
        return None
    closes = pd.Series(close_prices)
    delta = closes.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    if pd.isna(val):
        return None
    return round(float(val), 2)


def calc_kdj(high_prices, low_prices, close_prices, n=9, m1=3, m2=3):
    if len(close_prices) < n:
        return None, None, None
    high_s = pd.Series(high_prices)
    low_s = pd.Series(low_prices)
    close_s = pd.Series(close_prices)
    lowest_low = low_s.rolling(window=n, min_periods=n).min()
    highest_high = high_s.rolling(window=n, min_periods=n).max()
    rsv = (close_s - lowest_low) / (highest_high - lowest_low) * 100
    rsv = rsv.fillna(50)
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    k_val = k.iloc[-1]
    d_val = d.iloc[-1]
    j_val = j.iloc[-1]
    if pd.isna(k_val) or pd.isna(d_val) or pd.isna(j_val):
        return None, None, None
    return (
        round(float(k_val), 2),
        round(float(d_val), 2),
        round(float(j_val), 2)
    )

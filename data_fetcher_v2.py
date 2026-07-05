# -*- coding: utf-8 -*-
"""
数据拉取模块 — Tushare (A/H 首选) + Yahoo Finance (美/韩 + 兜底)
- 拉取最近2年日K线
- 3次网络重试，间隔 2/4/8 秒
- 缓存到 ./data_cache/ 目录，优先读缓存
- Tushare token 读取顺序: 环境变量 TUSHARE_TOKEN > ~/.tushare/token.txt
"""
import os
import sys
import time
import pickle
import socket
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# =============================================================================
# 【前置补丁】：DETACHED 进程下 HOME/USERPROFILE/临时目录可能不对
# 如果 main.py 已做过修复，这里会是幂等的 no-op；没做的话这里兜底。
# =============================================================================
_BASE_DIR_GUARD = Path(__file__).resolve().parent
_TEMP_DIR_GUARD = _BASE_DIR_GUARD / "data_cache" / "yfinance"
_TEMP_DIR_GUARD.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(_TEMP_DIR_GUARD)
for _ek in ("TMP", "TEMP", "TMPDIR", "SQLITE_TMPDIR"):
    try:
        os.environ[_ek] = str(_TEMP_DIR_GUARD)
    except Exception:
        pass
# 修复 HOME/USERPROFILE（兜底尝试）
for _ek in ("USERPROFILE", "HOME"):
    _ev = os.environ.get(_ek) or ""
    if not _ev or "system32" in _ev.lower() or "systemprofile" in _ev.lower():
        _guess = Path("C:/Users/Bart")
        if _guess.exists():
            os.environ[_ek] = str(_guess)
# Tushare token 兜底
if not os.environ.get("TUSHARE_TOKEN"):
    for _tp in [Path("C:/Users/Bart/.tushare/token.txt"),
                Path(os.environ.get("USERPROFILE", "")) / ".tushare" / "token.txt"
                if os.environ.get("USERPROFILE") else None]:
        if _tp and _tp.exists():
            try:
                _tk = _tp.read_text(encoding="utf-8").strip()
                if _tk:
                    os.environ["TUSHARE_TOKEN"] = _tk
                    break
            except Exception:
                continue
# yfinance cache 环境变量
for _ek in ("YF_CACHE_DIR", "YF_CACHE_PATH", "TZ_CACHE_PATH"):
    os.environ[_ek] = str(_TEMP_DIR_GUARD)

import numpy as np
import pandas as pd

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("data_fetcher")

try:
    socket.setdefaulttimeout(25)
except Exception:
    pass

_BASE_DIR = Path(__file__).resolve().parent
_CACHE_DIR = _BASE_DIR / "data_cache"
_PRICE_CACHE = _CACHE_DIR / "prices_v2"
_PRICE_CACHE.mkdir(parents=True, exist_ok=True)
_CACHE_TTL_HOURS = 6

# ============ Yahoo Finance ============
_YF_OK = False
try:
    # import 前再确保一次 tempdir
    tempfile.tempdir = str(_TEMP_DIR_GUARD)
    import yfinance as yf
    _YF_OK = True
    # 再尝试应用一次缓存路径 + 关缓存（避免 SQLite 写 system32）
    try:
        for fn in ("set_tz_cache_location", "_set_tz_cache_dir"):
            if hasattr(yf, fn):
                try:
                    getattr(yf, fn)(str(_TEMP_DIR_GUARD))
                except Exception:
                    pass
        if hasattr(yf, "enable_caching"):
            try:
                yf.enable_caching(False)
            except Exception:
                pass
    except Exception:
        pass
except Exception as e:
    logger.warning(f"yfinance 不可用: {e}")
    yf = None

_YF_BACKOFF_UNTIL = 0.0
_YF_CONSEC_EMPTY = [0]
_YF_BACKOFF_LEVEL = [0]
_YF_BACKOFF_SECONDS = [300, 600, 1200, 2400]
import random as _yf_rnd

# ============ Tushare (A/H 股首选) ============
_TS_OK = False
_ts_pro = None
TUSHARE_TOKEN = ""

def _init_tushare():
    global _TS_OK, _ts_pro, TUSHARE_TOKEN
    if _TS_OK:
        return True
    TUSHARE_TOKEN = (os.environ.get("TUSHARE_TOKEN") or "").strip()
    if not TUSHARE_TOKEN:
        home_token = Path.home() / ".tushare" / "token.txt"
        # 兜底：即便 Path.home() 被 DETACHED 进程改成了 system32，也硬尝试当前登录用户名 + 运行时已由 main.py 写入的 TUSHARE_TOKEN env
        candidate_tokens = [
            home_token,
            Path("C:/Users/Bart/.tushare/token.txt"),
            Path(os.environ.get("USERPROFILE", "")) / ".tushare" / "token.txt" if os.environ.get("USERPROFILE") else None,
        ]
        for p in candidate_tokens:
            if p and p.exists():
                try:
                    cand = p.read_text(encoding="utf-8").strip()
                    if cand:
                        TUSHARE_TOKEN = cand
                        break
                except Exception:
                    continue
    if not TUSHARE_TOKEN:
        logger.info("未检测到 TUSHARE_TOKEN，A/H 股将走 Yahoo Finance 兜底")
        return False
    try:
        # 【关键】tushare 库内部/导入时/pro_api() 可能尝试写 HOME/tk.csv 或 HOME/.tushare/
        # 下的文件，DETACHED 进程安全令牌下 C:\Users\Bart 根目录可能 Permission denied。
        # 这里临时把 HOME/USERPROFILE 切到项目 data_cache/tushare/（可写），
        # import + pro_api() 完成后再还原（或者干脆不还原——之后读 token 都靠 env + 兜底路径）。
        _ts_home = (_BASE_DIR / "data_cache" / "tushare")
        _ts_home.mkdir(parents=True, exist_ok=True)
        (_ts_home / ".tushare").mkdir(exist_ok=True)
        _old_home = os.environ.get("HOME")
        _old_userprof = os.environ.get("USERPROFILE")
        os.environ["HOME"] = str(_ts_home)
        os.environ["USERPROFILE"] = str(_ts_home)
        try:
            import tushare as ts
            ts.set_token(TUSHARE_TOKEN)
            _ts_pro = ts.pro_api()
        finally:
            # 还原，避免影响后续其他库（例如 Path.home() 的后续使用）
            if _old_home is not None:
                os.environ["HOME"] = _old_home
            else:
                os.environ.pop("HOME", None)
            if _old_userprof is not None:
                os.environ["USERPROFILE"] = _old_userprof
            else:
                os.environ.pop("USERPROFILE", None)
        _TS_OK = True
        logger.info("Tushare token 初始化成功（A/H 股将优先走 Tushare）")
        return True
    except Exception as e:
        logger.warning(f"Tushare 初始化失败: {e}，A/H 股走 Yahoo 兜底")
        return False

_init_tushare()


# 【yfinance SQLite 缓存】：重写到项目 data_cache/yfinance，避免 system32 下不可写
if _YF_OK:
    try:
        _YF_LOCAL_CACHE = _BASE_DIR / "data_cache" / "yfinance"
        _YF_LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
        for fn in ("set_tz_cache_location", "_set_tz_cache_dir"):
            if hasattr(yf, fn):
                try:
                    getattr(yf, fn)(str(_YF_LOCAL_CACHE))
                except Exception:
                    pass
        if hasattr(yf, "enable_caching"):
            try:
                yf.enable_caching(False)
            except Exception:
                pass
    except Exception:
        pass


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
    """把 Yahoo 代码转成 Tushare 的 ts_code 格式（仅支持 A/H）"""
    c = yf_code.strip()
    up = c.upper()
    if up.endswith(".SS"):
        return up.replace(".SS", ".SH")
    if up.endswith(".SZ"):
        return up
    if up.endswith(".HK"):
        # Tushare 港股 ts_code 形如 00700.HK（5位数字补零后.HK）
        num_part = c[:-3]
        try:
            num = int(num_part)
            return f"{num:05d}.HK"
        except Exception:
            return up
    return None


def _apply_qfq(daily_raw: pd.DataFrame, adj: pd.DataFrame) -> pd.DataFrame:
    """对 Tushare daily 原始 OHLCV 按最新价做前复权"""
    if daily_raw is None or len(daily_raw) == 0:
        return daily_raw
    df = daily_raw.copy().sort_values("trade_date").reset_index(drop=True)
    if adj is None or len(adj) == 0:
        return df
    adj = adj.sort_values("trade_date").reset_index(drop=True)
    last_factor = float(adj["adj_factor"].iloc[-1])
    if last_factor <= 0:
        return df
    df = df.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
    df["adj_factor"] = df["adj_factor"].ffill().bfill()
    ratio = df["adj_factor"] / last_factor
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = df[col] * ratio
    return df


def _fetch_via_tushare(yf_code: str, days_back: int) -> Optional[pd.DataFrame]:
    """A/H 股通过 Tushare 拉取最近 days_back 天日线（前复权），输出 Yahoo 列格式"""
    if not _TS_OK:
        return None
    market = _market_of(yf_code)
    if market not in ("CN", "HK"):
        return None
    ts_code = _yf_to_ts_code(yf_code)
    if not ts_code:
        return None

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    sd = start_date.strftime("%Y%m%d")
    ed = end_date.strftime("%Y%m%d")

    delays = [1, 2, 4]
    if market == "HK":
        # 港股 hk_daily 免费额度只有 1 次/分钟，遇到频率限制自动等 65 秒再试，
        # 重试次数放宽到 6 次（配合等待足以覆盖 20+ 只港股）
        delays = [65, 65, 65, 65, 65]
    last_err = None
    daily_df = None
    adj_df = None

    for attempt, delay in enumerate(delays, start=1):
        try:
            if market == "CN":
                daily_df = _ts_pro.daily(ts_code=ts_code, start_date=sd, end_date=ed)
                if not isinstance(daily_df, pd.DataFrame) or len(daily_df) == 0:
                    raise ValueError(f"Tushare daily 空数据: {ts_code}")
                try:
                    adj_df = _ts_pro.adj_factor(ts_code=ts_code, start_date=sd, end_date=ed)
                except Exception:
                    adj_df = None
            else:
                daily_df = _ts_pro.hk_daily(ts_code=ts_code, start_date=sd, end_date=ed)
                if not isinstance(daily_df, pd.DataFrame) or len(daily_df) == 0:
                    raise ValueError(f"Tushare hk_daily 空数据: {ts_code}")
            break
        except Exception as e:
            last_err = e
            logger.info(f"[Tushare {attempt}/{len(delays)}] 失败 {yf_code}: {e}")
            msg = str(e)
            if market == "HK" and ("1次/分钟" in msg or "频率超限" in msg):
                # 命中分钟级配额限制 → 强制 sleep 65 秒等窗口重置
                logger.info(f"[Tushare HK] {yf_code} 命中分钟级频率限制，sleep 65s 等待下一个窗口...")
                time.sleep(65)
            elif attempt < len(delays):
                time.sleep(delay)

    if daily_df is None or len(daily_df) < 60:
        if last_err:
            logger.info(f"[Tushare] 放弃 {yf_code}: 数据不足或失败 ({last_err})")
        return None

    try:
        if market == "CN":
            daily_df = _apply_qfq(daily_df, adj_df)
        daily_df = daily_df.sort_values("trade_date").reset_index(drop=True)
        daily_df["trade_date"] = pd.to_datetime(daily_df["trade_date"], format="%Y%m%d")
        out = pd.DataFrame({
            "Open":  daily_df["open"].astype(float).values,
            "High":  daily_df["high"].astype(float).values,
            "Low":   daily_df["low"].astype(float).values,
            "Close": daily_df["close"].astype(float).values,
            "Volume": (daily_df["vol"].astype(float) * (100.0 if market == "CN" else 1.0)).values,
        }, index=daily_df["trade_date"].values)
        out = out[out["Volume"].fillna(0) > 0]
        out = out.dropna(subset=["Close"])
        if len(out) < 60:
            raise ValueError(f"Tushare 清洗后不足60天({len(out)}天): {yf_code}")
        logger.info(f"[Tushare OK] {yf_code}({market}) {len(out)} 行 {out.index[0].date()} ~ {out.index[-1].date()}")
        return out.sort_index()
    except Exception as e:
        logger.info(f"[Tushare] 清洗失败 {yf_code}: {e}，回退 Yahoo")
        return None


def _cache_path(yf_code: str) -> Path:
    safe = yf_code.replace("/", "_").replace(":", "_")
    return _PRICE_CACHE / f"{safe}.pkl"


def _cache_valid(p: Path) -> bool:
    if not p.exists():
        return False
    try:
        age = time.time() - p.stat().st_mtime
        return age < _CACHE_TTL_HOURS * 3600
    except Exception:
        return False


def _read_cache(yf_code: str) -> Optional[pd.DataFrame]:
    p = _cache_path(yf_code)
    if not _cache_valid(p):
        return None
    try:
        with open(p, "rb") as f:
            df = pickle.load(f)
        if isinstance(df, pd.DataFrame) and len(df) >= 60:
            return df
    except Exception as e:
        logger.warning(f"读取缓存失败 {yf_code}: {e}")
    return None


def _write_cache(yf_code: str, df: pd.DataFrame) -> None:
    try:
        with open(_cache_path(yf_code), "wb") as f:
            pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        logger.warning(f"写入缓存失败 {yf_code}: {e}")


def fetch_single_price(yf_code: str, force_refresh: bool = False) -> Optional[pd.DataFrame]:
    """
    拉取单只股票最近2年日K线。
    返回 DataFrame 列：Open, High, Low, Close, Volume，索引为 DatetimeIndex(日期升序)。
    过滤 Volume==0 的无效行。若有效数据不足60行返回 None。
    数据源顺序：
      - A股/港股：Tushare 首选 → 失败则回退 Yahoo Finance
      - 美股/韩股：直接走 Yahoo Finance（每次请求前 sleep 0.8~1.5s 降 QPS）
    """
    global _YF_BACKOFF_UNTIL
    if not force_refresh:
        cached = _read_cache(yf_code)
        if cached is not None:
            return cached

    days_back = 365 * 2 + 30
    mkt = _market_of(yf_code)

    if mkt in ("CN", "HK") and _TS_OK:
        ts_df = _fetch_via_tushare(yf_code, days_back)
        if ts_df is not None:
            _write_cache(yf_code, ts_df)
            return ts_df
        # Tushare 港股失败（常见：hk_daily 5次/天超限），等 2 秒再试 Yahoo，
        # 避免立刻撞到 Yahoo 限流窗口，也给 Tushare 留一点 1次/分钟 的恢复时间
        if mkt == "HK":
            time.sleep(2.0)

    if not _YF_OK:
        logger.error(f"yfinance 未安装，无法拉取 {yf_code}")
        return None

    if _YF_BACKOFF_UNTIL and time.time() < _YF_BACKOFF_UNTIL:
        until = datetime.fromtimestamp(_YF_BACKOFF_UNTIL).strftime("%H:%M:%S")
        logger.warning(f"[YF 退避] 跳过 {yf_code}，限流退避至 {until}")
        return None

    # 美股/韩股 Yahoo 请求前 sleep 0.8~1.5s 随机降低 QPS，避免触发 429
    if mkt in ("US", "KR"):
        time.sleep(_yf_rnd.uniform(0.8, 1.5))

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    delays = [2, 4, 8]
    last_err = None
    df = None
    for attempt, delay in enumerate(delays, start=1):
        try:
            ticker = yf.Ticker(yf_code)
            hist = ticker.history(start=start_date.strftime("%Y-%m-%d"),
                                  end=end_date.strftime("%Y-%m-%d"),
                                  auto_adjust=False, actions=False)
            if hist is None or len(hist) == 0:
                raise ValueError(f"yfinance 返回空数据: {yf_code}")
            df = hist.copy()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df = df.sort_index()
            keep_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[keep_cols]
            df = df[df["Volume"].fillna(0) > 0]
            df = df.dropna(subset=["Close"])
            if len(df) < 60:
                raise ValueError(f"有效数据不足60天({len(df)}天): {yf_code}")
            logger.info(f"[YF {attempt}/3] 拉取成功 {yf_code}: {len(df)} 行, {df.index[0].date()} ~ {df.index[-1].date()}")
            _YF_CONSEC_EMPTY[0] = 0
            if _YF_BACKOFF_LEVEL[0] > 0:
                _YF_BACKOFF_LEVEL[0] = max(0, _YF_BACKOFF_LEVEL[0] - 1)
            break
        except Exception as e:
            last_err = e
            logger.warning(f"[YF {attempt}/3] 拉取失败 {yf_code}: {e}")
            msg = str(e)
            low = msg.lower()
            is_empty_or_rate = (isinstance(e, ValueError) and ("空数据" in msg or "不足60天" in msg or "empty" in low)) \
                               or "429" in msg or "rate limit" in low or "too many" in low
            if is_empty_or_rate:
                _YF_CONSEC_EMPTY[0] += 1
                if _YF_CONSEC_EMPTY[0] >= 2:
                    lvl = min(_YF_BACKOFF_LEVEL[0], len(_YF_BACKOFF_SECONDS) - 1)
                    secs = _YF_BACKOFF_SECONDS[lvl]
                    _YF_BACKOFF_UNTIL = time.time() + secs
                    _YF_BACKOFF_LEVEL[0] = min(len(_YF_BACKOFF_SECONDS) - 1, _YF_BACKOFF_LEVEL[0] + 1)
                    until = datetime.fromtimestamp(_YF_BACKOFF_UNTIL).strftime("%H:%M:%S")
                    mins = secs // 60
                    logger.warning(f"[YF 退避] 连续 {_YF_CONSEC_EMPTY[0]} 只空/限流，进入 {mins} 分钟退避至 {until}（level={_YF_BACKOFF_LEVEL[0]}）")
                break
            else:
                _YF_CONSEC_EMPTY[0] = 0
            if attempt < len(delays):
                time.sleep(delay)

    if df is None:
        logger.error(f"放弃 {yf_code}: {last_err}")
        return None

    _write_cache(yf_code, df)
    return df


def fetch_batch_prices(code_list, force_refresh: bool = False,
                       progress_cb=None) -> Dict[str, pd.DataFrame]:
    """
    批量拉取多只股票价格。返回 {yf_code: DataFrame} 字典。
    progress_cb(done, total, ok_count, fail_count) 可选进度回调。
    """
    results: Dict[str, pd.DataFrame] = {}
    total = len(code_list)
    ok = fail = 0
    for idx, code in enumerate(code_list, start=1):
        df = fetch_single_price(code, force_refresh=force_refresh)
        if df is not None:
            results[code] = df
            ok += 1
        else:
            fail += 1
        if progress_cb:
            try:
                progress_cb(idx, total, ok, fail)
            except Exception:
                pass
    logger.info(f"批量拉取完成: 成功 {ok}/{total}, 失败 {fail}")
    return results

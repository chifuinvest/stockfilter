# -*- coding: utf-8 -*-
"""
评分调度模块
- 股票池增删改查（持久化 stock_pool.json）
- 遍历股票池执行拉取 + 评分
- 评分结果缓存到 data_cache/scores_v2.pkl
- 统计汇总（信号分布等）

免责声明：本系统输出仅供研究和学习使用，不构成任何投资建议。
          市场有风险，投资需谨慎，实盘盈亏自负，版权方不承担法律责任。
版权所有 (c) 2025 Bart · 联系方式：yanying76@gmail.com
"""
import os
import json
import time
import pickle
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("scheduler")

from data_fetcher_v2 import fetch_batch_prices, fetch_single_price
from scoring_engine import score_single

_BASE_DIR = Path(__file__).resolve().parent
STOCK_POOL_PATH = _BASE_DIR / "stock_pool.json"
_SCORE_CACHE_PATH = _BASE_DIR / "data_cache" / "scores_v2.pkl"
(_BASE_DIR / "data_cache").mkdir(parents=True, exist_ok=True)

_MARKET_LABEL = {
    "US": "🇺🇸 美股",
    "CN": "🇨🇳 A股",
    "HK": "🇭🇰 港股",
    "KR": "🇰🇷 韩股",
}

_lock = threading.Lock()
_last_result: Dict[str, Any] = {}
_last_progress: Dict[str, Any] = {"running": False, "done": 0, "total": 0, "ok": 0, "fail": 0}


# ===================== 股票池 IO =====================

def load_stock_pool() -> Dict[str, List[Dict[str, str]]]:
    """加载股票池，不存在则返回空结构"""
    if not STOCK_POOL_PATH.exists():
        logger.warning(f"股票池文件不存在: {STOCK_POOL_PATH}")
        return {"US": [], "CN": [], "HK": [], "KR": []}
    try:
        with open(STOCK_POOL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for m in ["US", "CN", "HK", "KR"]:
            if m not in data:
                data[m] = []
        return data
    except Exception as e:
        logger.error(f"加载股票池失败: {e}")
        return {"US": [], "CN": [], "HK": [], "KR": []}


def save_stock_pool(pool: Dict[str, List[Dict[str, str]]]) -> bool:
    try:
        tmp = STOCK_POOL_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
        tmp.replace(STOCK_POOL_PATH)
        return True
    except Exception as e:
        logger.error(f"保存股票池失败: {e}")
        return False


def flatten_pool(pool: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """把按市场分组的股票池打平为列表，附加 market 字段"""
    rows = []
    for market, items in pool.items():
        for s in items:
            rows.append({"market": market, **s})
    return rows


def add_stock(market: str, code: str, name: str, sector: str = "其他") -> Tuple[bool, str]:
    """向股票池添加一只股票。返回 (成功?, 消息)"""
    market = (market or "").strip().upper()
    code = (code or "").strip()
    name = (name or "").strip()
    sector = (sector or "").strip() or "其他"
    if market not in _MARKET_LABEL:
        return False, f"市场必须是 {list(_MARKET_LABEL.keys())} 之一"
    if not code:
        return False, "代码不能为空"
    if not name:
        return False, "名称不能为空"
    pool = load_stock_pool()
    for exist in pool[market]:
        if exist.get("code", "").upper() == code.upper():
            return False, f"已存在相同代码: {code}"
    pool[market].append({"code": code, "name": name, "sector": sector})
    if save_stock_pool(pool):
        return True, "添加成功，手动点击「刷新」后参与评分"
    return False, "保存股票池文件失败"


def remove_stock(market: str, code: str) -> Tuple[bool, str]:
    market = (market or "").strip().upper()
    code = (code or "").strip()
    if market not in _MARKET_LABEL or not code:
        return False, "参数错误"
    pool = load_stock_pool()
    before = len(pool[market])
    pool[market] = [s for s in pool[market] if s.get("code", "").upper() != code.upper()]
    if len(pool[market]) == before:
        return False, f"未找到 {market}:{code}"
    if save_stock_pool(pool):
        return True, "删除成功"
    return False, "保存股票池文件失败"


def count_pool(pool: Optional[Dict] = None) -> int:
    pool = pool or load_stock_pool()
    return sum(len(v) for v in pool.values())


# ===================== 评分结果读写 =====================

def _read_score_cache() -> Optional[Dict[str, Any]]:
    if not _SCORE_CACHE_PATH.exists():
        return None
    try:
        with open(_SCORE_CACHE_PATH, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        logger.warning(f"读取评分缓存失败: {e}")
        return None


def _write_score_cache(data: Dict[str, Any]) -> None:
    try:
        with open(_SCORE_CACHE_PATH, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        logger.warning(f"写入评分缓存失败: {e}")


# ===================== 核心评分调度 =====================

def _progress_cb(done, total, ok, fail):
    global _last_progress
    with _lock:
        _last_progress = {"running": True, "done": done, "total": total, "ok": ok, "fail": fail}


def run_scoring(force_refresh: bool = False, use_thread: bool = True) -> Dict[str, Any]:
    """
    执行全量评分。若已在运行中则直接返回当前结果。
    先读缓存，缓存可用且非强制刷新则返回缓存。
    """
    global _last_result, _last_progress
    with _lock:
        if _last_progress.get("running"):
            return {"status": "running", "progress": dict(_last_progress), **_last_result}

        if not force_refresh:
            cached = _read_score_cache()
            if cached and isinstance(cached, dict) and cached.get("results"):
                _last_result = cached
                return {"status": "ok", "from_cache": True, **cached}

        _last_progress = {"running": True, "done": 0, "total": 0, "ok": 0, "fail": 0}

    if use_thread:
        t = threading.Thread(target=_do_run_scoring, args=(force_refresh,), daemon=True)
        t.start()
        return {"status": "scheduled", "progress": dict(_last_progress),
                "message": "评分任务已启动，请稍后查看结果"}
    else:
        return _do_run_scoring(force_refresh)


def _do_run_scoring(force_refresh: bool) -> Dict[str, Any]:
    global _last_result, _last_progress
    pool = load_stock_pool()
    flat = flatten_pool(pool)
    N = len(flat)
    with _lock:
        _last_progress = {"running": True, "done": 0, "total": N, "ok": 0, "fail": 0}

    logger.info(f"开始增量评分: {N} 只股票（强制刷新={force_refresh}）")

    results: List[Dict[str, Any]] = []
    ok = fail = 0

    def _flush_partial():
        sorted_results = sorted(results, key=lambda r: (r.get("total_score", -1) or -1), reverse=True)
        stats = _calc_stats(sorted_results)
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "results": sorted_results,
            "stats": stats,
            "updated_at": updated_at,
            "pool_size": count_pool(pool),
            "scored_count": len(sorted_results),
            "partial": True,
        }
        _write_score_cache(payload)
        with _lock:
            _last_result = payload

    for idx, meta in enumerate(flat, start=1):
        code = meta["code"]
        try:
            df = fetch_single_price(code, force_refresh=force_refresh)
            scored = None
            if df is not None:
                scored = score_single(df)
            if scored is not None:
                record = {
                    "market": meta.get("market", ""),
                    "market_label": _MARKET_LABEL.get(meta.get("market", ""), meta.get("market", "")),
                    "code": code,
                    "name": meta.get("name", code),
                    "sector": meta.get("sector", "其他"),
                    **scored,
                }
                results.append(record)
                ok += 1
            else:
                fail += 1
        except Exception as e:
            logger.exception(f"评分异常 {code}: {e}")
            fail += 1
        finally:
            try:
                with _lock:
                    _last_progress = {"running": True, "done": idx, "total": N, "ok": ok, "fail": fail}
                _flush_partial()
            except Exception as fe:
                logger.warning(f"进度/缓存写入异常({code}): {fe}")

    sorted_results = sorted(results, key=lambda r: (r.get("total_score", -1) or -1), reverse=True)
    stats = _calc_stats(sorted_results)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "results": sorted_results,
        "stats": stats,
        "updated_at": updated_at,
        "pool_size": count_pool(pool),
        "scored_count": len(sorted_results),
    }
    _write_score_cache(payload)
    with _lock:
        _last_result = payload
        _last_progress = {"running": False, "done": N, "total": N, "ok": ok, "fail": fail}
    logger.info(f"评分完成: {ok}/{N} 成功, {fail} 失败, 更新时间 {updated_at}")
    return {"status": "ok", "from_cache": False, **payload}


def _calc_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    dist = {"BUY": 0, "HOLD": 0, "WATCH": 0, "REDUCE": 0, "AVOID": 0}
    avg_score = 0.0
    if results:
        scores = [r.get("total_score", 0) or 0 for r in results]
        avg_score = round(sum(scores) / len(scores), 2)
    for r in results:
        lvl = r.get("level", "WATCH")
        if lvl in dist:
            dist[lvl] += 1
    return {
        "total": len(results),
        "BUY": dist["BUY"],
        "HOLD": dist["HOLD"],
        "WATCH": dist["WATCH"],
        "REDUCE": dist["REDUCE"],
        "AVOID": dist["AVOID"],
        "REDUCE_AVOID": dist["REDUCE"] + dist["AVOID"],
        "avg_score": avg_score,
    }


def get_current_result() -> Dict[str, Any]:
    """对外提供：取最新评分结果（带缓存兜底）"""
    global _last_result, _last_progress
    with _lock:
        prog = dict(_last_progress)
        res = dict(_last_result) if _last_result else {}
    if res:
        return {"status": "ok", "progress": prog, **res}
    cached = _read_score_cache()
    if cached:
        with _lock:
            _last_result = cached
        return {"status": "ok", "from_cache": True, "progress": prog, **cached}
    return {"status": "empty", "progress": prog,
            "results": [], "stats": _calc_stats([]),
            "updated_at": "", "pool_size": count_pool(), "scored_count": 0}


def get_progress() -> Dict[str, Any]:
    with _lock:
        return dict(_last_progress)

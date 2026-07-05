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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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
_ALT_CACHE_DIRS: List[Path] = []

def _init_cache_dirs() -> List[Path]:
    """返回按优先级排序的可写缓存目录列表（多路径兜底，防止 Streamlit 容器 /app 不可写）"""
    candidates: List[Path] = []
    candidates.append(_BASE_DIR / "data_cache")
    _home = Path(os.environ.get("HOME") or os.environ.get("USERPROFILE") or Path.home())
    candidates.append(_home / ".cache" / "stockfilter")
    candidates.append(Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp") / "stockfilter_cache")
    ok_dirs: List[Path] = []
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            _probe = p / f".write_probe_{os.getpid()}_{int(time.time()*1000)}.tmp"
            _probe.write_bytes(b"ok")
            _probe.unlink(missing_ok=True)
            ok_dirs.append(p)
        except Exception:
            continue
    if not ok_dirs:
        try:
            (_BASE_DIR / "data_cache").mkdir(parents=True, exist_ok=True)
            ok_dirs.append(_BASE_DIR / "data_cache")
        except Exception:
            pass
    return ok_dirs

_ALT_CACHE_DIRS = _init_cache_dirs()
def _all_cache_files() -> List[Path]:
    files: List[Path] = [_SCORE_CACHE_PATH]
    for d in _ALT_CACHE_DIRS:
        files.append(d / "scores_v2.pkl")
    seen = set()
    uniq: List[Path] = []
    for f in files:
        try:
            k = str(f.resolve())
        except Exception:
            k = str(f)
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq

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
    """多路径 + 多文件兜底读取缓存（任意一个路径读到最新 scored_count 最大的就返回）"""
    best: Optional[Dict[str, Any]] = None
    best_n = -1
    errors: List[str] = []
    for fp in _all_cache_files():
        try:
            if not fp.exists():
                continue
            with open(fp, "rb") as f:
                obj = pickle.load(f)
            if isinstance(obj, dict):
                n = int(obj.get("scored_count") or 0)
                if n > best_n:
                    best_n = n
                    best = obj
        except Exception as e:
            errors.append(f"{fp.name}:{e}")
    if errors:
        logger.warning(f"读取缓存部分失败: {'; '.join(errors[:3])}")
    return best


def _write_score_cache(data: Dict[str, Any]) -> None:
    """多路径 + 重试 + tmp 原子替换写入缓存（至少 1 个路径写成功才返回，否则报错）"""
    written = 0
    last_err: Optional[str] = None
    payload_bytes = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    for fp in _all_cache_files():
        for attempt in range(3):
            try:
                fp.parent.mkdir(parents=True, exist_ok=True)
                tmp = fp.with_suffix(fp.suffix + f".tmp{os.getpid()}")
                with open(tmp, "wb") as f:
                    f.write(payload_bytes)
                    try:
                        f.flush()
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                tmp.replace(fp)
                written += 1
                last_err = None
                break
            except Exception as e:
                last_err = f"{fp}:{e}"
                time.sleep(0.05 * (attempt + 1))
    if written == 0:
        logger.error(f"写缓存全部失败: {last_err}")
        raise IOError(f"Failed to write score cache to ALL paths: {last_err}")


# ===================== 核心评分调度 =====================

def _progress_cb(done, total, ok, fail, wait_msg: Optional[str] = None, wait_remaining_seconds: int = 0):
    """更新进度状态；可选 wait_msg 用于长等待时的提示（如港股配额/Yahoo 退避），让用户知道没卡死"""
    global _last_progress
    with _lock:
        payload = {"running": True, "done": done, "total": total, "ok": ok, "fail": fail}
        if wait_msg:
            payload["wait_msg"] = wait_msg
            payload["wait_remaining_seconds"] = int(max(0, wait_remaining_seconds))
        _last_progress = payload


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

    # ===== 单票超时保护：60 秒内必须完成 fetch+score，否则直接标记失败，避免单只股票卡死导致整个任务停在原地（用户反馈：11/157 卡住不再动） =====
    _SINGLE_TICKET_TIMEOUT_SECONDS = 60
    # 提供给 data_fetcher_v2 长 sleep（港股配额等待等）时调用的全局进度通知
    import data_fetcher_v2 as _dfv2
    if not getattr(_dfv2, "_progress_wait_hook", None):
        def _hook(msg, remaining):
            _progress_cb(max(0, idx-1), N, ok, fail, wait_msg=msg, wait_remaining_seconds=int(remaining))
        _dfv2._progress_wait_hook = _hook

    def _process_one(meta_dict):
        """单线程内处理 1 只股票：fetch → 评分 → 返回结果。被 ThreadPoolExecutor 包装加 60s 总超时。"""
        code_one = meta_dict["code"]
        mkt = meta_dict.get("market", "")
        df_one = fetch_single_price(code_one, force_refresh=force_refresh)
        scored_one = None
        if df_one is not None:
            scored_one = score_single(df_one)
        return scored_one, mkt, meta_dict

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="score_worker") as pool:
        for idx, meta in enumerate(flat, start=1):
            code = meta["code"]
            try:
                future = pool.submit(_process_one, meta)
                # 单票 60 秒硬超时：超过则取消，标记失败，直接下一只，绝对不卡
                scored, _, _meta = future.result(timeout=_SINGLE_TICKET_TIMEOUT_SECONDS)
                if scored is not None:
                    record = {
                        "market": _meta.get("market", ""),
                        "market_label": _MARKET_LABEL.get(_meta.get("market", ""), _meta.get("market", "")),
                        "code": code,
                        "name": _meta.get("name", code),
                        "sector": _meta.get("sector", "其他"),
                        **scored,
                    }
                    results.append(record)
                    ok += 1
                else:
                    fail += 1
            except FuturesTimeoutError:
                logger.warning(f"单票超时({_SINGLE_TICKET_TIMEOUT_SECONDS}s)，标记失败并跳过：{code}")
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
    """对外提供：取最新评分结果（多路径缓存兜底 + 进度-结果一致性自修复）

    自修复逻辑：
      - 如果 _last_progress.ok >= 2 但内存+磁盘 scored_count 都是 0 → 状态严重异常
        （典型：旧线程被 Streamlit Runtime 销毁，进度变量残留但结果&缓存全丢了）
        → 自动把 _last_progress 重置为 0/running=False，并在返回值里标记 stale=True
        让前端 UI 展示「检测到历史残留进度，已清理，请重新评分」提示
    """
    global _last_result, _last_progress
    with _lock:
        prog = dict(_last_progress)
        res = dict(_last_result) if _last_result else {}

    prog_ok = int(prog.get("ok") or 0)
    mem_scored = int(res.get("scored_count") or 0) if res else 0

    need_repair = (
        prog_ok > 0 and prog_ok - mem_scored > 1
    )

    stale_recovered = False
    if res and not need_repair:
        return {"status": "ok", "progress": prog, **res}

    cached = _read_score_cache()
    disk_scored = int((cached or {}).get("scored_count") or 0)

    if prog_ok >= 2 and mem_scored == 0 and disk_scored == 0:
        logger.warning(f"检测到脏状态: progress.ok={prog_ok} 但内存/磁盘 scored_count=0，自动清理进度并标记 stale")
        stale_recovered = True
        with _lock:
            _last_progress = {"running": False, "done": 0, "total": 0, "ok": 0, "fail": 0}
        prog = dict(_last_progress)

    if cached and disk_scored >= max(mem_scored, 0 if stale_recovered else mem_scored):
        with _lock:
            _last_result = cached
        out = {"status": "ok", "from_cache": True, "progress": prog, **cached}
        if stale_recovered:
            out["stale_recovered"] = True
        return out

    if res:
        out = {"status": "ok", "progress": prog, **res}
        if stale_recovered:
            out["stale_recovered"] = True
        return out

    empty = {"status": "empty", "progress": prog,
             "results": [], "stats": _calc_stats([]),
             "updated_at": "", "pool_size": count_pool(), "scored_count": 0}
    if stale_recovered:
        empty["stale_recovered"] = True
    return empty


def get_progress() -> Dict[str, Any]:
    with _lock:
        return dict(_last_progress)

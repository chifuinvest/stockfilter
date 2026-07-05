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
_PROGRESS_CACHE_PATH = _BASE_DIR / "data_cache" / "progress_v2.pkl"
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

def _all_cache_files_for(basename: str) -> List[Path]:
    default = _BASE_DIR / "data_cache" / basename
    files: List[Path] = [default]
    for d in _ALT_CACHE_DIRS:
        files.append(d / basename)
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

def _all_score_files() -> List[Path]:
    return _all_cache_files_for("scores_v2.pkl")

def _all_progress_files() -> List[Path]:
    return _all_cache_files_for("progress_v2.pkl")

def _all_cache_files() -> List[Path]:
    return _all_score_files()

def _inspect_caches() -> List[Dict[str, Any]]:
    """调试接口：返回所有缓存路径的元信息，便于前端展示诊断面板"""
    rows: List[Dict[str, Any]] = []
    for kind, files in (("scores", _all_score_files()), ("progress", _all_progress_files())):
        for fp in files:
            row: Dict[str, Any] = {"kind": kind, "path": str(fp)}
            try:
                if fp.exists():
                    st = fp.stat()
                    row["exists"] = True
                    row["size_bytes"] = int(st.st_size)
                    row["mtime"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        with open(fp, "rb") as f:
                            obj = pickle.load(f)
                        if isinstance(obj, dict):
                            if kind == "scores":
                                row["scored_count"] = int(obj.get("scored_count") or 0)
                                row["pool_size"] = int(obj.get("pool_size") or 0)
                                row["partial"] = bool(obj.get("partial", False))
                            else:
                                row["progress_done"] = int(obj.get("done") or 0)
                                row["progress_total"] = int(obj.get("total") or 0)
                                row["progress_ok"] = int(obj.get("ok") or 0)
                                row["progress_running"] = bool(obj.get("running", False))
                    except Exception as pe:
                        row["parse_error"] = str(pe)[:80]
                else:
                    row["exists"] = False
            except Exception as e:
                row["stat_error"] = str(e)[:80]
            rows.append(row)
    return rows

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

def _read_any_cache(basename: str, compare_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """读取某类缓存（scores/progress），从所有路径中挑 compare_key 值最大的那份返回（compare_key=None 则取最新 mtime）"""
    best: Optional[Dict[str, Any]] = None
    best_key_val = -1 if compare_key else 0.0
    best_mtime = -1.0
    errors: List[str] = []
    for fp in _all_cache_files_for(basename):
        try:
            if not fp.exists():
                continue
            st_info = fp.stat()
            mtime = float(st_info.st_mtime)
            with open(fp, "rb") as f:
                obj = pickle.load(f)
            if not isinstance(obj, dict):
                continue
            if compare_key:
                val = int(obj.get(compare_key) or 0)
                better = val > best_key_val or (val == best_key_val and mtime > best_mtime)
                if better:
                    best_key_val = val
                    best_mtime = mtime
                    best = obj
            else:
                if mtime > best_mtime:
                    best_mtime = mtime
                    best = obj
        except Exception as e:
            errors.append(f"{fp.name}:{e}")
    if errors:
        logger.warning(f"读缓存[{basename}]部分失败: {'; '.join(errors[:3])}")
    return best


def _write_any_cache(basename: str, data: Dict[str, Any]) -> None:
    """多路径+重试+原子+fsync写某类缓存。至少 1 路径成功返回；全失败抛 IOError。"""
    written = 0
    last_err: Optional[str] = None
    payload_bytes = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    for fp in _all_cache_files_for(basename):
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
        msg = f"写缓存[{basename}]全部路径失败: {last_err}"
        logger.error(msg)
        raise IOError(msg)


def _read_score_cache() -> Optional[Dict[str, Any]]:
    return _read_any_cache("scores_v2.pkl", compare_key="scored_count")


def _write_score_cache(data: Dict[str, Any]) -> None:
    _write_any_cache("scores_v2.pkl", data)


def _read_progress_cache() -> Optional[Dict[str, Any]]:
    return _read_any_cache("progress_v2.pkl", compare_key="done")


def _write_progress_cache(data: Dict[str, Any]) -> None:
    _write_any_cache("progress_v2.pkl", data)


# ===================== 核心评分调度 =====================

def _progress_cb(done, total, ok, fail, wait_msg: Optional[str] = None, wait_remaining_seconds: int = 0):
    """更新进度状态（内存 + 磁盘双写，彻底支持 Streamlit Cloud 多 worker 跨进程共享）"""
    global _last_progress
    payload: Dict[str, Any] = {"running": True, "done": int(done), "total": int(total), "ok": int(ok), "fail": int(fail)}
    if wait_msg:
        payload["wait_msg"] = wait_msg
        payload["wait_remaining_seconds"] = int(max(0, wait_remaining_seconds))
    with _lock:
        _last_progress = dict(payload)
    # 立刻写磁盘——任何 worker 下次调用 get_progress/get_current_result 都能立刻读到最新进度
    try:
        _write_progress_cache(payload)
    except Exception as e:
        logger.warning(f"进度落盘失败: {e}")


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

        _reset_prog = {"running": True, "done": 0, "total": 0, "ok": 0, "fail": 0}
        with _lock:
            _last_progress = dict(_reset_prog)
        try:
            _write_progress_cache(_reset_prog)
        except Exception:
            pass

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
    _init_prog = {"running": True, "done": 0, "total": N, "ok": 0, "fail": 0}
    with _lock:
        _last_progress = dict(_init_prog)
    try:
        _write_progress_cache(_init_prog)
    except Exception:
        pass

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
                    _cur_prog = {"running": True, "done": idx, "total": N, "ok": ok, "fail": fail}
                    with _lock:
                        _last_progress = dict(_cur_prog)
                    try:
                        _write_progress_cache(_cur_prog)
                    except Exception:
                        pass
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
    _final_prog = {"running": False, "done": N, "total": N, "ok": ok, "fail": fail}
    with _lock:
        _last_result = payload
        _last_progress = dict(_final_prog)
    try:
        _write_progress_cache(_final_prog)
    except Exception:
        pass
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


def get_progress() -> Dict[str, Any]:
    """取进度：内存 vs 磁盘，取 done 值最大的那份返回（跨 Streamlit worker 共享）"""
    global _last_progress
    with _lock:
        mem = dict(_last_progress)
    mem_done = int(mem.get("done") or 0)
    disk = _read_progress_cache() or {}
    disk_done = int(disk.get("done") or 0)
    if disk_done > mem_done or (not mem and disk_done > 0):
        merged = dict(disk)
    else:
        merged = mem
    running_disk = bool((disk or {}).get("running", False))
    if running_disk and not merged.get("running"):
        merged["running"] = True
    merged.setdefault("running", False)
    merged.setdefault("done", 0)
    merged.setdefault("total", 0)
    merged.setdefault("ok", 0)
    merged.setdefault("fail", 0)
    return merged


def get_current_result() -> Dict[str, Any]:
    """对外提供：取最新评分结果（磁盘优先 + 内存兜底 = Single Source of Truth 跨 worker 共享）

    架构核心变更：
      Streamlit Cloud 采用多 worker / fork-on-rerun 模型，评分线程写的内存变量只对写的那个进程可见。
      所以这里**无条件先读磁盘**（scored_count 最大的那份），再和内存合并取最优值。
      这样只要 `_flush_partial()` 每只写一次磁盘成功，所有 worker 都能读到最新结果。
    """
    global _last_result, _last_progress

    disk_scores = _read_score_cache()
    disk_prog = _read_progress_cache()

    with _lock:
        mem_prog = dict(_last_progress)
        mem_res = dict(_last_result) if _last_result else {}

    # -------- 合并进度：磁盘 vs 内存，取 done 更大的 --------
    mem_done = int(mem_prog.get("done") or 0)
    disk_done = int((disk_prog or {}).get("done") or 0)
    if disk_done > mem_done or (not mem_prog and disk_done > 0):
        prog = dict(disk_prog or {})
    else:
        prog = dict(mem_prog)
    running_disk = bool((disk_prog or {}).get("running", False))
    if running_disk and not prog.get("running"):
        prog["running"] = True
    prog.setdefault("running", False)
    prog.setdefault("done", 0)
    prog.setdefault("total", 0)
    prog.setdefault("ok", 0)
    prog.setdefault("fail", 0)

    prog_ok = int(prog.get("ok") or 0)

    # -------- 合并结果：磁盘 vs 内存，取 scored_count 更大的 --------
    disk_scored = int((disk_scores or {}).get("scored_count") or 0)
    mem_scored = int(mem_res.get("scored_count") or 0) if mem_res else 0

    stale_recovered = False
    if (disk_scores or {}).get("scored_count", 0) is not None:
        if disk_scored >= mem_scored and disk_scores is not None:
            final_res = dict(disk_scores)
            final_src = "disk"
            with _lock:
                if disk_scored > mem_scored:
                    _last_result = disk_scores
        elif mem_res:
            final_res = mem_res
            final_src = "mem"
        else:
            final_res = {}
            final_src = "empty"
    else:
        final_res = mem_res if mem_res else {}
        final_src = "mem" if mem_res else "empty"

    final_scored = int(final_res.get("scored_count") or 0) if final_res else 0

    # -------- stale 自修复：progress.ok >=2 但 final_scored=0（典型：旧线程销毁但缓存全丢）--------
    if prog_ok >= 2 and final_scored == 0:
        logger.warning(f"[stale修复] progress.ok={prog_ok} 但结果=0, 清理进度并标记")
        stale_recovered = True
        reset = {"running": False, "done": 0, "total": 0, "ok": 0, "fail": 0}
        with _lock:
            _last_progress = dict(reset)
        try:
            _write_progress_cache(reset)
        except Exception:
            pass
        prog = reset

    if final_res:
        out = {"status": "ok", "progress": prog, "debug_src": final_src, **final_res}
        if stale_recovered:
            out["stale_recovered"] = True
        return out

    empty = {"status": "empty", "progress": prog, "debug_src": final_src,
             "results": [], "stats": _calc_stats([]),
             "updated_at": "", "pool_size": count_pool(), "scored_count": 0}
    if stale_recovered:
        empty["stale_recovered"] = True
    return empty

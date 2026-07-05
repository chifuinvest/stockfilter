# -*- coding: utf-8 -*-
"""
AI 产业链全市场量化监控系统 · v1.0
单文件 Flask 入口
- 页面: GET /
- API:
    GET  /api/scores       获取评分结果和更新时间
    POST /api/refresh      触发刷新（重新拉取行情并评分）
    POST /api/stocks       添加股票
    DELETE /api/stocks     删除股票
    GET  /api/stocks       获取股票池

================================================================================
免责声明：
    本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标、股票池等）
    仅供研究和学习使用，**不构成任何投资建议或承诺**。
    市场有风险，投资需谨慎，任何基于本系统进行的实盘交易行为，盈亏自负，
    作者及版权方不承担任何法律责任。

版权所有 (c) 2025 Bart
联系方式：yanying76@gmail.com
================================================================================
"""
import os
import sys
import socket
import argparse
from pathlib import Path
from datetime import datetime

try:
    socket.setdefaulttimeout(25)
except Exception:
    pass

# =============================================================================
# 【关键】启动早期强制修复用户环境变量
# DETACHED_PROCESS / CREATE_NO_WINDOW 启动的子进程可能未加载用户 profile，
# 导致 Path.home() = C:\Windows\System32\config\systemprofile
# 进而：Tushare 找不到 token.txt、yfinance 在 system32 里打不开 SQLite 缓存。
# 这里在任何项目模块被 import 之前先纠正环境。
# =============================================================================
def _bootstrap_user_env():
    # 0) 先把 tempfile 临时目录强制改到可写路径，
    #    yfinance / requests-cache / sqlite 内部都用 tempfile.gettempdir() 建缓存
    import tempfile
    proj_dir = Path(__file__).resolve().parent
    temp_dir = proj_dir / "data_cache" / "yfinance"
    temp_dir.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temp_dir)
    try:
        # Windows 下也修改这些环境变量
        os.environ["TMP"] = str(temp_dir)
        os.environ["TEMP"] = str(temp_dir)
        os.environ["TMPDIR"] = str(temp_dir)
        os.environ["SQLITE_TMPDIR"] = str(temp_dir)
    except Exception:
        pass

    # 1) 找真实用户目录
    candidate_dirs = []
    for env_key in ("USERPROFILE", "HOME"):
        v = os.environ.get(env_key) or ""
        if v and Path(v).exists() and "systemprofile" not in v.lower() and "system32" not in v.lower():
            candidate_dirs.append(Path(v))
    try:
        import getpass
        guess = Path("C:/Users") / getpass.getuser()
        if guess.exists(): candidate_dirs.append(guess)
    except Exception:
        pass
    candidate_dirs.append(Path("C:/Users/Bart"))

    user_home = candidate_dirs[0]
    for d in candidate_dirs:
        if (d / ".tushare" / "token.txt").exists():
            user_home = d
            break
    os.environ["USERPROFILE"] = str(user_home)
    os.environ["HOME"] = str(user_home)

    # 2) Tushare token：读到就提前塞环境变量，保证 data_fetcher_v2 被 import 时就能拿到
    tok_file = user_home / ".tushare" / "token.txt"
    if tok_file.exists():
        try:
            tok = tok_file.read_text(encoding="utf-8").strip()
            if tok:
                os.environ["TUSHARE_TOKEN"] = tok
        except Exception:
            pass

    # 3) yfinance / TZ 缓存：重定向到项目 data_cache/yfinance（保证可写）
    for env_key in ("YF_CACHE_DIR", "YF_CACHE_PATH", "TZ_CACHE_PATH"):
        os.environ[env_key] = str(temp_dir)
    return user_home, proj_dir, temp_dir

_BOOT_HOME, _BOOT_PROJ, _BOOT_TEMP = _bootstrap_user_env()

# 【yfinance 前置补丁】：import 前先确保所有内部缓存路径都在可写位置
try:
    import tempfile
    tempfile.tempdir = str(_BOOT_TEMP)
    import yfinance as yf
    _YF_CACHE = _BOOT_TEMP
    for fn in ("set_tz_cache_location", "_set_tz_cache_dir"):
        if hasattr(yf, fn):
            try:
                getattr(yf, fn)(str(_YF_CACHE))
            except Exception:
                pass
    if hasattr(yf, "enable_caching"):
        try:
            yf.enable_caching(False)
        except Exception:
            pass
    if hasattr(yf, "enable_debug_mode"):
        try:
            yf.enable_debug_mode(False)
        except Exception:
            pass
except Exception:
    pass

try:
    from loguru import logger
    _LOGURU_OK = True
except Exception:
    _LOGURU_OK = False
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    logger = logging.getLogger("ai_monitor")

from flask import Flask, render_template, request, jsonify

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from scoring_scheduler import (
    run_scoring, get_current_result, get_progress,
    load_stock_pool, add_stock, remove_stock, count_pool,
)

app = Flask(__name__)
app.json.ensure_ascii = False


# ===================== 页面 =====================

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


# ===================== API: 评分 =====================

@app.route("/api/scores", methods=["GET"])
def api_scores():
    try:
        data = get_current_result()
        if not data.get("results"):
            triggered = run_scoring(force_refresh=False, use_thread=True)
            data = get_current_result()
            data["schedule"] = triggered.get("status")
        return jsonify(data)
    except Exception as e:
        logger.exception(f"/api/scores 异常: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    try:
        force = True
        data = request.get_json(silent=True) or {}
        if isinstance(data, dict):
            force = bool(data.get("force", True))
        ret = run_scoring(force_refresh=force, use_thread=True)
        return jsonify(ret)
    except Exception as e:
        logger.exception(f"/api/refresh 异常: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/progress", methods=["GET"])
def api_progress():
    try:
        return jsonify(get_progress())
    except Exception as e:
        return jsonify({"running": False, "error": str(e)})


# ===================== API: 股票池 =====================

@app.route("/api/stocks", methods=["GET"])
def api_stocks_get():
    try:
        pool = load_stock_pool()
        return jsonify({"status": "ok", "pool": pool, "total": count_pool(pool)})
    except Exception as e:
        logger.exception(e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/stocks", methods=["POST"])
def api_stocks_add():
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"ok": False, "message": "请求体必须为 JSON"}), 400
        ok, msg = add_stock(
            market=data.get("market", ""),
            code=data.get("code", ""),
            name=data.get("name", ""),
            sector=data.get("sector", "其他"),
        )
        return jsonify({"ok": ok, "message": msg}), (200 if ok else 400)
    except Exception as e:
        logger.exception(e)
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/stocks", methods=["DELETE"])
def api_stocks_remove():
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"ok": False, "message": "请求体必须为 JSON"}), 400
        ok, msg = remove_stock(
            market=data.get("market", ""),
            code=data.get("code", ""),
        )
        return jsonify({"ok": ok, "message": msg}), (200 if ok else 400)
    except Exception as e:
        logger.exception(e)
        return jsonify({"ok": False, "message": str(e)}), 500


# ===================== 启动入口 =====================

def _parse_args():
    p = argparse.ArgumentParser(description="AI 产业链全市场量化监控系统")
    p.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "5000")),
        help="Flask 监听端口 (默认 5000，Railway/云平台会通过 $PORT 注入)",
    )
    p.add_argument("--host", type=str, default=os.environ.get("HOST", "0.0.0.0"),
                   help="Flask 监听地址")
    p.add_argument("--skip-first-score", action="store_true",
                   help="跳过启动时的首轮评分（用缓存即可；生产部署推荐开启，避免启动超时）")
    return p.parse_args()


def main():
    args = _parse_args()
    logger.info("=" * 60)
    logger.info("AI 产业链全市场量化监控系统 · v1.0")
    logger.info(f"股票池: stock_pool.json（共 {count_pool()} 只）")
    logger.info("=" * 60)

    if not args.skip_first_score:
        logger.info("首次启动触发首轮评分（后台线程，页面可立即访问）...")
        try:
            run_scoring(force_refresh=False, use_thread=True)
        except Exception as e:
            logger.exception(f"首轮评分调度失败: {e}")

    try:
        logger.info(f"Flask 监听 http://{args.host}:{args.port}/")
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("服务已停止")
    except Exception as e:
        logger.exception(f"Flask 异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

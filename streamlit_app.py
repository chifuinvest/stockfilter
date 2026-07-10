# =============================================================================
# AI 产业链全市场量化监控系统 · Streamlit 入口
# 部署：Streamlit Community Cloud（完全免费，只要 GitHub 公开仓库）
# 启动：streamlit run streamlit_app.py
# =============================================================================
# 免责声明：
#     本系统及其输出的评分、信号、涨跌幅、技术指标等数据仅供研究与学习使用，
#     **不构成任何投资建议或承诺**。市场有风险，投资需谨慎，任何基于
#     本系统进行的实盘交易行为盈亏自负，作者及版权方不承担任何法律责任。
#
# 版权所有 (c) 2025 Bart
# 联系方式：yanying76@gmail.com
# =============================================================================
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import streamlit as st

# -----------------------------------------------------------------------------
# 0. 页面基础配置（必须放在所有 Streamlit 命令之前）
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI 产业链量化监控 · 中美港韩四市场",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "AI 产业链全市场量化监控系统（v1.0）\n\n"
                 "覆盖中美港韩四市场 150+ AI 产业链股票\n"
                 "6 维度技术评分（MA/MACD/RSI/BOLL/量能/KDJ）加权打分\n"
                 "GitHub: https://github.com/chifuinvest/stockfilter",
        "Get help": "https://github.com/chifuinvest/stockfilter",
        "Report a bug": "https://github.com/chifuinvest/stockfilter/issues",
    },
)

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# -----------------------------------------------------------------------------
# 0.5 Streamlit Secrets 注入到环境变量（关键！）
#     Streamlit Community Cloud 控制台里 Secrets 是 TOML 格式：
#       TUSHARE_TOKEN = "xxx"
#       PYTHONUNBUFFERED = "1"
#     我们把所有 key-value 转成 os.environ，这样 scoring_scheduler / data_fetcher_v2
#     无需任何修改，直接从 os.environ["TUSHARE_TOKEN"] 读到 token
# -----------------------------------------------------------------------------
try:
    if hasattr(st, "secrets"):
        _secrets_items = dict(st.secrets)
        for _k, _v in _secrets_items.items():
            if isinstance(_v, (str, int, float, bool)):
                os.environ[str(_k)] = str(_v).strip()
            elif isinstance(_v, dict):
                for _sk, _sv in _v.items():
                    if isinstance(_sv, (str, int, float, bool)):
                        os.environ[str(_sk).upper()] = str(_sv).strip()
except Exception:
    pass

os.environ["HOME"] = os.environ.get("HOME") or "/app"
os.environ["TZ"] = os.environ.get("TZ") or "Asia/Shanghai"

# -----------------------------------------------------------------------------
# 1. 导入后端引擎
# -----------------------------------------------------------------------------
try:
    import scoring_scheduler as sch
    import data_fetcher_v2 as fetcher  # noqa: F401
    _BACKEND_OK = True
    _BACKEND_ERR = ""
except Exception as e:  # pragma: no cover
    _BACKEND_OK = False
    _BACKEND_ERR = str(e)
    sch = None

try:
    import stock_analyzer as san
    import financial_analyzer as fan  # noqa: F401
    _SA_OK = True
    _SA_ERR = ""
except Exception as e:
    _SA_OK = False
    _SA_ERR = str(e)
    san = None

# -----------------------------------------------------------------------------
# 2. 常量
# -----------------------------------------------------------------------------
SIGNAL_LABEL: Dict[str, str] = {
    "BUY": "🟢 买入",
    "HOLD": "🔵 持有",
    "WATCH": "🟡 观望",
    "REDUCE": "🟠 减仓",
    "AVOID": "🔴 回避",
}
SIGNAL_ORDER: List[str] = ["BUY", "HOLD", "WATCH", "REDUCE", "AVOID"]
SIGNAL_COLOR_CSS: Dict[str, str] = {
    "BUY": "background-color: #d1e7dd; color: #0f5132;",
    "HOLD": "background-color: #cfe2ff; color: #084298;",
    "WATCH": "background-color: #fff3cd; color: #664d03;",
    "REDUCE": "background-color: #ffe5d0; color: #8a4500;",
    "AVOID": "background-color: #f8d7da; color: #842029;",
}
MARKET_LABEL: Dict[str, str] = {
    "US": "🇺🇸 美股",
    "CN": "🇨🇳 A股",
    "HK": "🇭🇰 港股",
    "KR": "🇰🇷 韩股",
}


def _fetch_scores() -> Dict[str, Any]:
    if not _BACKEND_OK:
        return {"results": [], "pool_size": 0, "scored_count": 0, "updated_at": "", "from_cache": False}
    data = sch.get_current_result() or {}
    data.setdefault("from_cache", True)
    return data


def _summary_by_signal(results: List[Dict[str, Any]]) -> Dict[str, int]:
    cnt = {k: 0 for k in SIGNAL_ORDER}
    for r in results or []:
        sig = (r.get("signal") or "WATCH").upper()
        if sig in cnt:
            cnt[sig] += 1
    return cnt


# -----------------------------------------------------------------------------
# 4. 侧边栏
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🛠️ 控制面板")

    st.subheader("🔄 刷新评分")
    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button("📥 读取缓存", use_container_width=True, type="secondary"):
            try: st.cache_data.clear()
            except Exception: pass
            st.session_state["__force_hash__"] = f"v{int(time.time())}"
            st.success("✅ 已读取缓存中最新结果")
            st.rerun()
    with c2:
        if st.button("⚡ 强制重新评分", use_container_width=True, type="primary"):
            if _BACKEND_OK:
                try: st.cache_data.clear()
                except Exception: pass
                resp = sch.run_scoring(force_refresh=True, use_thread=True)
                st.session_state["__force_hash__"] = f"v{int(time.time())}"
                status = resp.get("status")
                if status in ("scheduled", "running"):
                    st.info("✅ 评分任务已在后台启动")
                else:
                    st.success("✅ 评分完成")
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(f"后端不可用：{_BACKEND_ERR[:120]}")

    st.divider()

    st.subheader("🔍 信号筛选")
    filter_options = ["📊 全部"] + [SIGNAL_LABEL[s] for s in SIGNAL_ORDER]
    selected_label = st.radio(
        "按交易信号过滤结果",
        options=filter_options,
        index=0,
        horizontal=False,
    )
    _filter_signal: str = ""
    for k, v in SIGNAL_LABEL.items():
        if v == selected_label:
            _filter_signal = k
            break

    st.divider()

    st.subheader("➕ 添加股票")
    with st.form("add_stock_form", clear_on_submit=True):
        mkt = st.selectbox("市场", list(MARKET_LABEL.keys()), format_func=lambda x: MARKET_LABEL[x], index=1)
        code = st.text_input("代码（例如 688256.SS / AAPL / 00700.HK）", max_chars=32)
        name = st.text_input("股票名称", max_chars=64)
        sector = st.text_input("所属环节（AI 芯片/大模型/算力/其他）", value="其他", max_chars=64)
        submitted = st.form_submit_button("✅ 添加到股票池", use_container_width=True, type="primary")
        if submitted:
            if _BACKEND_OK:
                ok, msg = sch.add_stock(mkt, code, name, sector)
                if ok:
                    st.success(msg)
                    st.session_state["__force_hash__"] = f"v{int(time.time())}"
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.error("后端不可用")

    st.divider()

    st.subheader("➖ 删除股票")
    if _BACKEND_OK:
        pool = sch.load_stock_pool()
        flat: List[Tuple[str, str, str]] = []
        for mkt_name, stocks in pool.items():
            for s in stocks or []:
                flat.append((mkt_name, str(s.get("code", "")), str(s.get("name", ""))))
        flat.sort(key=lambda x: (x[0], x[1]))
        display_opts = [f"[{m}] {c} — {n}" for m, c, n in flat]
        selected_del = st.multiselect("选择要删除的股票（可多选）", options=display_opts)
        if st.button("🗑️ 确认删除选中", use_container_width=True, type="secondary", disabled=len(selected_del) == 0):
            if _BACKEND_OK:
                ok_cnt = 0
                errs: List[str] = []
                for d in selected_del:
                    try:
                        left = d.split("]", 1)[0]
                        mkt = left.replace("[", "").strip()
                        rest = d.split("—", 1)[0].split("]", 1)[1].strip()
                        code = rest.strip()
                        ok, _ = sch.remove_stock(mkt, code)
                        if ok:
                            ok_cnt += 1
                        else:
                            errs.append(code)
                    except Exception as e:
                        errs.append(str(e))
                st.session_state["__force_hash__"] = f"v{int(time.time())}"
                if errs:
                    st.warning(f"成功删除 {ok_cnt} 只，失败 {len(errs)} 只")
                else:
                    st.success(f"✅ 成功删除 {ok_cnt} 只股票")
                time.sleep(1)
                st.rerun()
    else:
        st.error("后端不可用")

    st.divider()
    st.caption("💡 Streamlit Cloud 版本：Yahoo 限流/港股 Tushare 1次/分钟 限制仍存在，美股/港股会在几分钟~几十分钟内陆续补齐评分。")


# -----------------------------------------------------------------------------
# 5. 双 Tab 主体
# -----------------------------------------------------------------------------
tab_pool, tab_single = st.tabs([
    "📊 全市场量化监控 · AI 产业链",
    "🔍 单股票深度分析 · 财报+技术面",
])

# ===================== Tab 1: 全市场量化监控 =====================
with tab_pool:
    st.markdown(
        """
        <h1 style="margin-top:-12px;margin-bottom:0;">
            📈 AI 产业链全市场量化监控系统
        </h1>
        <p style="margin-top:6px;color:#6c757d;font-size:16px;">
            覆盖 🇺🇸 美股 / 🇨🇳 A股 / 🇭🇰 港股 / 🇰🇷 韩股 共 <b>150+</b> 只 AI 全产业链股票，
            6 维度技术指标加权评分（MA30% / MACD20% / RSI15% / BOLL10% / 量能15% / KDJ10%），
            0~100 分综合打分 + 五档交易信号判定
        </p>
        """,
        unsafe_allow_html=True,
    )

    data = _fetch_scores() or {}
    results: List[Dict[str, Any]] = data.get("results") or []
    pool_size = int(data.get("pool_size", 0) or 0)
    scored_count = int(data.get("scored_count", 0) or 0)
    updated_at = str(data.get("updated_at") or "")
    from_cache = bool(data.get("from_cache", False))
    stale_recovered = bool(data.get("stale_recovered", False))

    progress_placeholder = st.empty()
    status_text = st.empty()

    try:
        if _BACKEND_OK:
            prog_direct = sch.get_progress() if sch else {}
            prog_from_data = data.get("progress", {}) if isinstance(data, dict) else {}

            def _merge_p(a, b):
                m = dict(a) if isinstance(a, dict) else {}
                b = dict(b) if isinstance(b, dict) else {}
                if int(b.get("total") or 0) > int(m.get("total") or 0) or \
                   int(b.get("ok") or 0) > int(m.get("ok") or 0) or \
                   int(b.get("done") or 0) > int(m.get("done") or 0):
                    for _kk, _vv in b.items():
                        m.setdefault(_kk, _vv)
                if bool(b.get("running")) and not bool(m.get("running")):
                    m["running"] = True
                if b.get("wait_msg") and not m.get("wait_msg"):
                    m["wait_msg"] = b["wait_msg"]
                    m["wait_remaining_seconds"] = b.get("wait_remaining_seconds", 0)
                return m

            prog = _merge_p(prog_direct, prog_from_data)
            running = bool(prog.get("running", False))
            total = int(prog.get("total", 0) or 0)
            done = int(prog.get("done", 0) or 0)
            ok = int(prog.get("ok", 0) or 0)
            fail = int(prog.get("fail", 0) or 0)
            wait_msg = str(prog.get("wait_msg") or "").strip()
            wait_rem = int(prog.get("wait_remaining_seconds") or 0)

            show_numbers = False
            pct = 0.0
            progress_text = ""

            if running and total > 0:
                show_numbers = True
                pct = max(0.0, min(1.0, (done / total) if total else 0.0))
                progress_text = f"评分中：{done}/{total} 只 （成功 {ok} / 失败 {fail}）"
            elif scored_count > 0 and pool_size > 0:
                show_numbers = True
                pct = max(0.0, min(1.0, scored_count / pool_size))
                progress_text = f"已评分：{scored_count}/{pool_size} 只 （成功 {max(ok, scored_count)} / 失败 {fail}）"
            elif done > 0 and total > 0:
                show_numbers = True
                pct = max(0.0, min(1.0, done / total))
                progress_text = f"进度残留：{done}/{total} 只（可点「强制重新评分」重启）"

            if show_numbers:
                progress_placeholder.progress(pct, text=progress_text)
                base_msg = "⏳ 页面每 15 秒自动刷新，也可以随时手动点侧边栏「📥 读取缓存」看最新结果。"
                if running and wait_msg:
                    status_text.caption(
                        f"{base_msg}\n\n"
                        f"⌛ 正在等待：**{wait_msg}**，剩余约 **{wait_rem}** 秒。"
                        f"  这不是卡死，是数据源接口配额/限流等待，请耐心等待。"
                    )
                elif running:
                    status_text.caption(base_msg)
                elif scored_count >= pool_size and pool_size > 0:
                    status_text.caption("✅ 全部评分完成，数据已缓存。点击「⚡ 强制重新评分」可重新拉取。")
                else:
                    status_text.caption(
                        "ℹ️ 读取到部分缓存结果。若需要最新数据，点击侧边栏「⚡ 强制重新评分」。"
                    )
            else:
                progress_placeholder.progress(1.0, text="✅ 评分任务已就绪，点击侧边栏「⚡ 强制重新评分」开始")
    except Exception as _pe:
        try:
            progress_placeholder.progress(1.0, text="ℹ️ 进度模块异常，评分结果仍可在下方表格中查看")
            status_text.caption(f"进度读取/渲染异常：{str(_pe)[:100]}")
        except Exception:
            pass

    if _BACKEND_OK:
        _dbg_prog = sch.get_progress() or {}
        _dbg_prog_ok = int(_dbg_prog.get("ok") or 0)
        _dbg_delta = _dbg_prog_ok - scored_count
    else:
        _dbg_prog_ok = 0
        _dbg_delta = 0

    if stale_recovered:
        st.error(
            "⚠️ **检测到历史评分线程被销毁，残留进度已自动清理**\n\n"
            "Streamlit Runtime 会在长时间无交互/内存压力时销毁旧进程，"
            "导致内存中的评分结果和后台线程丢失。\n\n"
            "👉 **请立即点侧边栏 「⚡ 强制重新评分」 按钮，重新启动一轮评分**"
            "（A 股 2~3 分钟完成，美股/港股受外部限流约需 15~60 分钟补齐）。"
        )
    elif _dbg_delta > 5:
        st.warning(
            f"🔍 状态自检：进度成功数 ({_dbg_prog_ok}) 与表格条数 ({scored_count}) "
            f"相差 {_dbg_delta} 条，系统正在自动从缓存恢复，请稍等几秒或「📥 读取缓存」。"
        )

    summary = _summary_by_signal(results)
    scores = [float(r.get("total_score") or 0) for r in results if isinstance(r.get("total_score"), (int, float))]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    if scored_count > 0 or pool_size > 0 or bool(results):
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7, gap="small")
        with col1:
            st.metric(label="✅ 已评分 / 总数", value=f"{scored_count} / {pool_size}", delta=f"{'已缓存' if from_cache else '实时拉取'}")
        with col2:
            st.metric(label=SIGNAL_LABEL["BUY"], value=summary["BUY"])
        with col3:
            st.metric(label=SIGNAL_LABEL["HOLD"], value=summary["HOLD"])
        with col4:
            st.metric(label=SIGNAL_LABEL["WATCH"], value=summary["WATCH"])
        with col5:
            st.metric(label=SIGNAL_LABEL["REDUCE"], value=summary["REDUCE"])
        with col6:
            st.metric(label=SIGNAL_LABEL["AVOID"], value=summary["AVOID"])
        with col7:
            st.metric(label="📊 平均得分", value=f"{avg_score}", delta="0~100 分")

        if updated_at:
            st.caption(f"🕒 最近一次完整评分时间：{updated_at}")
        st.divider()

    if _BACKEND_OK:
        with st.expander("🔧 系统诊断（排查「不显示表格 / 进度不更新」）", expanded=False):
            debug_src = str(data.get("debug_src") or "n/a")
            st.markdown(f"**当前结果来源**：`{debug_src}`")
            import pandas as pd
            try:
                _raw = sch._inspect_caches()
            except Exception as _de:
                _raw = []
                st.warning(f"调用 _inspect_caches 失败：{str(_de)[:100]}")
            if _raw:
                _rows = []
                for _r in _raw:
                    _p = str(_r.get("path", ""))
                    for _short in (str(BASE_DIR), os.environ.get("HOME") or "/home"):
                        if _short and _p.startswith(_short):
                            _p = "..." + _p[len(_short):]
                            break
                    _row = {
                        "类型": _r.get("kind", ""),
                        "路径": _p,
                        "存在": "✅" if _r.get("exists") else "❌",
                    }
                    if _r.get("exists"):
                        _row["大小(KB)"] = round(int(_r.get("size_bytes") or 0) / 1024, 1)
                        _row["修改时间"] = _r.get("mtime", "")
                        if _r.get("kind") == "scores":
                            _row["scored_count"] = _r.get("scored_count", 0)
                            _row["pool_size"] = _r.get("pool_size", 0)
                            _row["partial?"] = "是" if _r.get("partial") else "否"
                        else:
                            _row["进度 done/total"] = f"{_r.get('progress_done', 0)}/{_r.get('progress_total', 0)}"
                            _row["ok/fail"] = f"{_r.get('progress_ok', 0)}/{_r.get('fail', 0)}"
                            _row["running?"] = "是" if _r.get("progress_running") else "否"
                    if _r.get("parse_error"):
                        _row["解析错误"] = _r["parse_error"]
                    if _r.get("stat_error"):
                        _row["stat错误"] = _r["stat_error"]
                    _rows.append(_row)
                _df = pd.DataFrame(_rows)
                st.dataframe(_df, use_container_width=True, hide_index=True,
                             column_config={"路径": st.column_config.Column("路径", width="large")})
                st.caption(
                    "💡 **看这里快速判断根因**：\n"
                    "- 所有 scores 行 scored_count=0 → 写缓存全部失败（容器文件系统权限）\n"
                    "- progress.done>0 但 scores.scored_count=0 → 线程在跑但写结果失败\n"
                    "- 多路径之间 scored_count 不一致 → 某条路径写入/读取失败，已自动取最大值\n"
                    "- 所有路径 ❌ 不存在 → 还没触发过任何评分，请点「⚡ 强制重新评分」"
                )
            st.button("🔄 立即刷新诊断（重新扫所有缓存路径）", use_container_width=False)

    if _BACKEND_OK:
        failures_list = data.get("failures") or []
        fc = len(failures_list) if isinstance(failures_list, list) else 0
        _label = "❌ 失败清单"
        if fc > 0:
            _label = f"❌ 失败清单（{fc} 只 · 含市场/代码/原因，点我展开）"
        with st.expander(_label, expanded=(fc > 25)):
            if fc == 0:
                st.success("✅ 太棒了！目前没有失败的股票（如果你刚点击开始评分，失败清单会随着评分进展逐步更新）")
            else:
                import pandas as pd
                fl = [dict(f) for f in failures_list if isinstance(f, dict)]
                for _f in fl:
                    _mk = str(_f.get("market") or "")
                    _f["市场"] = MARKET_LABEL.get(_mk, _mk)
                fdf = pd.DataFrame(fl)
                col_order = [c for c in ["市场", "code", "name", "reason", "time"] if c in fdf.columns]
                for c in ["market"]:
                    if c in fdf.columns and c not in col_order:
                        col_order.append(c)
                col_order = [c for c in col_order if c in fdf.columns]
                if col_order:
                    fdf = fdf[col_order]
                st.dataframe(
                    fdf,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "市场": st.column_config.Column("市场", width="small"),
                        "code": st.column_config.Column("代码", width="small"),
                        "name": st.column_config.Column("名称", width="medium"),
                        "reason": st.column_config.Column("失败原因（关键！）", width="large"),
                        "time": st.column_config.Column("时间", width="small"),
                    },
                    height=min(720, 120 + fc * 28),
                )
                st.markdown("**📊 失败原因分类统计**：")
                def reason_bucket(r):
                    r = str(r or "").lower()
                    if "超时" in r or "timeout" in r:
                        return "⏰ 单票超时（网络堵塞）"
                    if "429" in r or "限流" in r or "rate" in r or "频率超限" in r or "1次/分钟" in r:
                        return "🚦 接口限流(Tushare/Yahoo 429)"
                    if "返回空数据" in r or "fetch返回空" in r:
                        return "📭 返回空数据"
                    if "超" in r and "限" in r:
                        return "🚦 Tushare每日配额超限"
                    if "nan" in r or "k线" in r or "K线" in r or "score_single返回none" in r:
                        return "⚠️ K线数据异常(NaN/不足)"
                    if "异常:" in r or "exception" in r:
                        return "🔥 代码异常/未预期错误"
                    return "❔ 其他: " + (str(r)[:16] if len(r) > 16 else r)
                if "reason" in fdf.columns:
                    buckets = [reason_bucket(r) for r in fdf["reason"].tolist()]
                    from collections import Counter
                    bc = Counter(buckets)
                    bc_sorted = sorted(bc.items(), key=lambda x: x[1], reverse=True)
                    col1, col2 = st.columns(2)
                    for i, (k, v) in enumerate(bc_sorted):
                        (col1 if i % 2 == 0 else col2).info(f"{k}：**{v} 只**")
                st.caption(
                    "🔧 **常见失败对应解决办法**：\n"
                    "- 🚦 接口限流：等 30 分钟后点「强制重新评分」；或开 VPN 换出口 IP（尤其本地 Windows）\n"
                    "- ⏰ 单票超时：多是本地宽带访问海外 Yahoo 被墙/丢包，换网络或用 Streamlit Cloud 版本\n"
                    "- 📭 返回空数据：检查股票代码格式，或数据源暂时无该标的历史数据\n"
                    "- 🚦 Tushare配额超限：Tushare免费用户港股每日限 5 次，等 0 点后再跑"
                )

    if not _BACKEND_OK:
        st.error(f"⚠️ 评分引擎后端初始化失败：{_BACKEND_ERR}")
        with st.expander("💡 可能的原因 & 解决", expanded=True):
            st.markdown(
                """
                1. **缺少 Tushare token**：在 Streamlit Community Cloud 控制台 → Secrets 里添加：
                   ```toml
                   TUSHARE_TOKEN = "你的56位Token"
                   ```
                2. **依赖安装失败**：看 Build 日志里 pip install 是否报错（网络问题点 Redeploy 重试）
                3. **端口冲突**：Streamlit 自动监听 $PORT，不需要改配置
                """
            )
    elif not results:
        st.info(
            "⚠️ 还没有评分结果，请点侧边栏 **「⚡ 强制重新评分」** 按钮触发首轮评分"
            "（A股几分钟内完成，美股/港股受外部限流影响可能需要 15~90 分钟）"
        )
    else:
        if _filter_signal:
            filtered = [r for r in results if (r.get("signal") or "").upper() == _filter_signal]
            st.caption(f"🔍 过滤条件：{SIGNAL_LABEL.get(_filter_signal, _filter_signal)} （共 {len(filtered)} 只）")
        else:
            filtered = results

        import pandas as pd
        rows: List[Dict[str, Any]] = []
        for r in filtered:
            rows.append({
                "市场": MARKET_LABEL.get(str(r.get("market") or "").upper(), str(r.get("market") or "")),
                "代码": r.get("code", ""),
                "名称": r.get("name", ""),
                "环节": r.get("sector", "其他"),
                "总分": round(float(r.get("total_score") or 0), 2),
                "信号": SIGNAL_LABEL.get((r.get("signal") or "").upper(), r.get("signal", "")),
                "24h%": round(float(r.get("pct_1d") if r.get("pct_1d") is not None else (r.get("pct_change") or 0)), 2),
                "7日%": round(float(r.get("pct_7d") or 0), 2),
                "30日%": round(float(r.get("pct_30d") or 0), 2),
                "12月%": round(float(r.get("pct_1y") or 0), 2),
                "MA 得分": round(float(r.get("ma_score") or 0), 1),
                "MACD 得分": round(float(r.get("macd_score") or 0), 1),
                "RSI 得分": round(float(r.get("rsi_score") or 0), 1),
                "布林带得分": round(float(r.get("boll_score") or 0), 1),
                "量能得分": round(float(r.get("vol_score") or 0), 1),
                "KDJ 得分": round(float(r.get("kdj_score") or 0), 1),
                "signal_key": (r.get("signal") or "").upper(),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values(by=["总分"], ascending=False, inplace=True)
            df.reset_index(drop=True, inplace=True)

            def _row_color(row):
                css = SIGNAL_COLOR_CSS.get(str(row.get("signal_key", "")), "")
                return [css] * len(row)

            def _pct_color(val):
                try:
                    v = float(val or 0)
                    if v > 0:
                        return "color: #d62728; font-weight: 600;"
                    elif v < 0:
                        return "color: #2ca02c; font-weight: 600;"
                except Exception:
                    pass
                return ""

            df_display = df.drop(columns=["signal_key"]).copy()
            df_style = df_display.style.apply(_row_color, axis=1)
            df_style = df_style.map(_pct_color, subset=["24h%", "7日%", "30日%", "12月%"])

            st.dataframe(
                df_style,
                use_container_width=True,
                height=760,
                column_config={
                    "市场": st.column_config.Column("市场", width="small"),
                    "代码": st.column_config.Column("代码", width="small"),
                    "名称": st.column_config.Column("名称", width="medium"),
                    "环节": st.column_config.Column("环节", width="medium"),
                    "总分": st.column_config.NumberColumn("总分 ⭐", min_value=0, max_value=100, format="%.1f", width="small"),
                    "信号": st.column_config.Column("信号", width="small"),
                    "24h%": st.column_config.NumberColumn("24h%", format="%.2f%%", width="small"),
                    "7日%": st.column_config.NumberColumn("7日%", format="%.2f%%", width="small"),
                    "30日%": st.column_config.NumberColumn("30日%", format="%.2f%%", width="small"),
                    "12月%": st.column_config.NumberColumn("12月%", format="%.2f%%", width="small"),
                    "MA 得分": st.column_config.NumberColumn("MA", format="%.0f", width="small"),
                    "MACD 得分": st.column_config.NumberColumn("MACD", format="%.0f", width="small"),
                    "RSI 得分": st.column_config.NumberColumn("RSI", format="%.0f", width="small"),
                    "布林带得分": st.column_config.NumberColumn("BOLL", format="%.0f", width="small"),
                    "量能得分": st.column_config.NumberColumn("VOL", format="%.0f", width="small"),
                    "KDJ 得分": st.column_config.NumberColumn("KDJ", format="%.0f", width="small"),
                },
                hide_index=True,
            )

            csv_bytes = df.drop(columns=["signal_key"]).to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 下载当前结果为 CSV",
                data=csv_bytes,
                file_name=f"ai_stock_scores_{int(time.time())}.csv",
                mime="text/csv",
                use_container_width=False,
            )
        else:
            st.info(f"🔍 当前筛选下没有匹配的股票（信号：{SIGNAL_LABEL.get(_filter_signal, _filter_signal)}），尝试切到其他信号或全部。")

    # Tab1 内的自动刷新
    if _BACKEND_OK and sch:
        _auto_prog = sch.get_progress() or {}
        if _auto_prog.get("running") and int(_auto_prog.get("total", 0) or 0) > 0:
            _auto_done = int(_auto_prog.get("done", 0) or 0)
            _auto_total = int(_auto_prog.get("total", 0) or 0)
            if _auto_done < _auto_total:
                with st.spinner(f"🔄 评分进行中（{_auto_done}/{_auto_total}），15 秒后自动刷新结果..."):
                    time.sleep(15)
                st.rerun()


# ===================== Tab 2: 单股票深度分析 =====================
with tab_single:
    st.markdown(
        """
        <h1 style="margin-top:-12px;margin-bottom:0;">
            🔍 单股票深度分析 · 财报 + 技术面双维打分
        </h1>
        <p style="margin-top:6px;color:#6c757d;font-size:16px;">
            输入任意 🇨🇳 A股 / 🇭🇰 港股 / 🇺🇸 美股 代码 → 自动拉取最新财报 12 项关键指标 + 6 项技术指标
            → 0~100 综合分 → 六级评级：强烈买入 / 买入 / 持有 / 观望 / 卖出 / 强烈卖出
        </p>
        """,
        unsafe_allow_html=True,
    )

    if not _SA_OK:
        st.error(f"⚠️ 单股票分析模块初始化失败：{_SA_ERR}")
    else:
        # 输入区域
        with st.form("single_analyze_form", clear_on_submit=False):
            col_code, col_mkt, col_w = st.columns([3, 2, 2], gap="medium")
            with col_code:
                input_code = st.text_input(
                    "📝 股票代码（支持多种写法）",
                    placeholder="例如：688256、000001.SZ、AAPL、MSFT、00700、9988.HK",
                    max_chars=32,
                    help="A股：6位数字自动识别；港股：5位以内自动补零；美股：纯字母代码即可",
                )
            with col_mkt:
                input_mkt = st.selectbox(
                    "🌐 市场提示（纯数字代码有歧义时使用）",
                    options=["自动识别", "CN", "HK", "US", "KR"],
                    index=0,
                    format_func=lambda x: {"自动识别": "🤖 自动识别",
                                          "CN": "🇨🇳 A股", "HK": "🇭🇰 港股",
                                          "US": "🇺🇸 美股", "KR": "🇰🇷 韩股"}.get(x, x),
                )
            with col_w:
                style = st.select_slider(
                    "⚖️ 分析风格（财报/技术面权重）",
                    options=["价值型 70/30", "均衡型 50/50", "成长型 40/60", "激进型 30/70", "交易型 20/80"],
                    value="均衡型 50/50",
                )
            col_btn1, col_btn2 = st.columns([1, 1], gap="small")
            with col_btn1:
                submitted = st.form_submit_button("🚀 开始分析", use_container_width=True, type="primary")
            with col_btn2:
                force = st.form_submit_button("🔄 强制刷新数据（忽略缓存）", use_container_width=True)

        # 权重解析
        weight_map = {
            "价值型 70/30": {"financial": 0.70, "technical": 0.30},
            "均衡型 50/50": {"financial": 0.50, "technical": 0.50},
            "成长型 40/60": {"financial": 0.40, "technical": 0.60},
            "激进型 30/70": {"financial": 0.30, "technical": 0.70},
            "交易型 20/80": {"financial": 0.20, "technical": 0.80},
        }
        weights_used = weight_map.get(style, {"financial": 0.5, "technical": 0.5})
        hint_mkt = None if input_mkt == "自动识别" else input_mkt

        # 触发分析
        if submitted or force:
            if not input_code.strip():
                st.warning("⚠️ 请先输入股票代码再点击分析。")
            else:
                try:
                    # 给用户看正在做什么
                    with st.status(f"🔎 正在分析「{input_code.strip()}」...", expanded=True) as status_st:
                        st.write("Step 1/4：智能识别代码并规范化...")
                        yf_code, market = san.normalize_code(input_code, market_hint=hint_mkt)
                        st.write(f"→ 识别结果：`{yf_code}`（{MARKET_LABEL.get(market, market)}）")

                        st.write("Step 2/4：拉取最近 2 年日 K 线数据（Tushare 优先 + Yahoo 兜底）...")
                        price_df = fetcher.fetch_single_price(yf_code, force_refresh=force)
                        if price_df is None or len(price_df) < 60:
                            st.warning("⚠️ 价格数据不足 60 条，技术评分将以 50 分（中性）计入综合分")
                        else:
                            st.write(f"→ 价格数据：{len(price_df)} 条有效日线")

                        st.write("Step 3/4：拉取财报指标（估值/盈利/成长/健康 12 项）...")
                        fin_result = fa.score_financial(yf_code, force_refresh=force)
                        raw_cnt = sum(1 for k, v in (fin_result.get("raw") or {}).items()
                                      if not k.startswith("_") and v is not None)
                        st.write(f"→ 财报指标：成功拉取 {raw_cnt} 项")

                        st.write("Step 4/4：综合评分 + 六级评级判定...")
                        result = san.analyze_stock(input_code, market_hint=hint_mkt,
                                                    force_refresh=force, weights=weights_used)
                        status_st.update(label="✅ 分析完成", state="complete", expanded=False)

                    # 存到 session_state 避免刷新丢失
                    st.session_state["_sa_last_result"] = result
                    st.session_state["_sa_last_yf_code"] = yf_code
                except Exception as ex:
                    st.exception(ex)
                    st.error(f"分析失败：{ex}")

        # 展示上一次结果
        sa_result = st.session_state.get("_sa_last_result")
        if sa_result is None:
            st.info(
                "👆 请在上方输入股票代码并点「🚀 开始分析」。\n\n"
                "**代码格式速查**：\n"
                "- 🇨🇳 A股：`600519` / `000001.SZ` / `688256.SS`\n"
                "- 🇭🇰 港股：`700` / `00700.HK` / `9988`\n"
                "- 🇺🇸 美股：`AAPL` / `MSFT` / `NVDA` / `TSLA`\n\n"
                "说明：财报 + 技术面综合分析，首次拉取需要 3~15 秒（受网络/接口影响），之后读取缓存 < 1 秒。"
            )
        else:
            _render_single_result(sa_result)


def _render_single_result(r: Dict[str, Any]) -> None:
    """把 san.analyze_stock 的返回值渲染成 Streamlit UI"""
    import pandas as pd

    rating = r.get("rating") or {}
    level = rating.get("level", "WATCH")
    label = rating.get("label", "观望")
    emoji = rating.get("emoji", "🟡")
    color = rating.get("color", "#666")
    meaning = rating.get("meaning", "")
    css = san.get_rating_css(level) if san else {"bg": "#f3f4f6", "fg": "#111", "border": "#999"}

    # 基本信息卡
    bc = css["bg"]; fc = css["fg"]; bdc = css["border"]
    st.markdown(
        f"""
        <div style="background:{bc};border:2px solid {bdc};border-radius:16px;padding:28px 32px;margin:12px 0 24px 0;">
          <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:16px;">
            <div>
              <div style="font-size:13px;color:#666;margin-bottom:6px;">
                {r.get('market_label','')} · <code style="background:#fff;padding:1px 6px;border-radius:4px;">{r.get('yf_code','')}</code>
              </div>
              <div style="font-size:34px;font-weight:800;color:{fc};line-height:1.1;">
                {emoji} 综合评级：{label}
              </div>
              <div style="margin-top:8px;font-size:15px;color:{fc};opacity:0.9;">{meaning}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:52px;font-weight:900;color:{fc};line-height:1;">
                {r.get('total_score', 0)}
                <span style="font-size:20px;font-weight:500;opacity:0.7;">/100</span>
              </div>
              <div style="margin-top:6px;font-size:13px;color:#666;">综合得分（财报 {r['weights_used']['financial']*100:.0f}% + 技术面 {r['weights_used']['technical']*100:.0f}%）</div>
              <div style="margin-top:10px;display:flex;gap:12px;justify-content:flex-end;flex-wrap:wrap;">
                <div style="background:#fff;padding:6px 12px;border-radius:8px;border:1px solid #ddd;">
                  财报分 <b style="color:#1d4ed8;margin-left:4px;">{r.get('financial_score', 0):.1f}</b>
                </div>
                <div style="background:#fff;padding:6px 12px;border-radius:8px;border:1px solid #ddd;">
                  技术分 <b style="color:#047857;margin-left:4px;">{r.get('technical_score', 0):.1f}</b>
                </div>
                <div style="background:#fff;padding:6px 12px;border-radius:8px;border:1px solid #ddd;">
                  现价 <b style="margin-left:4px;">{r.get('price') or 'N/A'}</b>
                </div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 涨跌幅小卡片
    cols = st.columns(4)
    pct_labels = [("近 1 日", r.get("pct_1d")), ("近 7 日", r.get("pct_7d")),
                  ("近 30 日", r.get("pct_30d")), ("近 1 年", r.get("pct_1y"))]
    for (lab, val), c in zip(pct_labels, cols):
        try:
            v = float(val) if val is not None else None
            if v is None:
                c.metric(lab, "N/A")
            else:
                delta_c = "off" if v == 0 else ("normal" if v > 0 else "inverse")
                c.metric(lab, f"{v:+.2f}%", delta=None, delta_color=delta_c)
        except Exception:
            c.metric(lab, "N/A")

    # 亮点 & 风险
    hl = r.get("highlights") or []
    if hl:
        pros = [h for h in hl if h.get("type") == "pro"]
        cons = [h for h in hl if h.get("type") == "con"]
        col_p, col_c = st.columns(2, gap="large")
        with col_p:
            if pros:
                st.markdown("#### ✅ 主要看点 / 利好因素")
                for p in pros:
                    dim = p.get("dim", "")
                    txt = p.get("text", "")
                    st.success(f"**【{dim}】** {txt}")
        with col_c:
            if cons:
                st.markdown("#### ⚠️ 主要风险 / 利空因素")
                for cn in cons:
                    dim = cn.get("dim", "")
                    txt = cn.get("text", "")
                    st.error(f"**【{dim}】** {txt}")

    st.divider()

    # 财报 & 技术面 双列细项
    col_fin, col_tech = st.columns(2, gap="large")

    # 左：财报四维度
    with col_fin:
        st.subheader("📊 财报评分 · 四大维度", anchor=False)
        fin = r.get("financial") or {}
        fs_total = float(fin.get("total_score") or 0)
        st.progress(min(max(fs_total / 100.0, 0.0), 1.0),
                    text=f"财报综合分：{fs_total:.1f}/100（估值30%+盈利30%+成长20%+健康20%）")

        dim_defs = [
            ("valuation", "💹 估值（PE/PB/PS/股息率）", "#2563eb"),
            ("profitability", "💼 盈利（ROE/ROA/毛利率/净利率）", "#047857"),
            ("growth", "📈 成长（营收同比/净利润同比）", "#7c3aed"),
            ("health", "🛡️ 健康（资产负债率/流动比率）", "#b45309"),
        ]
        for key, title, col in dim_defs:
            d = fin.get(key) or {}
            s = float(d.get("score") or 0)
            with st.expander(f"{title} → **{s:.1f}/100**", expanded=True):
                # 子项得分条
                subs = d.get("sub_items") or {}
                if subs:
                    sub_rows = []
                    for kn, vs in subs.items():
                        cn_map = {"pe": "PE(TTM)", "pb": "PB", "ps": "PS(TTM)", "div": "股息率",
                                  "roe": "ROE", "roa": "ROA", "gross_margin": "毛利率", "net_margin": "净利率",
                                  "revenue": "营收同比", "earnings": "净利润同比",
                                  "debt": "资产负债率", "current": "流动比率"}
                        sub_rows.append({
                            "指标": cn_map.get(kn, kn),
                            "得分(0-100)": float(vs),
                        })
                    sdf = pd.DataFrame(sub_rows)
                    st.dataframe(sdf, use_container_width=True, hide_index=True,
                                 column_config={
                                     "得分(0-100)": st.column_config.ProgressColumn(
                                         "得分(0-100)", format="%.1f", min_value=0, max_value=100),
                                 })
                # 说明
                dts = d.get("details") or {}
                if dts:
                    st.markdown("**📝 打分依据：**")
                    for _, txt in dts.items():
                        st.caption(f"· {txt}")

        # 原始指标速览
        raw = fin.get("raw") or {}
        with st.expander("📋 财报原始指标速览（含单位说明）", expanded=False):
            def fmt(v, unit=""):
                if v is None:
                    return "未披露"
                try:
                    if isinstance(v, float):
                        return f"{v:.2f}{unit}"
                    return f"{v}{unit}"
                except Exception:
                    return str(v)
            metric_rows = [
                ("估值 · PE(TTM)", raw.get("pe_ttm"), "倍"),
                ("估值 · PB", raw.get("pb"), "倍"),
                ("估值 · PS(TTM)", raw.get("ps_ttm"), "倍"),
                ("估值 · 股息率", raw.get("div_yield"), "%"),
                ("盈利 · ROE", raw.get("roe"), "%"),
                ("盈利 · ROA", raw.get("roa"), "%"),
                ("盈利 · 毛利率", raw.get("gross_margin"), "%"),
                ("盈利 · 净利率", raw.get("net_margin"), "%"),
                ("成长 · 营收同比", raw.get("revenue_yoy"), "%"),
                ("成长 · 净利润同比", raw.get("earnings_yoy"), "%"),
                ("健康 · 资产负债率", raw.get("debt_ratio"), "%"),
                ("健康 · 流动比率", raw.get("current_ratio"), ""),
                ("市值", (raw.get("market_cap") / 1e8) if raw.get("market_cap") else None, "亿元"),
            ]
            mrdf = pd.DataFrame([{"指标": n, "数值": fmt(v, u)} for n, v, u in metric_rows])
            st.dataframe(mrdf, use_container_width=True, hide_index=True,
                         column_config={
                             "指标": st.column_config.Column("指标", width="large"),
                             "数值": st.column_config.Column("数值", width="medium"),
                         })

    # 右：技术面六维度
    with col_tech:
        st.subheader("📈 技术评分 · 六大指标", anchor=False)
        tech = r.get("technical") or {}
        ts_total = float(tech.get("total_score") or 0)
        st.progress(min(max(ts_total / 100.0, 0.0), 1.0),
                    text=f"技术综合分：{ts_total:.1f}/100（MA30%+MACD20%+RSI15%+BOLL10%+量能15%+KDJ10%）")

        tech_defs = [
            ("score_ma", "均线 MA", 30.0, tech.get("ma_score"), tech.get("ma5"), tech.get("ma10"), tech.get("ma20"), tech.get("ma60"), tech.get("price")),
            ("score_macd", "MACD", 20.0, tech.get("macd_score"), tech.get("dif_value"), tech.get("dea_value"), tech.get("macd_hist_value"), None, None),
            ("score_rsi", "RSI", 15.0, tech.get("rsi_score"), tech.get("rsi_value"), None, None, None, None),
            ("score_boll", "布林带 BOLL", 10.0, tech.get("boll_score"), tech.get("bb_upper"), tech.get("bb_mid"), tech.get("bb_lower"), None, tech.get("price")),
            ("score_volume", "量能 VOL", 15.0, tech.get("vol_score"), tech.get("vol_ratio_value"), tech.get("volume_last"), None, None, None),
            ("score_kdj", "KDJ", 10.0, tech.get("kdj_score"), tech.get("k_value"), tech.get("d_value"), tech.get("j_value"), None, None),
        ]
        rows_t = []
        for name_cn, title, weight, raw_s, *rest in tech_defs:
            try:
                s = float(raw_s) if raw_s is not None else None
            except Exception:
                s = None
            extra = []
            if title == "均线 MA" and rest[0] is not None:
                extra.append(f"MA5={rest[0]:.3f}" if rest[0] else "")
                extra.append(f"MA10={rest[1]:.3f}" if rest[1] else "")
                extra.append(f"MA20={rest[2]:.3f}" if rest[2] else "")
                extra.append(f"MA60={rest[3]:.3f}" if rest[3] else "")
                extra.append(f"价={rest[4]:.3f}" if rest[4] else "")
            elif title == "MACD":
                extra.append(f"DIF={rest[0]:.4f}" if rest[0] is not None else "")
                extra.append(f"DEA={rest[1]:.4f}" if rest[1] is not None else "")
                extra.append(f"HIST={rest[2]:.4f}" if rest[2] is not None else "")
            elif title == "RSI":
                extra.append(f"RSI(14)={rest[0]:.2f}" if rest[0] is not None else "")
            elif title == "布林带 BOLL":
                extra.append(f"UP={rest[0]:.3f}" if rest[0] is not None else "")
                extra.append(f"MID={rest[1]:.3f}" if rest[1] is not None else "")
                extra.append(f"LOW={rest[2]:.3f}" if rest[2] is not None else "")
                extra.append(f"价={rest[4]:.3f}" if len(rest) > 4 and rest[4] is not None else "")
            elif title == "量能 VOL":
                extra.append(f"量比={rest[0]:.2f}" if rest[0] is not None else "")
            elif title == "KDJ":
                extra.append(f"K={rest[0]:.2f}" if rest[0] is not None else "")
                extra.append(f"D={rest[1]:.2f}" if rest[1] is not None else "")
                extra.append(f"J={rest[2]:.2f}" if rest[2] is not None else "")
            extra_txt = "  ".join([e for e in extra if e])
            rows_t.append({
                "指标": f"{title}（权重{weight:.0f}%）",
                "加权得分": round(s * weight / 100.0, 2) if s is not None else 0.0,
                "子打分(0-100)": s if s is not None else 50.0,
                "关键数值": extra_txt or "—",
            })
        tdf = pd.DataFrame(rows_t)
        st.dataframe(
            tdf,
            use_container_width=True,
            hide_index=True,
            height=380,
            column_config={
                "子打分(0-100)": st.column_config.ProgressColumn(
                    "子打分(0-100)", format="%.1f", min_value=0, max_value=100),
                "加权得分": st.column_config.NumberColumn("加权得分", format="%.2f"),
                "关键数值": st.column_config.Column("关键数值", width="large"),
            },
        )

        # 技术面原始信号
        tech_sig = tech.get("signal") or ""
        tech_label = SIGNAL_LABEL.get(tech_sig.upper(), tech_sig)
        st.info(f"技术面独立信号判定：**{tech_label}**（0~100 分换算：≥80买入 / ≥65持有 / ≥45观望 / ≥30减仓 / <30回避）")

    st.divider()

    # 综合结论文字
    st.subheader("💡 综合结论摘要", anchor=False)
    summary = r.get("summary") or ""
    for line in summary.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("⚠️") or "免责" in line:
            st.caption(line)
        else:
            st.markdown(f"<div style='font-size:16px;line-height:1.7;'>{line}</div>", unsafe_allow_html=True)


# =============================================================================
# 公共页脚
# =============================================================================
st.divider()
c_left, c_right = st.columns([2, 1], gap="large")
with c_left:
    st.markdown(
        """
        <div style="color:#6c757d;font-size:14px;line-height:1.6;">
          <p style="font-weight:600;margin-bottom:8px;color:#212529;">📜 免责声明</p>
          <p style="margin:0 0 6px 0;">
            本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标、股票池等）
            <b>仅供研究和学习使用，不构成任何投资建议或承诺</b>。
          </p>
          <p style="margin:0;">
            市场有风险，投资需谨慎。任何基于本系统进行的实盘交易行为，盈亏自负，
            作者及版权方不承担任何法律责任。
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c_right:
    st.markdown(
        """
        <div style="color:#6c757d;font-size:14px;line-height:1.6;text-align:right;">
          <p style="font-weight:600;margin-bottom:8px;color:#212529;">© 版权信息</p>
          <p style="margin:0 0 6px 0;">&copy; 2025 <b>Bart</b><br>All rights reserved.</p>
          <p style="margin:0;">
            📧 联系方式：<a href="mailto:yanying76@gmail.com">yanying76@gmail.com</a>
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

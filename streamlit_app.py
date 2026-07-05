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
            # TOML 顶层还可以嵌套 [section]，例如 [tushare] token = "xxx"
            # 这种情况下 dict(st.secrets["tushare"]) 会返回子字典，递归展开
            elif isinstance(_v, dict):
                for _sk, _sv in _v.items():
                    if isinstance(_sv, (str, int, float, bool)):
                        os.environ[str(_sk).upper()] = str(_sv).strip()
except Exception:
    pass

# 再兜底 HOME / TZ（Streamlit 容器默认 HOME=/app，可写）
os.environ["HOME"] = os.environ.get("HOME") or "/app"
os.environ["TZ"] = os.environ.get("TZ") or "Asia/Shanghai"

# -----------------------------------------------------------------------------
# 1. 导入后端评分引擎（scoring_scheduler）
#    scoring_scheduler 内部会自动 import data_fetcher_v2 / scoring_engine 等
# -----------------------------------------------------------------------------
try:
    import scoring_scheduler as sch
    import data_fetcher_v2 as fetcher  # noqa: F401 （触发 Tushare 初始化）
    _BACKEND_OK = True
    _BACKEND_ERR = ""
except Exception as e:  # pragma: no cover - 部署时出错给用户看
    _BACKEND_OK = False
    _BACKEND_ERR = str(e)
    sch = None

# -----------------------------------------------------------------------------
# 2. 常量：信号映射（与 scoring_engine.score_single 返回的 signal 对应）
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

# -----------------------------------------------------------------------------
def _fetch_scores() -> Dict[str, Any]:
    """
    页面主读路径：直接读 scoring_scheduler 维护的双重缓存（内存 + 磁盘）。

    scoring_scheduler 已经实现了【实时增量更新】：
      - _flush_partial() 每完成 1 只股票就立即 ① 写磁盘 pickle ② 更新内存 _last_result
      - get_current_result() 先读内存（毫秒级），再兜底读磁盘缓存（跨进程/跨刷新也能拿到最新）
    所以这里**绝对不能**再加一层 @st.cache_data！之前套 @st.cache_data(ttl=6h) 是致命重复缓存：
      ① 「📥 读取缓存」按钮没更新 force_hash → cache_data 一直返回 6h 前的「早期空快照」
      ② 即使用户后台线程跑到 126/157，页面也读不到新结果，用户误以为「要等全跑完才显示」
    """
    if not _BACKEND_OK:
        return {"results": [], "pool_size": 0, "scored_count": 0, "updated_at": "", "from_cache": False}
    data = sch.get_current_result() or {}
    # KPI 卡片 delta 需要 from_cache 字段（默认 True，因为读的都是 scoring_scheduler 的缓存）
    data.setdefault("from_cache", True)
    return data


def _summary_by_signal(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """统计各信号的数量"""
    cnt = {k: 0 for k in SIGNAL_ORDER}
    for r in results or []:
        sig = (r.get("signal") or "WATCH").upper()
        if sig in cnt:
            cnt[sig] += 1
    return cnt


def _apply_signal_style(df_row):
    """dataframe 的 style apply：按 signal 列给整行染色"""
    sig = str(df_row.get("signal", "") or "").upper()
    css = SIGNAL_COLOR_CSS.get(sig, "")
    return [css] * len(df_row)


# -----------------------------------------------------------------------------
# 4. 侧边栏（刷新控制 + 信号筛选 + 添加/删除股票）
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🛠️ 控制面板")

    st.subheader("🔄 刷新评分")
    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button("📥 读取缓存", use_container_width=True, type="secondary"):
            # 关键修复：清除所有 st.cache_data 旧快照，避免拿到早期空结果
            try: st.cache_data.clear()
            except Exception: pass
            # 同步更新 force_hash，触发任何残留的缓存 key 失效
            st.session_state["__force_hash__"] = f"v{int(time.time())}"
            st.success("✅ 已读取缓存中最新结果（出了多少只就显示多少只）")
            st.rerun()
    with c2:
        if st.button("⚡ 强制重新评分", use_container_width=True, type="primary"):
            if _BACKEND_OK:
                # 清除历史旧快照缓存，防止显示空结果
                try: st.cache_data.clear()
                except Exception: pass
                # 开启后台线程评分，不阻塞页面
                resp = sch.run_scoring(force_refresh=True, use_thread=True)
                st.session_state["__force_hash__"] = f"v{int(time.time())}"
                status = resp.get("status")
                if status in ("scheduled", "running"):
                    st.info("✅ 评分任务已在后台启动，进度会在页面顶部实时刷新")
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
    # 反推到内部 signal key
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
                st.error("后端不可用，暂时无法添加")

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
    st.caption("💡 Streamlit Community Cloud（免费）版本：数据拉取和评分在云端执行，Yahoo Finance 限流/港股 Tushare 1次/分钟 限制依旧存在，美股/港股会在几分钟~几十分钟内陆续补齐评分。")

# -----------------------------------------------------------------------------
# 5. 页面主体（顶部进度 → KPI 卡片 → 股票表格）
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 5.1 先读一次评分结果（用于：进度块合并 progress、后面 KPI 和表格共享）
#     必须放在进度条渲染之前，保证进度块里能拿到 scored_count / pool_size / data.progress
# -----------------------------------------------------------------------------
data = _fetch_scores() or {}
results: List[Dict[str, Any]] = data.get("results") or []
pool_size = int(data.get("pool_size", 0) or 0)
scored_count = int(data.get("scored_count", 0) or 0)
updated_at = str(data.get("updated_at") or "")
from_cache = bool(data.get("from_cache", False))
stale_recovered = bool(data.get("stale_recovered", False))

# -----------------------------------------------------------------------------
# 5.2 进度条 + 运行状态
# -----------------------------------------------------------------------------
progress_placeholder = st.empty()
status_text = st.empty()

try:
    if _BACKEND_OK:
        # 合并两处进度源：直接 get_progress() + 评分结果里带的 progress；取信息更丰富的那份
        prog_direct = sch.get_progress() if sch else {}
        prog_from_data = data.get("progress", {}) if isinstance(data, dict) else {}

        def _merge_p(a, b):
            """取 total/ok/done 值更大、running 更真、有 wait_msg 的那份"""
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

        # --- 显示条件放宽：评分中(running) 或 有缓存结果(scored_count) 都显示进度数字 ---
        show_numbers = False
        pct = 0.0
        progress_text = ""

        if running and total > 0:
            # Case A：评分线程正在跑 → 进度百分比 + 数字实时显示
            show_numbers = True
            pct = max(0.0, min(1.0, (done / total) if total else 0.0))
            progress_text = f"评分中：{done}/{total} 只 （成功 {ok} / 失败 {fail}）"
        elif scored_count > 0 and pool_size > 0:
            # Case B：评分未在跑，但已有缓存结果（可能刚结束、或在其他 worker 上跑）→ 显示已评分进度
            show_numbers = True
            pct = max(0.0, min(1.0, scored_count / pool_size))
            progress_text = f"已评分：{scored_count}/{pool_size} 只 （成功 {max(ok, scored_count)} / 失败 {fail}）"
        elif done > 0 and total > 0:
            # Case C：线程未标记 running 但磁盘里存了部分 done（典型：worker 被杀后残留进度）→ 也显示出来避免"数字完全不出现"
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
    # 进度条渲染绝不阻塞主页面：出错时只显示一个安全的兜底占位
    try:
        progress_placeholder.progress(1.0, text="ℹ️ 进度模块异常，评分结果仍可在下方表格中查看")
        status_text.caption(f"进度读取/渲染异常：{str(_pe)[:100]}")
    except Exception:
        pass

# -----------------------------------------------------------------------------
# 5.3 诊断告警：stale_recovered / 进度-结果差异过大
# -----------------------------------------------------------------------------

# ---- 诊断：进度 vs 结果不一致时，给用户明确提示 ----
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

# 只有当有评分结果（哪怕只是部分）时才显示 KPI 卡片，避免 7 个全 0/0 空卡片
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

# ===== 诊断面板（默认折叠）：展示所有缓存路径的真实状态，快速定位写入/读取问题 =====
if _BACKEND_OK:
    with st.expander("🔧 系统诊断（排查「不显示表格 / 进度不更新」）", expanded=False):
        debug_src = str(data.get("debug_src") or "n/a")
        st.markdown(f"**当前结果来源**：`{debug_src}`  （disk=从磁盘缓存读到最新；mem=只读到内存；empty=两者都空）")
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
                # 缩短路径展示
                for _short in (str(_BASE_DIR), os.environ.get("HOME") or "/home"):
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

# -----------------------------------------------------------------------------
# 失败清单展示（所有评分未成功的股票，按失败原因分组，显示给用户）
# -----------------------------------------------------------------------------
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
            # 美化输出：市场标签替换
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
            # 失败原因分类统计
            st.markdown("**📊 失败原因分类统计**（帮你快速判断根因）：")
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
                "- 🚦 接口限流(Tushare/Yahoo)：等 30 分钟后点「强制重新评分」；或开 VPN 换出口 IP（尤其本地 Windows）\n"
                "- ⏰ 单票超时：多是本地宽带访问海外 Yahoo 被墙/丢包，换网络、开全局代理，或直接用 Streamlit Cloud 版本更稳定\n"
                "- 📭 返回空数据：检查股票代码映射（尤其韩股代码格式），或数据源暂时无该标的历史数据\n"
                "- 🚦 Tushare配额超限：Tushare免费用户港股每日限 5 次，等 0 点后再跑；或付费升级额度"
            )

# -----------------------------------------------------------------------------
# 5.3 信号筛选 + 表格展示
# -----------------------------------------------------------------------------
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
    # 过滤信号
    if _filter_signal:
        filtered = [r for r in results if (r.get("signal") or "").upper() == _filter_signal]
        st.caption(f"🔍 过滤条件：{SIGNAL_LABEL.get(_filter_signal, _filter_signal)} （共 {len(filtered)} 只）")
    else:
        filtered = results

    # 转 DataFrame，显示更清晰
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
            "涨跌幅%": round(float(r.get("pct_change") or 0), 2),
            "MA 得分": round(float(r.get("ma_score") or 0), 1),
            "MACD 得分": round(float(r.get("macd_score") or 0), 1),
            "RSI 得分": round(float(r.get("rsi_score") or 0), 1),
            "布林带得分": round(float(r.get("boll_score") or 0), 1),
            "量能得分": round(float(r.get("vol_score") or 0), 1),
            "KDJ 得分": round(float(r.get("kdj_score") or 0), 1),
            "signal_key": (r.get("signal") or "").upper(),  # 辅助列，用于染色
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(by=["总分"], ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)

        # DataFrame style：按 signal_key 给整行染色 + 涨跌幅红涨绿跌
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
        df_style = df_style.map(_pct_color, subset=["涨跌幅%"])

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
                "涨跌幅%": st.column_config.NumberColumn("涨跌%", format="%.2f%%", width="small"),
                "MA 得分": st.column_config.NumberColumn("MA", format="%.0f", width="small"),
                "MACD 得分": st.column_config.NumberColumn("MACD", format="%.0f", width="small"),
                "RSI 得分": st.column_config.NumberColumn("RSI", format="%.0f", width="small"),
                "布林带得分": st.column_config.NumberColumn("BOLL", format="%.0f", width="small"),
                "量能得分": st.column_config.NumberColumn("VOL", format="%.0f", width="small"),
                "KDJ 得分": st.column_config.NumberColumn("KDJ", format="%.0f", width="small"),
            },
            hide_index=True,
        )

        # 下载 CSV 按钮（给用户导出 Excel 用）
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

# =============================================================================
# 页脚：免责声明 + 版权 + 联系方式（固定在页面最底部，每次 rerun 都会渲染）
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

# -----------------------------------------------------------------------------
# 6. 自动刷新：评分任务进行中时，每 15 秒自动刷新一次页面
#    （页面渲染完成后才 sleep，所以用户 15 秒内可正常交互，到期后自动拉取增量结果）
# -----------------------------------------------------------------------------
if _BACKEND_OK and sch:
    _auto_prog = sch.get_progress() or {}
    if _auto_prog.get("running") and int(_auto_prog.get("total", 0) or 0) > 0:
        _auto_done = int(_auto_prog.get("done", 0) or 0)
        _auto_total = int(_auto_prog.get("total", 0) or 0)
        if _auto_done < _auto_total:
            with st.spinner(f"🔄 评分进行中（{_auto_done}/{_auto_total}），15 秒后自动刷新结果..."):
                time.sleep(15)
            st.rerun()

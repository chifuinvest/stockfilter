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
# 5.1 进度条 + 运行状态
# -----------------------------------------------------------------------------
progress_placeholder = st.empty()
status_text = st.empty()

if _BACKEND_OK:
    prog = sch.get_progress() or {}
    running = prog.get("running", False)
    total = int(prog.get("total", 0) or 0)
    done = int(prog.get("done", 0) or 0)
    ok = int(prog.get("ok", 0) or 0)
    fail = int(prog.get("fail", 0) or 0)

    if running and total > 0:
        pct = max(0.0, min(1.0, (done / total) if total else 0.0))
        progress_placeholder.progress(pct, text=f"评分中：{done}/{total} 只 （成功 {ok} / 失败 {fail}）")
        wait_msg = str(prog.get("wait_msg") or "").strip()
        wait_rem = int(prog.get("wait_remaining_seconds") or 0)
        base_msg = "⏳ 评分任务进行中，稍后页面自动会刷新，也可以手动点侧边栏「📥 读取缓存」看最新结果。"
        if wait_msg:
            status_text.caption(
                f"{base_msg}\n\n"
                f"⌛ 正在等待：**{wait_msg}**，剩余约 **{wait_rem}** 秒。"
                f"  *这不是卡死，是接口配额/限流等待，请耐心等待。*"
            )
        else:
            status_text.caption(base_msg)
    else:
        progress_placeholder.progress(1.0, text="✅ 评分任务已就绪（读缓存）")

# -----------------------------------------------------------------------------
# 5.2 读取评分结果 + KPI 卡片
# -----------------------------------------------------------------------------
data = _fetch_scores() or {}
results: List[Dict[str, Any]] = data.get("results") or []
pool_size = int(data.get("pool_size", 0) or 0)
scored_count = int(data.get("scored_count", 0) or 0)
updated_at = str(data.get("updated_at") or "")
from_cache = bool(data.get("from_cache", False))

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

        # DataFrame style：按 signal_key 给整行染色（Streamlit 1.30+ 支持 Styler）
        def _row_color(row):
            css = SIGNAL_COLOR_CSS.get(str(row.get("signal_key", "")), "")
            return [css] * len(row)

        styled = df.drop(columns=["signal_key"]).style.apply(_row_color, axis=1)

        st.dataframe(
            styled,
            use_container_width=True,
            height=900,
            column_config={
                "市场": st.column_config.Column("市场", width="small"),
                "代码": st.column_config.Column("代码", width="medium"),
                "名称": st.column_config.Column("名称", width="medium"),
                "环节": st.column_config.Column("环节", width="medium"),
                "总分": st.column_config.NumberColumn("总分 ⭐", min_value=0, max_value=100, format="%.2f", width="small"),
                "信号": st.column_config.Column("信号", width="small"),
                "涨跌幅%": st.column_config.NumberColumn("涨跌%", format="%.2f%%", width="small"),
                "MA 得分": st.column_config.NumberColumn("MA", format="%.1f", width="small"),
                "MACD 得分": st.column_config.NumberColumn("MACD", format="%.1f", width="small"),
                "RSI 得分": st.column_config.NumberColumn("RSI", format="%.1f", width="small"),
                "布林带得分": st.column_config.NumberColumn("BOLL", format="%.1f", width="small"),
                "量能得分": st.column_config.NumberColumn("VOL", format="%.1f", width="small"),
                "KDJ 得分": st.column_config.NumberColumn("KDJ", format="%.1f", width="small"),
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

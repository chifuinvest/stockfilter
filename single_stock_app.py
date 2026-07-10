# -*- coding: utf-8 -*-
r"""
========================================
 🔍 独立页面 · 单股票深度分析
----------------------------------------
 · 完全独立，不依赖原监控页面 (streamlit_app.py)
 · 只做一件事：输入代码 → 输出财报+技术面综合分析与六级评级
 · 适用于：🇨🇳A股 / 🇭🇰港股 / 🇺🇸美股

 启动命令：
   .venv\Scripts\python.exe -m streamlit run single_stock_app.py \
       --server.port 8502 --server.address 127.0.0.1 --server.headless true
========================================
"""
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
import streamlit as st

try:
    import stock_analyzer as san
    _SA_OK = True
    _SA_ERR = None
except Exception as e:
    _SA_OK = False
    _SA_ERR = e

# ------------------------------------------------------------------
# 常量（从原页面独立复制，不依赖原文件）
# ------------------------------------------------------------------
SIGNAL_LABEL: Dict[str, str] = {
    "BUY":    "🟢 买入",
    "HOLD":   "🔵 持有",
    "WATCH":  "🟡 观望",
    "REDUCE": "🟠 减仓",
    "AVOID":  "🔴 回避",
}

MARKET_LABEL: Dict[str, str] = {
    "US": "🇺🇸 美股",
    "CN": "🇨🇳 A股",
    "HK": "🇭🇰 港股",
    "KR": "🇰🇷 韩股",
}

DEFAULT_WEIGHTS_HELP = {
    "financial": 50,
    "technical": 50,
}


# ==================================================================
# 渲染函数：把 san.analyze_stock 返回值变成 UI
# ==================================================================
def render_result(r: Dict[str, Any]) -> None:
    rating = r.get("rating") or {}
    level = rating.get("level", "WATCH")
    label = rating.get("label", "观望")
    emoji = rating.get("emoji", "🟡")
    color = rating.get("color", "#666")
    meaning = rating.get("meaning", "")
    try:
        css = san.get_rating_css(level) if _SA_OK else {"bg": "#f3f4f6", "fg": "#111", "border": "#999"}
    except Exception:
        css = {"bg": "#f3f4f6", "fg": "#111", "border": "#999"}

    bc = css.get("bg", "#f3f4f6")
    fc = css.get("fg", "#111")
    bdc = css.get("border", "#999")

    # ---- 综合评级大卡 ----
    w = r.get("weights_used") or {"financial": 0.5, "technical": 0.5}
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
              <div style="margin-top:6px;font-size:13px;color:#666;">
                综合得分（财报 {w.get('financial',0)*100:.0f}% + 技术面 {w.get('technical',0)*100:.0f}%）
              </div>
              <div style="margin-top:10px;display:flex;gap:12px;justify-content:flex-end;flex-wrap:wrap;">
                <div style="background:#fff;padding:6px 12px;border-radius:8px;border:1px solid #ddd;">
                  财报分 <b style="color:#1d4ed8;margin-left:4px;">{float(r.get('financial_score', 0) or 0):.1f}</b>
                </div>
                <div style="background:#fff;padding:6px 12px;border-radius:8px;border:1px solid #ddd;">
                  技术分 <b style="color:#047857;margin-left:4px;">{float(r.get('technical_score', 0) or 0):.1f}</b>
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

    # ---- 涨跌幅四卡 ----
    cols = st.columns(4)
    pct_labels = [("近 1 日", r.get("pct_1d")), ("近 7 日", r.get("pct_7d")),
                  ("近 30 日", r.get("pct_30d")), ("近 1 年", r.get("pct_1y"))]
    for (lab, val), c in zip(pct_labels, cols):
        try:
            v = float(val) if val is not None else None
            if v is None:
                c.metric(lab, "N/A")
            else:
                dc = "off" if abs(v) < 1e-9 else ("normal" if v > 0 else "inverse")
                c.metric(lab, f"{v:+.2f}%", delta=None, delta_color=dc)
        except Exception:
            c.metric(lab, "N/A")

    # ---- 亮点 & 风险 ----
    hl = r.get("highlights") or []
    if hl:
        pros = [h for h in hl if isinstance(h, dict) and h.get("type") == "pro"]
        cons = [h for h in hl if isinstance(h, dict) and h.get("type") == "con"]
        if pros or cons:
            col_p, col_c = st.columns(2, gap="large")
            with col_p:
                if pros:
                    st.markdown("#### ✅ 主要看点 / 利好因素")
                    for p in pros:
                        st.success(f"**【{p.get('dim','')}】** {p.get('text','')}")
            with col_c:
                if cons:
                    st.markdown("#### ⚠️ 主要风险 / 利空因素")
                    for cn in cons:
                        st.error(f"**【{cn.get('dim','')}】** {cn.get('text','')}")

    st.divider()

    # ---- 左：财报 · 右：技术面 ----
    col_fin, col_tech = st.columns(2, gap="large")

    with col_fin:
        st.subheader("📊 财报评分 · 四大维度", anchor=False)
        fin = r.get("financial") or {}
        fs_total = float(fin.get("total_score") or 0)
        st.progress(min(max(fs_total / 100.0, 0.0), 1.0),
                    text=f"财报综合分：{fs_total:.1f}/100（估值30%+盈利30%+成长20%+健康20%）")

        dim_defs = [
            ("valuation",     "💹 估值（PE/PB/PS/股息率）",      "#2563eb"),
            ("profitability", "💼 盈利（ROE/ROA/毛利率/净利率）",  "#047857"),
            ("growth",        "📈 成长（营收同比/净利润同比）",    "#7c3aed"),
            ("health",        "🛡️ 健康（资产负债率/流动比率）",    "#b45309"),
        ]
        for key, title, _col in dim_defs:
            d = fin.get(key) or {}
            s = float(d.get("score") or 0)
            with st.expander(f"{title} → **{s:.1f}/100**", expanded=True):
                subs = d.get("sub_items") or {}
                if subs:
                    cn_map = {
                        "pe": "PE(TTM)", "pb": "PB", "ps": "PS(TTM)", "div": "股息率",
                        "roe": "ROE", "roa": "ROA", "gross_margin": "毛利率", "net_margin": "净利率",
                        "revenue": "营收同比", "earnings": "净利润同比",
                        "debt": "资产负债率", "current": "流动比率",
                    }
                    rows = []
                    for kn, vs in subs.items():
                        try:
                            score = float(vs)
                        except Exception:
                            score = 50.0
                        rows.append({"指标": cn_map.get(kn, kn), "得分(0-100)": score})
                    if rows:
                        sdf = pd.DataFrame(rows)
                        st.dataframe(sdf, use_container_width=True, hide_index=True,
                                     column_config={
                                         "得分(0-100)": st.column_config.ProgressColumn(
                                             "得分(0-100)", format="%.1f", min_value=0, max_value=100)
                                     })
                dts = d.get("details") or {}
                if dts:
                    st.markdown("**📝 打分依据：**")
                    for _, txt in dts.items():
                        st.caption(f"· {txt}")

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
            cap = raw.get("market_cap")
            cap_str = f"{(cap / 1e8):.2f}亿元" if cap else "未披露"
            metric_rows = [
                ("估值 · PE(TTM)",      fmt(raw.get("pe_ttm"),      "倍")),
                ("估值 · PB",           fmt(raw.get("pb"),          "倍")),
                ("估值 · PS(TTM)",      fmt(raw.get("ps_ttm"),      "倍")),
                ("估值 · 股息率",       fmt(raw.get("div_yield"),   "%")),
                ("盈利 · ROE",          fmt(raw.get("roe"),         "%")),
                ("盈利 · ROA",          fmt(raw.get("roa"),         "%")),
                ("盈利 · 毛利率",       fmt(raw.get("gross_margin"),"%")),
                ("盈利 · 净利率",       fmt(raw.get("net_margin"),  "%")),
                ("成长 · 营收同比",     fmt(raw.get("revenue_yoy"), "%")),
                ("成长 · 净利润同比",   fmt(raw.get("earnings_yoy"),"%")),
                ("健康 · 资产负债率",   fmt(raw.get("debt_ratio"),  "%")),
                ("健康 · 流动比率",     fmt(raw.get("current_ratio"), "")),
                ("市值",                cap_str),
            ]
            mrdf = pd.DataFrame([{"指标": n, "数值": v} for n, v in metric_rows])
            st.dataframe(mrdf, use_container_width=True, hide_index=True,
                         column_config={
                             "指标": st.column_config.Column("指标", width="large"),
                             "数值": st.column_config.Column("数值", width="medium"),
                         })

    with col_tech:
        st.subheader("📈 技术评分 · 六大指标", anchor=False)
        tech = r.get("technical") or {}
        ts_total = float(tech.get("total_score") or 0)
        st.progress(min(max(ts_total / 100.0, 0.0), 1.0),
                    text=f"技术综合分：{ts_total:.1f}/100（MA30%+MACD20%+RSI15%+BOLL10%+量能15%+KDJ10%）")

        tech_defs = [
            ("score_ma",     "均线 MA",  30.0, tech.get("score_ma"),    tech.get("ma5"),    tech.get("ma10"),   tech.get("ma20"),   tech.get("ma60"),   tech.get("price")),
            ("score_macd",   "MACD",     20.0, tech.get("score_macd"),  tech.get("dif_value"), tech.get("dea_value"), tech.get("macd_hist_value"), None, None),
            ("score_rsi",    "RSI",      15.0, tech.get("score_rsi"),   tech.get("rsi_value"), None, None, None, None),
            ("score_boll",   "布林带 BOLL", 10.0, tech.get("score_boll"), tech.get("bb_upper"), tech.get("bb_mid"), tech.get("bb_lower"), None, tech.get("price")),
            ("score_volume", "量能 VOL", 15.0, tech.get("score_volume"),tech.get("vol_ratio_value"), tech.get("volume_last"), None, None, None),
            ("score_kdj",    "KDJ",      10.0, tech.get("score_kdj"),   tech.get("k_value"), tech.get("d_value"), tech.get("j_value"), None, None),
        ]
        rows_t = []
        for _name_cn, title, weight, raw_s, *rest in tech_defs:
            try:
                s = float(raw_s) if raw_s is not None else None
            except Exception:
                s = None
            extra = []
            if title == "均线 MA":
                for lab, idx in [("MA5", 0), ("MA10", 1), ("MA20", 2), ("MA60", 3), ("价", 4)]:
                    if len(rest) > idx and rest[idx] is not None:
                        try:
                            extra.append(f"{lab}={float(rest[idx]):.3f}")
                        except Exception:
                            pass
            elif title == "MACD":
                for lab, idx, fmt_s in [("DIF", 0, ".4f"), ("DEA", 1, ".4f"), ("HIST", 2, ".4f")]:
                    if len(rest) > idx and rest[idx] is not None:
                        try:
                            extra.append(f"{lab}={float(rest[idx]):{fmt_s}}")
                        except Exception:
                            pass
            elif title == "RSI" and len(rest) > 0 and rest[0] is not None:
                try:
                    extra.append(f"RSI(14)={float(rest[0]):.2f}")
                except Exception:
                    pass
            elif title == "布林带 BOLL":
                for lab, idx, fmt_s in [("UP", 0, ".3f"), ("MID", 1, ".3f"), ("LOW", 2, ".3f")]:
                    if len(rest) > idx and rest[idx] is not None:
                        try:
                            extra.append(f"{lab}={float(rest[idx]):{fmt_s}}")
                        except Exception:
                            pass
                if len(rest) > 4 and rest[4] is not None:
                    try:
                        extra.append(f"价={float(rest[4]):.3f}")
                    except Exception:
                        pass
            elif title == "量能 VOL" and len(rest) > 0 and rest[0] is not None:
                try:
                    extra.append(f"量比={float(rest[0]):.2f}")
                except Exception:
                    pass
            elif title == "KDJ":
                for lab, idx, fmt_s in [("K", 0, ".2f"), ("D", 1, ".2f"), ("J", 2, ".2f")]:
                    if len(rest) > idx and rest[idx] is not None:
                        try:
                            extra.append(f"{lab}={float(rest[idx]):{fmt_s}}")
                        except Exception:
                            pass
            extra_txt = "  ".join([e for e in extra if e])
            s_val = s if s is not None else 50.0
            w_score = round(s_val * weight / 100.0, 2)
            rows_t.append({
                "指标": f"{title}（权重{weight:.0f}%）",
                "加权得分": w_score,
                "子打分(0-100)": s_val,
                "关键数值": extra_txt or "—",
            })
        if rows_t:
            tdf = pd.DataFrame(rows_t)
            st.dataframe(
                tdf, use_container_width=True, hide_index=True, height=380,
                column_config={
                    "子打分(0-100)": st.column_config.ProgressColumn(
                        "子打分(0-100)", format="%.1f", min_value=0, max_value=100),
                    "加权得分": st.column_config.NumberColumn("加权得分", format="%.2f"),
                    "关键数值": st.column_config.Column("关键数值", width="large"),
                },
            )

        tech_sig = (tech.get("signal") or "").upper()
        tech_label = SIGNAL_LABEL.get(tech_sig, tech_sig or "—")
        st.info(f"技术面独立信号判定：**{tech_label}**（0~100 分换算：≥80买入 / ≥65持有 / ≥45观望 / ≥30减仓 / <30回避）")

    st.divider()

    # ---- 综合结论摘要 ----
    st.subheader("💡 综合结论摘要", anchor=False)
    summary = r.get("summary") or ""
    for line in summary.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("⚠️") or "免责" in line:
            st.caption(line)
        else:
            st.markdown(
                f"<div style='font-size:16px;line-height:1.7;'>{line}</div>",
                unsafe_allow_html=True,
            )


# ==================================================================
# 页面入口
# ==================================================================
st.set_page_config(
    page_title="🔍 单股票深度分析 · 财报+技术面",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="auto",
)

st.title("🔍 单股票深度分析 · 财报 + 技术面综合打分")
st.caption(
    "独立页面 · 适用于 🇨🇳 A股 / 🇭🇰 港股 / 🇺🇸 美股 · "
    "输出：估值/盈利/成长/健康 4 大财报维度 + MA/MACD/RSI/BOLL/VOL/KDJ 6 大技术维度 + 六级评级结论"
)

if not _SA_OK:
    st.error("❌ 核心模块 stock_analyzer 导入失败，请检查环境。")
    with st.expander("📌 错误详情", expanded=True):
        st.exception(_SA_ERR)
    st.stop()

with st.sidebar:
    st.header("⚙️ 分析参数", divider=True)
    fin_w = st.slider("财报权重 %", min_value=0, max_value=100,
                      value=DEFAULT_WEIGHTS_HELP["financial"], step=5)
    tech_w = 100 - fin_w
    st.markdown(f"技术面权重：**{tech_w}%**")
    force = st.checkbox("🔄 强制刷新（忽略本地缓存）", value=True,
                        help="⚠️ 默认已勾选：确保你看到的是最新真实财报数据；取消勾选可使用本地12小时缓存提速。")
    st.divider()
    st.markdown(
        "#### 📖 输入代码示例\n"
        "- A股：`600519.SS` / `000001.SZ` / `688256`\n"
        "- 港股：`00700.HK` / `09988.HK` / `700`\n"
        "- 美股：`AAPL` / `NVDA` / `TSLA`\n"
    )

with st.container():
    st.subheader("① 输入股票代码", divider=True)
    col_a, col_b, col_c = st.columns([3, 1, 1])
    with col_a:
        input_code = st.text_input(
            "股票代码",
            value="600519.SS",
            placeholder="例：600519.SS / AAPL / 00700.HK",
            label_visibility="collapsed",
        )
    with col_b:
        hint_mkt = st.selectbox(
            "市场提示（可选）",
            options=["自动识别", "🇨🇳 A股", "🇭🇰 港股", "🇺🇸 美股", "🇰🇷 韩股"],
            label_visibility="collapsed",
        )
    with col_c:
        run_btn = st.button("🚀 开始分析", type="primary", use_container_width=True)

    st.info(
        "💡 提示：首次拉取数据需要 3~15 秒（受接口限流/网络影响），之后使用缓存 < 1 秒。"
        "如遇拉取失败可勾选左侧「强制刷新」或稍后再试。"
    )

hint_map = {
    "自动识别": None,
    "🇨🇳 A股": "CN",
    "🇭🇰 港股": "HK",
    "🇺🇸 美股": "US",
    "🇰🇷 韩股": "KR",
}
hint_val = hint_map.get(hint_mkt)
weights_used = {"financial": fin_w / 100.0, "technical": tech_w / 100.0}

# ---------- 点击按钮执行分析 ----------
if run_btn:
    code = (input_code or "").strip()
    if not code:
        st.warning("请先输入股票代码")
    else:
        t0 = time.time()
        yf_code = market = None
        with st.status("🔧 正在执行分析...", expanded=True, state="running") as status_st:
            try:
                st.write("Step 1/4：规范化识别股票代码...")
                yf_code, market = san.normalize_code(code, market_hint=hint_val)
                st.write(f"→ 识别结果：`{yf_code}`（{MARKET_LABEL.get(market, market)}）")

                st.write("Step 2/4：综合分析（拉取行情 + 财报 + 技术评分 + 综合评级）...")
                result = san.analyze_stock(
                    code, market_hint=hint_val,
                    force_refresh=force, weights=weights_used,
                )

                if result.get("error"):
                    st.warning(f"⚠️ 分析提示：{result['error']}")
                dt = time.time() - t0
                status_st.update(label=f"✅ 分析完成 · 耗时 {dt:.1f}s", state="complete", expanded=False)
                st.session_state["_ss_last_result"] = result
                st.session_state["_ss_last_yf_code"] = yf_code
                st.session_state["_ss_last_code"] = code
            except Exception as ex:
                status_st.update(label="❌ 分析失败", state="error", expanded=True)
                st.exception(ex)
                st.error(f"分析失败：{ex}")

# ---------- 展示上一次结果 ----------
last = st.session_state.get("_ss_last_result")
if last is None:
    st.info(
        "👆 请在上方输入股票代码并点「🚀 开始分析」。\n\n"
        "**快速体验可直接点按钮**（默认已填入 600519.SS 贵州茅台）。"
    )
else:
    st.divider()
    st.subheader("② 分析结果", divider=True)
    render_result(last)

# ---------- 页脚 ----------
st.divider()
c_left, c_right = st.columns([2, 1], gap="large")
with c_left:
    st.markdown(
        """
        <div style="color:#6c757d;font-size:14px;line-height:1.6;">
          <p style="font-weight:600;margin-bottom:8px;color:#212529;">📜 免责声明</p>
          <p style="margin:0 0 6px 0;">
            本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标等）
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
          <p style="margin:0;">联系方式：<a href="mailto:yanying76@gmail.com" style="color:#6c757d;">yanying76@gmail.com</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

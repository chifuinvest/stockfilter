# -*- coding: utf-8 -*-
"""
Yahoo Finance + Tushare 真实数据诊断脚本
输出：600519.SS (A) 与 AAPL (US) 的
  1) Tushare fina_indicator 字段/真实值（为什么之前 50 分？）
  2) Yahoo ticker.info 里与财务相关的 12 个 key 的值
  3) Yahoo income_stmt / balance_sheet 的列名 + 最近两期数值（用来自算 ROE/ROA/同比/负债率等）
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import pandas as pd
pd.set_option("display.max_columns", 60)
pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 60)


def print_sep(title):
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def _dump_yf(yf, code):
    print_sep(f"Yahoo Finance 真实数据诊断：{code}")
    t = yf.Ticker(code)

    # 1) info
    try:
        info = t.info or {}
        print(f"\n[1/4] ticker.info 总字段数：{len(info)}")
        fin_keys = [
            "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
            "dividendYield", "returnOnEquity", "returnOnAssets",
            "grossMargins", "profitMargins", "revenueGrowth", "earningsGrowth",
            "debtToEquity", "debtToAssets", "currentRatio", "marketCap",
            "totalRevenue", "netIncomeToCommon", "totalCash", "totalDebt",
            "totalAssets", "totalLiab", "currentAssets", "currentLiabilities",
            "stockholdersEquity", "bookValue", "revenuePerShare", "trailingEps",
        ]
        rows = []
        for k in fin_keys:
            v = info.get(k)
            if v is not None and v != "N/A":
                rows.append({"key": k, "value": v, "type": type(v).__name__})
        if rows:
            print("     下列财务相关字段**确实有真实数据**（非None）：")
            print(pd.DataFrame(rows).to_string(index=False))
        else:
            print("     ⚠️ info 中上述关键字段全部为 None/N/A（极可能被限流或 Yahoo 已移除这些字段）")
    except Exception as e:
        print(f"\n[1/4] ticker.info 抛出异常: {type(e).__name__}: {e}")

    # 2) income_stmt (年度)
    try:
        inc = t.income_stmt
        print(f"\n[2/4] ticker.income_stmt（年度利润表）shape={getattr(inc,'shape',None)}，columns={list(inc.columns)[:6] if isinstance(inc, pd.DataFrame) else 'N/A'}")
        if isinstance(inc, pd.DataFrame) and len(inc) > 0:
            key_rows = ["Total Revenue", "Gross Profit", "Operating Income",
                        "Net Income", "Net Income Common Stockholders",
                        "Cost Of Revenue", "Total Operating Expenses"]
            exist = [r for r in key_rows if r in inc.index]
            if exist:
                # 最近两期（按列日期倒序取前两列）
                cols_sorted = sorted(inc.columns, reverse=True)[:3]
                print(f"     关键行 × 最近 {len(cols_sorted)} 期：")
                print(inc.loc[exist, cols_sorted].to_string())
            else:
                print("     profit表全部index名示例：", list(inc.index)[:20])
    except Exception as e:
        print(f"\n[2/4] income_stmt 异常: {type(e).__name__}: {e}")

    # 3) quarterly_income_stmt
    try:
        qinc = t.quarterly_income_stmt
        print(f"\n[3/4] ticker.quarterly_income_stmt（季度利润表）shape={getattr(qinc,'shape',None)}")
        if isinstance(qinc, pd.DataFrame) and len(qinc) > 0:
            key_rows = ["Total Revenue", "Gross Profit", "Net Income", "Net Income Common Stockholders"]
            exist = [r for r in key_rows if r in qinc.index]
            if exist:
                cols_sorted = sorted(qinc.columns, reverse=True)[:4]
                print(f"     关键行 × 最近 {len(cols_sorted)} 季度：")
                print(qinc.loc[exist, cols_sorted].to_string())
            else:
                print("     quarterly profit index示例：", list(qinc.index)[:20])
    except Exception as e:
        print(f"\n[3/4] quarterly_income_stmt 异常: {type(e).__name__}: {e}")

    # 4) balance_sheet (年度)
    try:
        bs = t.balance_sheet
        print(f"\n[4/4] ticker.balance_sheet（年度资产负债表）shape={getattr(bs,'shape',None)}")
        if isinstance(bs, pd.DataFrame) and len(bs) > 0:
            key_rows = [
                "Total Assets", "Total Liabilities Net Minority Interest",
                "Total Equity Gross Minority Interest",
                "Stockholders Equity",
                "Current Assets", "Current Liabilities",
                "Total Current Assets", "Total Current Liabilities",
                "Total Debt", "Net Debt", "Cash And Cash Equivalents",
            ]
            exist = [r for r in key_rows if r in bs.index]
            if exist:
                cols_sorted = sorted(bs.columns, reverse=True)[:3]
                print(f"     关键行 × 最近 {len(cols_sorted)} 期：")
                print(bs.loc[exist, cols_sorted].to_string())
            else:
                print("     balance_sheet 全部index名示例：", list(bs.index)[:30])
    except Exception as e:
        print(f"\n[4/4] balance_sheet 异常: {type(e).__name__}: {e}")


def _dump_ts():
    print_sep("Tushare fina_indicator 真实数据诊断：600519.SS（对应 ts_code=600519.SH）")
    try:
        import data_fetcher_v2 as dfv2
        from datetime import datetime
        _ = getattr(dfv2, "_TS_OK", False)
        pro = getattr(dfv2, "_ts_pro", None)
    except Exception as e:
        print(f"  ⚠️ 无法导入 data_fetcher_v2 的 Tushare：{e}")
        return
    if pro is None:
        print("  ⚠️ Tushare _ts_pro 未初始化成功，跳过")
        return

    # 原代码的时间范围（7月 → 20260630 ~ 20260710） VS 扩展到 2 年
    cases = [
        ("原代码窄范围",
         "20260630",
         "20260710"),
        ("扩展到最近2年（修复方案）",
         (datetime(2026, 7, 10).replace(year=datetime(2026, 7, 10).year - 2)).strftime("%Y%m%d"),
         "20260710"),
    ]
    for name, sd, ed in cases:
        print(f"\n--- [{name}] start_date={sd} end_date={ed} ---")
        try:
            fi = pro.fina_indicator(ts_code="600519.SH", start_date=sd, end_date=ed,
                                    fields="ts_code,end_date,roe,roe_dt,roa,"
                                           "grossprofit_margin,netprofit_margin,"
                                           "revenue_yoy,profit_yoy,debt_to_assets,current_ratio")
            print(f"     fina_indicator 返回行数：{len(fi) if isinstance(fi, pd.DataFrame) else type(fi)}")
            if isinstance(fi, pd.DataFrame) and len(fi) > 0:
                fi_sorted = fi.sort_values("end_date", ascending=False)
                print(fi_sorted.head(6).to_string(index=False))
            else:
                print("     ⚠️ 空（所以原代码拿不到ROE等，全部默认50 → 这就是BUG）")
        except Exception as e:
            print(f"     异常: {type(e).__name__}: {e}")


def main():
    print_sep("1. 初始化后端 + 检查 yfinance 版本")
    try:
        import financial_analyzer as fa
        fa._ensure_backend()
        yf = fa.yf
        print(f"   yfinance 对象 = {yf!r}，TS_OK={fa._TS_OK}，YF_OK={fa._YF_OK}")
    except Exception as e:
        print(f"   ⚠️ 导入financial_analyzer失败: {type(e).__name__}: {e}")
        import yfinance as yf

    # AAPL 作为 Yahoo 全功能基准测试（美股一般不限流且数据齐全）
    _dump_yf(yf, "AAPL")
    # 600519.SS 验证 A 股 Yahoo 数据
    _dump_yf(yf, "600519.SS")
    # 检查 Tushare 为什么没拿到 A 股财务指标
    _dump_ts()


if __name__ == "__main__":
    sys.exit(main() or 0)

# -*- coding: utf-8 -*-
"""真实数据接口探测：先跑小样本确认 akshare/yfinance 四个接口都通"""
import sys, time, traceback
import numpy as np
import pandas as pd

print(f"[env] python={sys.version.split()[0]}  pandas={pd.__version__}  numpy={np.__version__}")
t0 = time.time()

# 1) akshare
print("\n=== 1/5  akshare import + A股概念板块列表 ===")
try:
    import akshare as ak
    print(f"  akshare version: {ak.__version__}")
    t = time.time()
    df = ak.stock_board_concept_name_em()
    print(f"  stock_board_concept_name_em -> {len(df)} 行, cols={list(df.columns[:6])}  ({time.time()-t:.1f}s)")
    # 取一个包含"芯片"的板块
    kw_cols = [c for c in df.columns if "板块名称" in str(c) or "名称" == str(c)]
    name_col = kw_cols[0] if kw_cols else df.columns[0]
    chip_row = df[df[name_col].astype(str).str.contains("芯片|半导体|光模块|算力", na=False)]
    if len(chip_row):
        r = chip_row.iloc[0]
        bname = str(r[name_col])
        code_col = [c for c in df.columns if "板块代码" in str(c) or "代码" == str(c)]
        bcode = str(r[code_col[0]]) if code_col else ""
        print(f"  命中板块示例: {bname}  代码={bcode}")
        # 拿成分
        t2 = time.time()
        try:
            cons = ak.stock_board_concept_cons_em(symbol=bname)
            print(f"  stock_board_concept_cons_em({bname}) -> {len(cons)} 行  cols={list(cons.columns[:5])}  ({time.time()-t2:.1f}s)")
        except Exception as e:
            print(f"  [WARN] 成分接口失败: {e}")
except Exception as e:
    print(f"  [FATAL] akshare: {e}")
    traceback.print_exc()

# 2) akshare A股日线: 688256 (寒武纪) 最近1年
print("\n=== 2/5  akshare.stock_zh_a_hist (688256 寒武纪 最近1年) ===")
try:
    from datetime import datetime, timedelta
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    t = time.time()
    df = ak.stock_zh_a_hist(symbol="688256", period="daily", start_date=start, end_date=end, adjust="qfq")
    print(f"  -> {len(df)} 行, cols={list(df.columns)}, 日期范围={df.iloc[0]['日期'] if len(df) else '?'} ~ {df.iloc[-1]['日期'] if len(df) else '?'}  ({time.time()-t:.1f}s)")
except Exception as e:
    print(f"  [WARN] {e}")
    traceback.print_exc()

# 3) akshare A股财报摘要: 688256
print("\n=== 3/5  akshare.stock_financial_abstract_ths (688256 寒武纪) ===")
try:
    t = time.time()
    df = ak.stock_financial_abstract_ths(symbol="688256", indicator="按报告期")
    print(f"  -> {df.shape}, cols={list(df.columns)[:8]}  ({time.time()-t:.1f}s)")
    print(f"     前3行前3列:\n{df.iloc[:3, :3].to_string()}")
except Exception as e:
    print(f"  [WARN] 同花顺财报摘要失败: {e}")
    try:
        t = time.time()
        inc = ak.stock_financial_report_sina(stock="688256", symbol="利润表")
        bs = ak.stock_financial_report_sina(stock="688256", symbol="资产负债表")
        print(f"  [FALLBACK] sina利润表{inc.shape} 资产负债表{bs.shape}  ({time.time()-t:.1f}s)")
        if not inc.empty:
            print(f"     利润表 cols={list(inc.columns[:8])}")
            print(f"     最近1个报告日 cols 示例: {inc.iloc[-1, :4].to_dict()}")
    except Exception as ee:
        print(f"  [FAIL] sina财务也失败: {ee}")

# 4) yfinance 批量下载价格 3 只 (NVDA / 0700.HK / 9988.HK)
print("\n=== 4/5  yfinance.download 批量3只 (NVDA,0700.HK,9988.HK) 最近1年 ===")
try:
    import yfinance as yf
    print(f"  yfinance version: {yf.__version__}")
    t = time.time()
    dl = yf.download(tickers=["NVDA", "0700.HK", "9988.HK"], period="1y", interval="1d",
                     auto_adjust=True, progress=False, threads=False, group_by="ticker")
    print(f"  -> 列数={len(dl.columns)} 行数={len(dl)}  用时={time.time()-t:.1f}s")
    n_per = {t_: len(dl[t_].dropna(how="all")) for t_ in ["NVDA", "0700.HK", "9988.HK"] if t_ in dl.columns.get_level_values(0)}
    print(f"     各只非空天数: {n_per}")
except Exception as e:
    print(f"  [WARN] {e}")
    traceback.print_exc()

# 5) yfinance Ticker NVDA 季度财务
print("\n=== 5/5  yfinance.Ticker('NVDA').quarterly_financials / quarterly_balance_sheet ===")
try:
    import yfinance as yf
    t = time.time()
    tk = yf.Ticker("NVDA")
    inc = tk.quarterly_financials
    bs = tk.quarterly_balance_sheet
    print(f"  income: {inc.shape if inc is not None else 'None'}  bs: {bs.shape if bs is not None else 'None'}  ({time.time()-t:.1f}s)")
    if inc is not None and len(inc) > 0:
        print(f"     income行标样本(前10): {list(inc.index[:10])}")
        print(f"     income列(报告期): {list(inc.columns)}")
except Exception as e:
    print(f"  [WARN] {e}")
    traceback.print_exc()

print(f"\n[DONE] 总用时 {time.time()-t0:.1f}s")

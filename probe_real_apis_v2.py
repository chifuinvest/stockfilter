# -*- coding: utf-8 -*-
"""真实数据接口探测 2：先打 curl_cffi 指纹，再测 akshare EM/同花顺 + yfinance 单只"""
import sys, time, traceback
t0 = time.time()

# —— 提前植入和 main.py 一样的 monkey patch ——
_CURL_CFFI_PATCHED = False
try:
    from curl_cffi import requests as _cf_req
    import requests as _orig_req
    from urllib.parse import urlparse
    _TARGET_DOMAINS = (
        "eastmoney.com", "push2his.eastmoney.com", "push2.eastmoney.com",
        "datacenter-web.eastmoney.com", "data.eastmoney.com", "quote.eastmoney.com",
        "10jqka.com.cn", "ths123.com", "5ifund.com",
        "biz.finance.sina.com.cn", "finance.sina.com.cn", "stock.finance.sina.com.cn",
        "query.sse.com.cn", "www.szse.cn", "market.finance.sina.com.cn",
        "finance.yahoo.com", "query1.finance.yahoo.com", "query2.finance.yahoo.com",
        "fc.yahoo.com", "hk.finance.yahoo.com", "caiban.eastmoney.com"
    )
    def _hit(url):
        h = (urlparse(url).hostname or "").lower()
        return bool(h and any(h.endswith(d) for d in _TARGET_DOMAINS))
    _IMPERSONATE = "chrome"
    _orig_get = _orig_req.get
    def _patched_get(url, **kw):
        if _hit(url):
            kw.setdefault("impersonate", _IMPERSONATE)
            kw.pop("proxies", None)
            return _cf_req.get(url, **kw)
        return _orig_get(url, **kw)
    _orig_req.get = _patched_get
    _orig_sr = _orig_req.Session.request
    def _patched_sr(self, method, url, **kw):
        if _hit(url) and method.upper() in ("GET","POST"):
            kw.setdefault("impersonate", _IMPERSONATE)
            kw.pop("proxies", None)
            return getattr(_cf_req, method.lower())(url, **kw)
        return _orig_sr(self, method, url, **kw)
    _orig_req.Session.request = _patched_sr
    _CURL_CFFI_PATCHED = True
    print("[PREP] curl_cffi monkey patch installed ✅")
except Exception as e:
    print(f"[PREP][WARN] cannot install curl_cffi patch: {e}")

import numpy as np
import pandas as pd
print(f"[env] python={sys.version.split()[0]}  pandas={pd.__version__}  numpy={np.__version__}")

# 1) akshare 概念板块（东财 EM 接口，之前 RemoteDisconnected）
print("\n=== 1/6  akshare.stock_board_concept_name_em() ===")
try:
    import akshare as ak
    print(f"  akshare: {ak.__version__}")
    t = time.time()
    df = ak.stock_board_concept_name_em()
    print(f"  -> {len(df)} 行, cols={list(df.columns[:4])}  ({time.time()-t:.1f}s)")
    # 找关键词
    nc = next((c for c in df.columns if "板块名称" in str(c) or "名称" == str(c)), df.columns[0])
    hits = df[df[nc].astype(str).str.contains("芯片|半导体|光模块|算力|液冷", na=False)]
    print(f"     关键词板块命中: {len(hits)} 条，示例前5={hits[nc].head().tolist()}")
    if len(hits):
        r = hits.iloc[0]
        bn = str(r[nc])
        cc = next((c for c in df.columns if "板块代码" in str(c)), None)
        bc = str(r[cc]) if cc else ""
        print(f"     取板块 {bn} ({bc}) 的成分股...")
        t2 = time.time()
        cons = ak.stock_board_concept_cons_em(symbol=bn)
        print(f"     stock_board_concept_cons_em({bn}) -> {len(cons)} 行, cols={list(cons.columns[:5])}  ({time.time()-t2:.1f}s)")
except Exception as e:
    print(f"  [ERR] {e}")
    traceback.print_exc()

# 2) akshare A股日线（push2his.eastmoney.com，之前 RemoteDisconnected）
print("\n=== 2/6  akshare.stock_zh_a_hist(688256, 最近1年) ===")
try:
    from datetime import datetime, timedelta
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    t = time.time()
    df = ak.stock_zh_a_hist(symbol="688256", period="daily", start_date=start, end_date=end, adjust="qfq")
    print(f"  -> {len(df)} 行, cols={list(df.columns)}  ({time.time()-t:.1f}s)")
except Exception as e:
    print(f"  [ERR] {e}")
    traceback.print_exc()

# 3) akshare 同花顺财报摘要
print("\n=== 3/6  akshare.stock_financial_abstract_ths(688256) ===")
try:
    t = time.time()
    df = ak.stock_financial_abstract_ths(symbol="688256", indicator="按报告期")
    print(f"  -> {df.shape}, cols={list(df.columns)[:8]}  ({time.time()-t:.1f}s)")
except Exception as e:
    print(f"  [ERR] {e}")

# 4) yfinance 单只 Ticker.history(NVDA 最近 1 年)
print("\n=== 4/6  yfinance Ticker('NVDA').history(1y) ===")
try:
    import yfinance as yf
    print(f"  yfinance: {yf.__version__}")
    t = time.time()
    tk = yf.Ticker("NVDA")
    hist = tk.history(period="1y", interval="1d", auto_adjust=True)
    print(f"  -> {hist.shape}, cols={list(hist.columns)}  ({time.time()-t:.1f}s)")
    if len(hist):
        print(f"     范围: {hist.index[0].date()} ~ {hist.index[-1].date()}, 收盘: {hist['Close'].iloc[-1]:.2f}")
except Exception as e:
    print(f"  [ERR] {e}")
    traceback.print_exc()

# 5) yfinance 单只 港股 history(0700.HK)
print("\n=== 5/6  yfinance Ticker('0700.HK').history(1y) ===")
try:
    t = time.time()
    hist = yf.Ticker("0700.HK").history(period="1y")
    print(f"  -> {hist.shape}  ({time.time()-t:.1f}s)")
except Exception as e:
    print(f"  [ERR] {e}")

# 6) NVDA quarterly_financials
print("\n=== 6/6  yfinance Ticker('NVDA').quarterly_financials ===")
try:
    import yfinance as yf
    t = time.time()
    inc = yf.Ticker("NVDA").quarterly_financials
    print(f"  income: {inc.shape if inc is not None else 'None'}  ({time.time()-t:.1f}s)")
    if inc is not None and len(inc):
        print(f"     行标前10: {list(inc.index[:10])}")
        print(f"     列(报告期): {list(inc.columns)}")
except Exception as e:
    print(f"  [ERR] {e}")

print(f"\n[DONE] 总用时 {time.time()-t0:.1f}s")

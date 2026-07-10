# -*- coding: utf-8 -*-
"""
后端直接测试：600519.SS（贵州茅台）
绕开 Streamlit，直接验证核心分析函数返回值是否正确
"""
import os
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

def _shorten(obj, max_len=200):
    s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s

def main():
    t0 = time.time()
    try:
        import stock_analyzer as san
        print("[OK] 模块 stock_analyzer 导入成功\n")
    except Exception as e:
        print(f"[ERR] 导入 stock_analyzer 失败：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return 1

    CODE = "600519.SS"
    print(f">>> 调用 san.analyze_stock('{CODE}', force_refresh=False) ...")
    try:
        result = san.analyze_stock(CODE, force_refresh=False)
    except Exception as e:
        print(f"[ERR] analyze_stock 抛出异常：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return 2

    dt = time.time() - t0
    print(f"[OK] 分析完成，耗时 {dt:.1f}s")
    print(f"     result dict keys 共 {len(result)} 个：{sorted(result.keys())}\n")

    print("=" * 78)
    print(" 一、基础信息")
    print("=" * 78)
    for k in ["yf_code", "market", "market_label", "price"]:
        v = result.get(k)
        print(f"  {k:>14s} = {v!r}")
    for k in ["pct_1d", "pct_7d", "pct_30d", "pct_1y"]:
        v = result.get(k)
        if isinstance(v, (int, float)):
            print(f"  {k:>14s} = {v*100:+.2f}%")
        else:
            print(f"  {k:>14s} = {v!r}")
    w = result.get("weights_used")
    print(f"  weights_used   = {w!r}\n")

    print("=" * 78)
    print(" 二、综合评分 & 最终评级")
    print("=" * 78)
    fs = result.get("financial_score")
    ts = result.get("technical_score")
    total = result.get("total_score")
    rating = result.get("rating")
    print(f"  financial_score = {fs}")
    print(f"  technical_score = {ts}")
    print(f"  total_score     = {total}")
    if isinstance(rating, dict):
        print(f"  rating 明细     = {json.dumps(rating, ensure_ascii=False, indent=8)}\n")
    else:
        print(f"  rating          = {rating!r}\n")

    fin = result.get("financial") or {}
    tech = result.get("technical") or {}
    print("=" * 78)
    print(" 三、财报维度（financial）子项得分")
    print("=" * 78)
    print(f"  [raw]  财务原始数据 keys = {sorted(fin.get('raw', {}).keys()) if isinstance(fin.get('raw'), dict) else 'N/A'}")
    for section in ["valuation", "profitability", "growth", "health"]:
        sub = fin.get(section) or {}
        print(f"  [{section:>12s}]  score = {sub.get('score')!r:>6s}   细节摘要: {_shorten(sub.get('details') or sub.get('sub_items') or sub, 220)}")
    print(f"  financial['total_score'] = {fin.get('total_score')}\n")

    print("=" * 78)
    print(" 四、技术面维度（technical）子项得分")
    print("=" * 78)
    if isinstance(tech, dict):
        for k in sorted(tech.keys()):
            if k.startswith("score_") or k in ["total_score", "signal", "rsi_value", "macd_value"]:
                print(f"  {k:>20s} = {tech[k]!r}")
    else:
        print(f"  technical = {tech!r}")
    print()

    print("=" * 78)
    print(" 五、亮点 / 风险提示 + 自然语言总结")
    print("=" * 78)
    hl = result.get("highlights") or []
    print(f"  highlights 共 {len(hl)} 条：")
    for i, h in enumerate(hl, 1):
        print(f"    {i}. {h}")
    sm = result.get("summary")
    print(f"\n  summary:\n    {sm}\n")

    if result.get("error"):
        print("=" * 78)
        print(f"  ⚠️  result['error'] 存在：{result['error']}")
        print("=" * 78)

    return 0

if __name__ == "__main__":
    sys.exit(main())

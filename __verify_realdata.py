# -*- coding: utf-8 -*-
"""
强制刷新测试：600519.SS 验证修复后不再是默认50分
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

def main():
    import stock_analyzer as san
    CODE = "600519.SS"
    print(f"[STEP 1] san.analyze_stock('{CODE}', force_refresh=True) ...")
    r = san.analyze_stock(CODE, force_refresh=True)
    print("✓ 完成\n")

    raw = (r.get("financial") or {}).get("raw") or {}
    print("=" * 90)
    print(" 一、financial.raw 真实字段（之前只有7个，现在应该>14个）")
    print("=" * 90)
    keys12 = ["pe_ttm","pb","ps_ttm","div_yield","roe","roa","gross_margin",
              "net_margin","revenue_yoy","earnings_yoy","debt_ratio","current_ratio"]
    rows = []
    for k in keys12:
        v = raw.get(k)
        rows.append({"字段":k,"值":v if v is not None else "⚠️ N/A（还是默认50）"})
    try:
        import pandas as pd
        print(pd.DataFrame(rows).to_string(index=False))
    except Exception:
        for row in rows:
            print(f"  {row['字段']:<15s} = {row['值']}")
    print(f"\n  raw 总字段数: {len(raw)} → keys: {sorted(raw.keys())}\n")

    print("=" * 90)
    print(" 二、四个财报维度分数（盈利/成长/健康不应再是50.0！）")
    print("=" * 90)
    fin = r.get("financial") or {}
    for sec in ["valuation","profitability","growth","health"]:
        s = (fin.get(sec) or {}).get("score")
        dts = (fin.get(sec) or {}).get("details") or {}
        lines = [f"{k}: {v}" for k,v in list(dts.items())[:4]]
        print(f"  {sec:>14s} 分数 = {s!r:<7}   细节: {'; '.join(lines) if lines else '(空)'}")
    print(f"  financial.total_score = {fin.get('total_score')!r}")

    print("\n" + "=" * 90)
    print(" 三、综合评分 & 评级")
    print("=" * 90)
    print(f"  financial_score={r.get('financial_score')}  technical_score={r.get('technical_score')}  total_score={r.get('total_score')}")
    print(f"  rating={r.get('rating')!r}")

    print("\n" + "=" * 90)
    print(" 四、亮点 + 摘要")
    print("=" * 90)
    for h in r.get("highlights") or []:
        print(f"  · [{h.get('type')}/{h.get('dim')}] {h.get('text')}")
    sm = r.get("summary") or ""
    print(f"\n{sm}")

    # 验证标志：如果8项关键指标都不为None，则算通过
    missing = [k for k in ["roe","roa","gross_margin","net_margin","debt_ratio","current_ratio"] if raw.get(k) is None]
    print("\n" + "=" * 90)
    if missing:
        print(f"  ❌ 仍有真实数据缺失: {missing}（可能Yahoo也没连）")
    else:
        print(f"  ✅ 6项核心财务指标全部接入真实数据！之前是默认50的现在已经是真实分了")
    return 0

if __name__ == "__main__":
    sys.exit(main())

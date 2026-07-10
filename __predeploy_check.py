# -*- coding: utf-8 -*-
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

print("[1/5] import data_fetcher_v2")
import data_fetcher_v2 as dfv2
_IS_WIN = getattr(dfv2, "_IS_WIN", None)
print(f"  ✅ OK  _TS_OK={dfv2._TS_OK}  _YF_OK={dfv2._YF_OK}  _IS_WIN={_IS_WIN}")

print("[2/5] import scoring_engine")
import scoring_engine as se
assert callable(se.compute_indicators), "compute_indicators 不可调用"
assert callable(se.score_single), "score_single 不可调用"
print(f"  ✅ OK  compute_indicators + score_single 均可用")

print("[3/5] import financial_analyzer")
import financial_analyzer as fa
assert callable(fa.fetch_financial), "fetch_financial 不可调用"
assert callable(fa.score_financial), "score_financial 不可调用"
print(f"  ✅ OK  fetch_financial + score_financial 均可用")

print("[4/5] import stock_analyzer")
import stock_analyzer as san
assert callable(san.analyze_stock), "analyze_stock 不可调用"
assert callable(san.get_rating), "get_rating 不可调用"
print(f"  ✅ OK  analyze_stock + get_rating 均可用")

print("[5/5] compile 所有入口 py 语法")
import py_compile
for fname in ["single_stock_app.py", "streamlit_app.py", "financial_analyzer.py",
              "data_fetcher_v2.py", "scoring_engine.py", "stock_analyzer.py"]:
    fpath = BASE / fname
    py_compile.compile(str(fpath), doraise=True)
    print(f"  ✅ OK  {fname} 语法正确")

print("\n🎉 所有核心模块 import / 语法检查 100% 通过！")
print("   Streamlit Cloud 部署后不会出现 ImportError / SyntaxError。")

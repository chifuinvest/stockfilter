# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import traceback

PROJ_DIR = r"c:\Users\Bart\Documents\trae_projects\stockfilter"
EXPECTED_TEMP = os.path.join(PROJ_DIR, "data_cache", "yfinance")

print("=" * 70)
print("【测试2：DETACHED 坏环境验证修复】")
print("=" * 70)

print("\n[步骤1] 破坏环境变量（模拟 DETACHED 坏环境）")
os.environ["HOME"] = "C:/nonexistent123"
os.environ["USERPROFILE"] = "C:/nonexistent456"
os.environ["TMP"] = "C:/Windows/System32/fake"
os.environ["TEMP"] = "C:/Windows/System32/fake"
if "TUSHARE_TOKEN" in os.environ:
    del os.environ["TUSHARE_TOKEN"]
print(f"  HOME        = {os.environ.get('HOME')}")
print(f"  USERPROFILE = {os.environ.get('USERPROFILE')}")
print(f"  TMP         = {os.environ.get('TMP')}")
print(f"  TEMP        = {os.environ.get('TEMP')}")
print(f"  TUSHARE_TOKEN in env? {'TUSHARE_TOKEN' in os.environ} (预期: False)")

print("\n[步骤2] 插入项目路径到 sys.path")
sys.path.insert(0, PROJ_DIR)
print(f"  sys.path[0] = {sys.path[0]}")

print("\n[步骤3] import tempfile 后打印 tempfile.gettempdir()（import main 之前）")
# 注意：tempfile 可能已经被 import 了，这里要强制重置 tempfile.tempdir 为 None 再获取
tempfile.tempdir = None
try:
    td_before = tempfile.gettempdir()
except Exception as e:
    td_before = f"<ERROR: {e}>"
print(f"  tempfile.gettempdir() = {td_before}")

print("\n[步骤4] import main 模块（触发 _bootstrap_user_env）")
try:
    import main
    print("  ✅ import main 成功")
except Exception as e:
    print(f"  ❌ import main 失败: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n[步骤5] import main 后 tempfile.gettempdir() 的值")
tempfile.tempdir = None
try:
    td_after_main = tempfile.gettempdir()
except Exception as e:
    td_after_main = f"<ERROR: {e}>"
print(f"  tempfile.gettempdir() = {td_after_main}")
print(f"  预期路径:              {EXPECTED_TEMP}")
print(f"  是否匹配预期?         {str(td_after_main).lower().replace(chr(92), '/') == EXPECTED_TEMP.lower().replace(chr(92), '/')}")

print("\n[步骤6] TUSHARE_TOKEN 是否设置成功")
tushare_tok = os.environ.get("TUSHARE_TOKEN", "")
print(f"  TUSHARE_TOKEN 已设置? {bool(tushare_tok)}")
if tushare_tok:
    masked = tushare_tok[:4] + "***" + tushare_tok[-4:] if len(tushare_tok) > 8 else "***"
    print(f"  TUSHARE_TOKEN 值(遮蔽): {masked}")
else:
    print("  ⚠️  TUSHARE_TOKEN 为空")

print("\n[步骤7] from data_fetcher_v2 import fetch_single_price, _YF_OK")
try:
    from data_fetcher_v2 import fetch_single_price, _YF_OK
    print("  ✅ import data_fetcher_v2 成功")
except Exception as e:
    print(f"  ❌ import data_fetcher_v2 失败: {type(e).__name__}: {e}")
    traceback.print_exc()
    _YF_OK = None
    fetch_single_price = None

print(f"\n[步骤8] 打印 _YF_OK (预期: True)")
print(f"  _YF_OK = {_YF_OK}")
print(f"  是否匹配预期? {_YF_OK is True}")

print("\n[步骤9] 打印 tempfile.gettempdir()（应为项目路径）")
tempfile.tempdir = None
try:
    td_after_df = tempfile.gettempdir()
except Exception as e:
    td_after_df = f"<ERROR: {e}>"
print(f"  tempfile.gettempdir() = {td_after_df}")
print(f"  是否项目内路径?       {'data_cache' in str(td_after_df)}")

print("\n[步骤10] 尝试 fetch_single_price('NVDA', force_refresh=True)")
print("  判定规则:")
print("    - YFRateLimit/429/空数据/返回None = OK")
print('    - "unable to open database file" = FAIL')
unable_to_open_db = False
fetch_status = "UNKNOWN"
fetch_exception_type = None
fetch_exception_msg = ""
fetch_result = None

if fetch_single_price is not None and _YF_OK:
    try:
        fetch_result = fetch_single_price("NVDA", force_refresh=True)
        if fetch_result is None:
            fetch_status = "OK (返回 None - 空数据视为 OK)"
        else:
            n_rows = len(fetch_result)
            fetch_status = f"OK (返回 DataFrame {n_rows} 行)"
    except Exception as e:
        fetch_exception_type = type(e).__name__
        fetch_exception_msg = str(e)
        msg_lower = fetch_exception_msg.lower()
        if "unable to open database file" in msg_lower:
            fetch_status = "FAIL (unable to open database file)"
            unable_to_open_db = True
        elif ("429" in fetch_exception_msg
              or "rate" in msg_lower and "limit" in msg_lower
              or "too many" in msg_lower
              or "empty" in msg_lower):
            fetch_status = f"OK ({fetch_exception_type}: {fetch_exception_msg[:120]})"
        else:
            fetch_status = f"OTHER ({fetch_exception_type}: {fetch_exception_msg[:200]})"
            if "unable to open database file" in msg_lower:
                unable_to_open_db = True
                fetch_status = "FAIL (unable to open database file)"
else:
    fetch_status = "SKIP (fetch_single_price 或 _YF_OK 不可用)"

print(f"  结果: {fetch_status}")
if fetch_exception_type:
    print(f"  异常类型: {fetch_exception_type}")
    print(f"  异常消息: {fetch_exception_msg[:300]}")

print("\n" + "=" * 70)
print("【关键结论汇总】")
print("=" * 70)
print(f"1. import main 前 tempfile.gettempdir() = {td_before}")
print(f"2. import main 后 tempfile.gettempdir() = {td_after_main}")
print(f"3. import data_fetcher_v2 后 tempfile.gettempdir() = {td_after_df}")
print(f"4. 最终 tempfile 临时目录 = {td_after_df}")
print(f"5. TUSHARE_TOKEN 是否设置成功: {bool(tushare_tok)}")
print(f"6. _YF_OK = {_YF_OK}")
print(f'7. 是否出现 "unable to open database file": {unable_to_open_db}')
print(f"8. fetch_single_price('NVDA') 状态: {fetch_status}")

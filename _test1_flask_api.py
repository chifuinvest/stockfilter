# -*- coding: utf-8 -*-
import urllib.request
import urllib.error
import json
import time
import sys

BASE_URL = "http://127.0.0.1:5000"


def get_scores():
    url = f"{BASE_URL}/api/scores"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return status_code, data, None
    except urllib.error.HTTPError as e:
        return e.code, None, str(e)
    except Exception as e:
        return None, None, str(e)


def post_refresh(force=False):
    url = f"{BASE_URL}/api/refresh"
    body = json.dumps({"force": force}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.getcode()
            resp_body = resp.read().decode("utf-8")
            data = json.loads(resp_body)
            return status_code, data, None
    except urllib.error.HTTPError as e:
        return e.code, None, str(e)
    except Exception as e:
        return None, None, str(e)


def print_score_result(status_code, data, err):
    print("=" * 70)
    print("【测试1：Flask API /api/scores 验证】")
    print("=" * 70)
    print(f"HTTP 状态码: {status_code}")
    if err:
        print(f"请求错误: {err}")
        return
    if data is None:
        print("返回数据为空（无 JSON）")
        return

    print(f"JSON status: {data.get('status')}")
    print(f"scored_count: {data.get('scored_count')}")
    print(f"pool_size: {data.get('pool_size')}")
    results = data.get("results") or []
    print(f"results 长度: {len(results)}")
    print(f"stats: {json.dumps(data.get('stats'), ensure_ascii=False, indent=2)}")

    print("\n前 3 条 results (code, name, total_score, level):")
    for i, r in enumerate(results[:3], 1):
        code = r.get("code")
        name = r.get("name")
        total_score = r.get("total_score")
        level = r.get("level")
        print(f"  [{i}] code={code!r}, name={name!r}, total_score={total_score!r}, level={level!r}")

    if len(results) == 0:
        print("\n⚠️  返回 results 为空，将触发 POST /api/refresh + 等待 15 秒后重试...")
        return True
    return False


def main():
    status_code, data, err = get_scores()
    need_retry = print_score_result(status_code, data, err)

    if need_retry:
        print("\n--- 触发 POST /api/refresh (force=false) ---")
        rf_status, rf_data, rf_err = post_refresh(force=False)
        print(f"refresh HTTP 状态码: {rf_status}")
        if rf_data:
            print(f"refresh 返回: {json.dumps(rf_data, ensure_ascii=False, indent=2)}")
        if rf_err:
            print(f"refresh 错误: {rf_err}")

        print("\n等待 15 秒...")
        time.sleep(15)

        print("\n--- 重试 GET /api/scores ---")
        status_code2, data2, err2 = get_scores()
        print_score_result(status_code2, data2, err2)


if __name__ == "__main__":
    main()

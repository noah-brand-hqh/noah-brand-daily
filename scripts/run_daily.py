"""
run_daily.py
============
每日主编排脚本 · GitHub Actions 调用入口。
按顺序执行：
  1. collect_data.py       采集今日数据
  2. compute_rankings.py   计算与昨日的对比
  3. generate_and_send.py  生成并发送邮件

每一步都做异常捕获，即使某步失败也尽可能完成其他步骤。
"""

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def run_step(name: str, script: str) -> bool:
    print(f"\n{'='*60}\n[STEP] {name}\n{'='*60}")
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, script)],
            check=True,
            capture_output=False,
        )
        print(f"[OK] {name} 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] {name} 失败 · 退出码 {e.returncode}", file=sys.stderr)
        return False


def main():
    steps = [
        ("采集数据", "collect_data.py"),
        ("计算排序", "compute_rankings.py"),
        ("生成邮件并发送", "generate_and_send.py"),
    ]

    failures = []
    for name, script in steps:
        ok = run_step(name, script)
        if not ok:
            failures.append(name)
            # collect_data 失败则整体终止
            if name == "采集数据":
                print("[FATAL] 采集环节失败，终止流程", file=sys.stderr)
                sys.exit(1)

    if failures:
        print(f"\n[WARN] 以下环节失败: {failures}", file=sys.stderr)
        sys.exit(1)
    print("\n[ALL OK] 今日流程全部完成")


if __name__ == "__main__":
    main()

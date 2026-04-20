"""
run_daily.py
============
每日主编排脚本 · GitHub Actions 调用入口。
按顺序执行：
  1. collect_data.py       采集今日数据
  2. compute_rankings.py   计算与昨日的对比
  3. generate_and_send.py  生成并发送邮件
  4. publish_latest.py     生成 data/latest.json + git push（看板自动更新）

每一步都做异常捕获，即使某步失败也尽可能完成其他步骤。
"""

import subprocess
import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
import pytz

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = Path(ROOT).parent

# 自动加载项目根目录的 .env 文件（本地运行时使用）
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def run_step(name: str, script: str) -> bool:
    print(f"\n{'='*60}\n[STEP] {name}\n{'='*60}")
    try:
        subprocess.run(
            [sys.executable, os.path.join(ROOT, script)],
            check=True,
            capture_output=False,
        )
        print(f"[OK] {name} 完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] {name} 失败 · 退出码 {e.returncode}", file=sys.stderr)
        return False


def publish_latest():
    """复制今日排名到 data/latest.json 和 docs/data/latest.json，供看板动态加载。"""
    print(f"\n{'='*60}\n[STEP] 发布 latest.json\n{'='*60}")
    sgt = pytz.timezone("Asia/Singapore")
    today = datetime.now(sgt).strftime("%Y-%m-%d")
    src = PROJECT_ROOT / "data" / f"rankings_{today}.json"
    dst = PROJECT_ROOT / "data" / "latest.json"
    if not src.exists():
        print(f"[SKIP] 排名文件不存在: {src}", file=sys.stderr)
        return False
    shutil.copy2(src, dst)
    print(f"[OK] data/latest.json 已更新（{today}）")
    # 同步到 docs/data/ 供 GitHub Pages 服务
    docs_data = PROJECT_ROOT / "docs" / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, docs_data / "latest.json")
    print(f"[OK] docs/data/latest.json 已同步")
    return True


def git_push():
    """将 data/ 变更提交并推送到 GitHub，触发 GitHub Pages 更新。"""
    print(f"\n{'='*60}\n[STEP] Git push 到 GitHub\n{'='*60}")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    repo_url = os.environ.get("GITHUB_REPO_URL", "")

    git = shutil.which("git")
    if not git:
        print("[SKIP] 未找到 git 命令，跳过推送", file=sys.stderr)
        return False

    repo = PROJECT_ROOT

    # 确保是 git 仓库
    if not (repo / ".git").exists():
        print("[SKIP] 当前目录不是 git 仓库，跳过推送", file=sys.stderr)
        return False

    sgt = pytz.timezone("Asia/Singapore")
    today = datetime.now(sgt).strftime("%Y-%m-%d")

    try:
        # 配置提交身份
        subprocess.run([git, "-C", str(repo), "config", "user.name", "noah-brand-bot"], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "config", "user.email", "bot@noah-brand.local"], check=True, capture_output=True)

        # 如果有 token，更新 remote URL 为带认证的版本
        if github_token and repo_url:
            from urllib.parse import urlparse
            parsed = urlparse(repo_url)
            auth_url = f"https://{github_token}@{parsed.netloc}{parsed.path}"
            subprocess.run([git, "-C", str(repo), "remote", "set-url", "origin", auth_url], check=True, capture_output=True)

        # 暂存 data/ 和 docs/（看板+数据，供 GitHub Pages 服务）
        subprocess.run([git, "-C", str(repo), "add", "data/", "docs/"], check=True, capture_output=True)

        # 检查是否有变更
        result = subprocess.run([git, "-C", str(repo), "diff", "--staged", "--quiet"], capture_output=True)
        if result.returncode == 0:
            print("[OK] 无新增数据变更，跳过 commit")
            return True

        subprocess.run([git, "-C", str(repo), "commit", "-m", f"📊 Daily data snapshot {today}"], check=True, capture_output=True)
        subprocess.run([git, "-C", str(repo), "push"], check=True, capture_output=True)
        print("[OK] 已推送到 GitHub，看板将在 1-2 分钟内更新")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] git push 失败: {e}", file=sys.stderr)
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
            if name == "采集数据":
                print("[FATAL] 采集环节失败，终止流程", file=sys.stderr)
                sys.exit(1)

    # 生成 latest.json（不影响主流程成败）
    publish_latest()

    # 推送到 GitHub（不影响主流程成败）
    git_push()

    if failures:
        print(f"\n[WARN] 以下环节失败: {failures}", file=sys.stderr)
        sys.exit(1)
    print("\n[ALL OK] 今日流程全部完成")


if __name__ == "__main__":
    main()

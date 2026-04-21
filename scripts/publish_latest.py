"""
publish_latest.py
=================
合并当日的两份 JSON（采集快照 + 排名结果）为看板前端消费的 latest.json。

读取：
  - data/{today}.json              由 collect_data.py 产出的当日采集快照
  - data/rankings_{today}.json     由 compute_rankings.py 产出的对比与排名

写入：
  - docs/data/latest.json          给 GitHub Pages 上的看板前端读取

输出键：date, compared_to, top_gains, top_losses, all_changes,
        sentiment_highlights, suggestions_top10, raw_stock, raw_sentiment,
        top_mentions（前 5 条来自 rankings，后 5 条来自当日采集快照）

注：整体字段从 rankings 文件继承；只有 top_mentions 做 5+5 合并，
    以便看板同时展示"权重排序的头条"和"原始采集流"两种视角。
"""

import json
import os
import sys
from datetime import datetime

import pytz

SGT = pytz.timezone("Asia/Singapore")
TODAY = datetime.now(SGT).strftime("%Y-%m-%d")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "docs", "data")
OUT_PATH = os.path.join(OUT_DIR, "latest.json")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    snapshot_path = os.path.join(DATA_DIR, f"{TODAY}.json")
    rankings_path = os.path.join(DATA_DIR, f"rankings_{TODAY}.json")

    if not os.path.exists(rankings_path):
        print(f"[ERROR] 排名文件未找到：{rankings_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(snapshot_path):
        print(f"[ERROR] 采集快照未找到：{snapshot_path}", file=sys.stderr)
        sys.exit(1)

    rankings = load_json(rankings_path)
    snapshot = load_json(snapshot_path)

    rankings_top = rankings.get("top_mentions", []) or []
    snapshot_top = snapshot.get("top_mentions", []) or []

    merged_top_mentions = rankings_top[:5] + snapshot_top[:5]

    payload = {
        "date": rankings.get("date", TODAY),
        "compared_to": rankings.get("compared_to"),
        "top_gains": rankings.get("top_gains", []),
        "top_losses": rankings.get("top_losses", []),
        "all_changes": rankings.get("all_changes", []),
        "sentiment_highlights": rankings.get("sentiment_highlights", {}),
        "suggestions_top10": rankings.get("suggestions_top10", []),
        "raw_stock": rankings.get("raw_stock", {}),
        "raw_sentiment": rankings.get("raw_sentiment", {}),
        "top_mentions": merged_top_mentions,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(
        f"[OK] 已写入 {OUT_PATH} · "
        f"date={payload['date']} compared_to={payload['compared_to']} "
        f"top_mentions={len(merged_top_mentions)} "
        f"(rankings={min(len(rankings_top), 5)} + snapshot={min(len(snapshot_top), 5)})"
    )


if __name__ == "__main__":
    main()

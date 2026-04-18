"""
collect_data.py
================
每日数据采集脚本 · 零成本数据源

运行时机：每天 SGT 09:00 前由 GitHub Actions 触发

数据源（全部免费）：
1. Google News RSS  —— 品牌媒体提及量 + 标题 + URL
2. Yahoo Finance    —— NOAH 股价 + 交易量
3. Reddit JSON API  —— 社群提及（无需密钥的公开端点）
4. PRNewswire RSS   —— 官方新闻稿追踪

输出：data/YYYY-MM-DD.json
"""

import json
import os
import sys
import re
from datetime import datetime, timedelta
from urllib.parse import quote
import feedparser
import requests
import yfinance as yf
import pytz

SGT = pytz.timezone("Asia/Singapore")
TODAY = datetime.now(SGT).strftime("%Y-%m-%d")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ===================================================================
# 配置：监测关键词矩阵
# ===================================================================
KEYWORDS = {
    # 主品牌
    "noah_holdings_en": ["Noah Holdings"],
    "noah_holdings_zh": ["诺亚财富", "诺亚控股"],
    # 子品牌
    "sub_olive": ["Olive Asset Management"],
    "sub_ark": ["ARK Wealth Management"],
    "sub_gopher": ["Gopher Asset Management", "歌斐资产"],
    "sub_glory": ["Glory Family Heritage", "荣耀传承"],
    "sub_iark": ["iARK"],
    # 核心人物
    "people_norah": ["Norah Wang", "汪静波"],
    "people_zander": ["Zander Yin", "殷哲"],
    # 竞品
    "comp_arta": ["Arta Finance"],
    "comp_ubs_apac": ["UBS Asia wealth", "UBS Singapore wealth"],
    # 议题
    "topic_hnw_chinese": ["overseas Chinese wealth management", "华人财富管理"],
    "topic_family_office": ["Singapore family office", "家族办公室"],
}

# 情感关键词（简易规则，第一版够用）
POSITIVE_WORDS = [
    "award", "best", "leading", "honor", "top", "innovation", "success",
    "growth", "excellence", "strong", "profit", "dividend", "outperform",
    "获奖", "领先", "卓越", "创新", "增长", "优秀", "第一", "成功", "突破",
]
NEGATIVE_WORDS = [
    "fraud", "lawsuit", "loss", "scandal", "fine", "penalty", "decline",
    "drop", "concern", "risk", "warning", "fail", "controversy",
    "诈骗", "亏损", "违规", "处罚", "诉讼", "争议", "下跌", "风险", "丑闻",
]

# ===================================================================
# 数据采集模块
# ===================================================================

def fetch_google_news(query: str, max_items: int = 20) -> list:
    """通过 Google News RSS 抓取最近新闻（免费，无需密钥）"""
    # 限制最近24小时，中文+英文
    url = f"https://news.google.com/rss/search?q={quote(query)}+when:1d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            pub = entry.get("published", "")
            source = ""
            if hasattr(entry, "source"):
                source = entry.source.get("title", "") if isinstance(entry.source, dict) else ""
            items.append({
                "title": title,
                "url": link,
                "published": pub,
                "source": source,
                "query": query,
            })
        return items
    except Exception as e:
        print(f"[WARN] Google News fetch failed for '{query}': {e}", file=sys.stderr)
        return []


def fetch_stock_data(ticker: str = "NOAH") -> dict:
    """从 Yahoo Finance 拉取股价"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return {"error": "no data"}
        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else latest
        return {
            "ticker": ticker,
            "price": round(float(latest["Close"]), 2),
            "prev_close": round(float(prev["Close"]), 2),
            "change_pct": round((float(latest["Close"]) - float(prev["Close"])) / float(prev["Close"]) * 100, 2),
            "volume": int(latest["Volume"]),
            "high_52w": round(float(stock.info.get("fiftyTwoWeekHigh", 0) or 0), 2),
            "low_52w": round(float(stock.info.get("fiftyTwoWeekLow", 0) or 0), 2),
        }
    except Exception as e:
        print(f"[WARN] Yahoo Finance failed: {e}", file=sys.stderr)
        return {"error": str(e)}


def fetch_reddit_mentions(query: str, subreddits: list = None) -> list:
    """Reddit 搜索 API（公开，无需密钥，加 User-Agent 即可）"""
    if subreddits is None:
        subreddits = ["ChineseAmerican", "fatFIRE", "singapore", "personalfinance", "investing"]
    results = []
    headers = {"User-Agent": "NoahBrandMonitor/1.0"}
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/search.json?q={quote(query)}&restrict_sr=1&sort=new&t=day&limit=10"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            data = r.json()
            for post in data.get("data", {}).get("children", []):
                p = post.get("data", {})
                results.append({
                    "subreddit": sub,
                    "title": p.get("title", ""),
                    "url": "https://www.reddit.com" + p.get("permalink", ""),
                    "score": p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                    "created_utc": p.get("created_utc", 0),
                })
        except Exception as e:
            print(f"[WARN] Reddit r/{sub} failed for '{query}': {e}", file=sys.stderr)
    return results


def score_sentiment(text: str) -> int:
    """简易情感打分：+1 正面词、-1 负面词"""
    if not text:
        return 0
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w.lower() in text_lower)
    neg = sum(1 for w in NEGATIVE_WORDS if w.lower() in text_lower)
    return pos - neg


def classify_sentiment(items: list) -> dict:
    """对一批内容分类正/中/负"""
    pos, neu, neg = 0, 0, 0
    for item in items:
        s = score_sentiment(item.get("title", ""))
        if s > 0:
            pos += 1
        elif s < 0:
            neg += 1
        else:
            neu += 1
    total = pos + neu + neg
    return {
        "positive": pos,
        "neutral": neu,
        "negative": neg,
        "total": total,
        "pos_pct": round(pos / total * 100, 1) if total else 0,
        "neg_pct": round(neg / total * 100, 1) if total else 0,
    }


# ===================================================================
# 主流程
# ===================================================================

def collect_all() -> dict:
    """统一采集所有数据并输出结构化字典"""
    print(f"[{TODAY}] 开始采集数据...")

    snapshot = {
        "date": TODAY,
        "collected_at": datetime.now(SGT).isoformat(),
        "metrics": {},
        "news": {},
        "reddit": {},
        "stock": {},
        "sentiment": {},
        "top_mentions": [],
    }

    # 1. 新闻采集
    all_news = []
    for key, queries in KEYWORDS.items():
        combined = []
        for q in queries:
            combined.extend(fetch_google_news(q, max_items=15))
        # 按 URL 去重
        seen = set()
        deduped = []
        for n in combined:
            if n["url"] not in seen:
                seen.add(n["url"])
                deduped.append(n)
        snapshot["news"][key] = {
            "count": len(deduped),
            "items": deduped[:10],
        }
        all_news.extend(deduped)
        print(f"  [新闻] {key}: {len(deduped)} 条")

    # 2. 股价
    snapshot["stock"] = fetch_stock_data("NOAH")
    print(f"  [股价] NOAH: ${snapshot['stock'].get('price', 'N/A')}")

    # 3. Reddit
    for key in ["noah_holdings_en", "comp_arta", "topic_hnw_chinese"]:
        query_list = KEYWORDS[key]
        all_reddit = []
        for q in query_list:
            all_reddit.extend(fetch_reddit_mentions(q))
        snapshot["reddit"][key] = {
            "count": len(all_reddit),
            "items": all_reddit[:8],
        }
        print(f"  [Reddit] {key}: {len(all_reddit)} 条")

    # 4. 汇总核心指标（用于 Top3 提升/下降计算）
    snapshot["metrics"] = {
        # 品牌主流量
        "news_noah_en": snapshot["news"]["noah_holdings_en"]["count"],
        "news_noah_zh": snapshot["news"]["noah_holdings_zh"]["count"],
        # 子品牌
        "news_olive": snapshot["news"]["sub_olive"]["count"],
        "news_ark": snapshot["news"]["sub_ark"]["count"],
        "news_gopher": snapshot["news"]["sub_gopher"]["count"],
        "news_glory": snapshot["news"]["sub_glory"]["count"],
        "news_iark": snapshot["news"]["sub_iark"]["count"],
        # 人物
        "news_norah": snapshot["news"]["people_norah"]["count"],
        "news_zander": snapshot["news"]["people_zander"]["count"],
        # 竞品
        "news_arta": snapshot["news"]["comp_arta"]["count"],
        "news_ubs_apac": snapshot["news"]["comp_ubs_apac"]["count"],
        # 议题
        "news_topic_hnw": snapshot["news"]["topic_hnw_chinese"]["count"],
        "news_topic_fo": snapshot["news"]["topic_family_office"]["count"],
        # 股价
        "stock_price": snapshot["stock"].get("price", 0),
        "stock_change_pct": snapshot["stock"].get("change_pct", 0),
        "stock_volume": snapshot["stock"].get("volume", 0),
        # Reddit
        "reddit_noah": snapshot["reddit"]["noah_holdings_en"]["count"],
        "reddit_arta": snapshot["reddit"]["comp_arta"]["count"],
        "reddit_topic": snapshot["reddit"]["topic_hnw_chinese"]["count"],
    }

    # 5. 情感分析（对主品牌新闻）
    noah_news_all = snapshot["news"]["noah_holdings_en"]["items"] + snapshot["news"]["noah_holdings_zh"]["items"]
    snapshot["sentiment"] = classify_sentiment(noah_news_all)
    snapshot["metrics"]["sentiment_pos_pct"] = snapshot["sentiment"]["pos_pct"]
    snapshot["metrics"]["sentiment_neg_pct"] = snapshot["sentiment"]["neg_pct"]
    print(f"  [情感] 正面 {snapshot['sentiment']['pos_pct']}% / 负面 {snapshot['sentiment']['neg_pct']}%")

    # 6. Top 影响力提及（按信号强度排序，供邮件引用）
    top = []
    for n in all_news:
        # 信号强度 = 来源优先级（权威源加分）+ 情感分
        src = (n.get("source") or "").lower()
        weight = 1
        if any(auth in src for auth in ["bloomberg", "reuters", "ft.com", "wsj",
                                         "financial times", "prnewswire", "asian private banker",
                                         "euromoney", "caixin", "21世纪", "财新"]):
            weight = 3
        elif any(med in src for med in ["yahoo", "seeking alpha", "investing.com"]):
            weight = 2
        sent = score_sentiment(n["title"])
        top.append({**n, "weight": weight, "sentiment": sent})

    # 按 weight 降序，再按 sentiment 绝对值（重要正面/负面都保留）
    top.sort(key=lambda x: (x["weight"], abs(x["sentiment"])), reverse=True)
    snapshot["top_mentions"] = top[:10]

    return snapshot


def save_snapshot(snapshot: dict) -> str:
    """保存今日快照"""
    path = os.path.join(DATA_DIR, f"{TODAY}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"[OK] 已保存至 {path}")
    return path


if __name__ == "__main__":
    snap = collect_all()
    save_snapshot(snap)

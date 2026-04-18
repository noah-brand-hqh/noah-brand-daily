"""
compute_rankings.py
===================
对比今日与前一天的数据，计算每个指标的变化百分比，
输出 Top 3 提升 + Top 3 下降 + 舆情风险/机会。

输出：data/rankings_YYYY-MM-DD.json
"""

import json
import os
import sys
from datetime import datetime, timedelta
import pytz

SGT = pytz.timezone("Asia/Singapore")
TODAY = datetime.now(SGT).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(SGT) - timedelta(days=1)).strftime("%Y-%m-%d")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# 指标可读标签 —— 中文友好
METRIC_LABELS = {
    "news_noah_en": ("Noah Holdings 英文媒体提及", "brand_core"),
    "news_noah_zh": ("诺亚财富中文媒体提及", "brand_core"),
    "news_olive": ("Olive 子品牌曝光", "sub_brand"),
    "news_ark": ("ARK Wealth 子品牌曝光", "sub_brand"),
    "news_gopher": ("歌斐 Gopher 子品牌曝光", "sub_brand"),
    "news_glory": ("荣耀传承 Glory 子品牌曝光", "sub_brand"),
    "news_iark": ("iARK 平台曝光", "sub_brand"),
    "news_norah": ("汪静波 Norah 个人IP", "leadership"),
    "news_zander": ("殷哲 Zander 个人IP", "leadership"),
    "news_arta": ("Arta Finance 竞品声量", "competitor"),
    "news_ubs_apac": ("UBS 亚太竞品声量", "competitor"),
    "news_topic_hnw": ("华人财富议题讨论", "topic"),
    "news_topic_fo": ("家办议题讨论", "topic"),
    "stock_price": ("NOAH 股价", "market"),
    "stock_change_pct": ("NOAH 单日涨跌幅", "market"),
    "stock_volume": ("NOAH 成交量", "market"),
    "reddit_noah": ("Reddit 诺亚自然提及", "community"),
    "reddit_arta": ("Reddit Arta 竞品讨论", "competitor"),
    "reddit_topic": ("Reddit 华人财富讨论", "topic"),
    "sentiment_pos_pct": ("全网正面情感占比", "sentiment"),
    "sentiment_neg_pct": ("全网负面情感占比", "sentiment"),
}

# 某些指标"下降"才是好事（如负面情感、竞品声量）
INVERTED_METRICS = {"sentiment_neg_pct", "news_arta", "news_ubs_apac", "reddit_arta"}


def load_snapshot(date_str: str):
    path = os.path.join(DATA_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_change(today_val, yest_val):
    """计算百分比变化，处理除零和 None"""
    if today_val is None or yest_val is None:
        return None
    try:
        today_val = float(today_val)
        yest_val = float(yest_val)
    except (TypeError, ValueError):
        return None
    if yest_val == 0:
        if today_val == 0:
            return 0
        return 999  # 从 0 到 N 视为极大增长
    return round((today_val - yest_val) / abs(yest_val) * 100, 1)


def rank_changes(today_snap: dict, yest_snap: dict) -> dict:
    """核心排序逻辑"""
    if not yest_snap:
        print("[INFO] 前一日无数据，使用 0 作为基线")
        yest_metrics = {k: 0 for k in today_snap["metrics"]}
    else:
        yest_metrics = yest_snap.get("metrics", {})

    today_metrics = today_snap.get("metrics", {})
    changes = []

    for key, today_val in today_metrics.items():
        yest_val = yest_metrics.get(key, 0)
        pct = compute_change(today_val, yest_val)
        if pct is None:
            continue

        label, category = METRIC_LABELS.get(key, (key, "other"))
        is_inverted = key in INVERTED_METRICS

        # "品牌提升"定义：
        # - 正向指标：上升 = 好 = 正分
        # - 反向指标：下降 = 好 = 正分（如负面情感下降是好事）
        if is_inverted:
            brand_impact = -pct
        else:
            brand_impact = pct

        changes.append({
            "metric": key,
            "label": label,
            "category": category,
            "today": today_val,
            "yesterday": yest_val,
            "change_pct": pct,
            "brand_impact_score": brand_impact,
            "is_inverted": is_inverted,
        })

    # 过滤掉变化太小的（噪音）
    meaningful = [c for c in changes if abs(c["change_pct"]) >= 1 or c["today"] != c["yesterday"]]

    # Top 3 提升（按 brand_impact_score 降序）
    top_gains = sorted(meaningful, key=lambda x: x["brand_impact_score"], reverse=True)[:5]
    top_gains = [c for c in top_gains if c["brand_impact_score"] > 0][:3]

    # Top 3 下降（按 brand_impact_score 升序）
    top_losses = sorted(meaningful, key=lambda x: x["brand_impact_score"])[:5]
    top_losses = [c for c in top_losses if c["brand_impact_score"] < 0][:3]

    return {
        "date": TODAY,
        "compared_to": YESTERDAY,
        "top_gains": top_gains,
        "top_losses": top_losses,
        "all_changes": changes,
    }


def extract_sentiment_highlights(today_snap: dict) -> dict:
    """从新闻中提取情感亮点和风险点（供邮件引用）"""
    positive = []
    negative = []

    # 收集所有新闻
    all_news = []
    for key, val in today_snap.get("news", {}).items():
        if key.startswith("noah_") or key.startswith("sub_") or key.startswith("people_"):
            all_news.extend(val.get("items", []))

    # 按情感分类
    from collect_data import score_sentiment
    seen = set()
    for n in all_news:
        url = n.get("url", "")
        if url in seen:
            continue
        seen.add(url)
        s = score_sentiment(n.get("title", ""))
        if s > 0:
            positive.append({**n, "sentiment": s})
        elif s < 0:
            negative.append({**n, "sentiment": s})

    positive.sort(key=lambda x: x["sentiment"], reverse=True)
    negative.sort(key=lambda x: x["sentiment"])

    return {
        "positive_signals": positive[:5],
        "negative_signals": negative[:5],
    }


def generate_suggestions(rankings: dict, today_snap: dict) -> list:
    """
    基于 Top3 下降 + 负面舆情 + 数据缺口 生成 Top 10 建议。
    这不是模板 —— 是基于当天数据的动态推理。
    """
    suggestions = []
    gains = rankings["top_gains"]
    losses = rankings["top_losses"]
    metrics = today_snap["metrics"]

    # --- 从下降项生成补救建议 ---
    for loss in losses:
        cat = loss["category"]
        label = loss["label"]
        if cat == "sub_brand":
            suggestions.append({
                "priority": "HIGH",
                "title": f"补救 · {label} 声量下滑 {abs(loss['change_pct'])}%",
                "action": f"在 LinkedIn 和 PRNewswire 推送 1 条涉及 {label} 的原创观点，并同步转译中文版",
                "why": f"子品牌声量断档会让 AI 在相关细分问题上（如 {label} 相关 query）降权诺亚",
                "owner": "品牌 + 业务线负责人",
                "timeline": "3 天内",
            })
        elif cat == "competitor":
            suggestions.append({
                "priority": "MED",
                "title": f"竞争监控 · {label} 在下降（好事）",
                "action": "借势补位：在其声量真空期发布一篇同议题诺亚观点文章",
                "why": "搜索算法的热点空窗可以被占领",
                "owner": "内容团队",
                "timeline": "一周内",
            })
        elif cat == "sentiment" and loss["metric"] == "sentiment_pos_pct":
            suggestions.append({
                "priority": "HIGH",
                "title": f"情感恢复 · 正面占比跌至 {loss['today']}%",
                "action": "盘点当日负面新闻源头；若是承兴类历史遗留，发布《合规升级年报》对冲；若是新议题，启动 24 小时应对声明",
                "why": "AI 模型对近期情感倾向权重高，连续 3 天负向会结构性影响品牌叙事",
                "owner": "品牌 + 法务",
                "timeline": "24 小时内",
            })

    # --- 从上升项生成放大建议 ---
    for gain in gains:
        cat = gain["category"]
        label = gain["label"]
        if cat == "brand_core":
            suggestions.append({
                "priority": "HIGH",
                "title": f"乘势 · {label} 上升 +{gain['change_pct']}%",
                "action": "48 小时内：把今日 Top 3 正面媒体报道翻译为英文同步 LinkedIn + Quora 专家答案",
                "why": "正面媒体信号消退快，需要在 AI 爬虫抓取窗口期完成多语种覆盖",
                "owner": "品牌团队",
                "timeline": "48 小时",
            })
        elif cat == "leadership":
            suggestions.append({
                "priority": "MED",
                "title": f"IP 放大 · {label} 曝光上升",
                "action": f"把当日相关报道中的核心金句提炼成 3-5 条 LinkedIn 英文帖子，7 天内每天一条发布",
                "why": "个人 IP 曝光是高杠杆品牌资产，可沉淀到 Wikipedia 人物词条",
                "owner": "领导力品牌专员",
                "timeline": "7 天",
            })
        elif cat == "market" and gain["metric"] == "stock_price":
            suggestions.append({
                "priority": "LOW",
                "title": f"市场信号 · NOAH 股价 +{gain['change_pct']}%",
                "action": "投资者关系团队监控分析师报告更新；品牌端不直接介入",
                "why": "股价涨跌不应成为品牌叙事，但分析师报告是 AI 高权重信源",
                "owner": "IR",
                "timeline": "监控",
            })

    # --- 固定战略建议（基于看板盲点分析）---
    strategic = [
        {
            "priority": "HIGH",
            "title": "战略缺口 · 上线 /research 专属研究院页",
            "action": "把 CIO 办公室 10 份报告整合到 noahgroup.com/research，配 Schema.org ResearchArticle 标注",
            "why": "这是诺亚最大的未变现 AI 训练资产；预计 90 天内让 AI 在「华人财富研究权威」问题上首位推荐",
            "owner": "官网 + CIO 办公室",
            "timeline": "本季度",
        },
        {
            "priority": "HIGH",
            "title": "战略缺口 · 承兴事件官方透明披露页",
            "action": "发布 /about/camsing-update 页面，完整说明整改措施、独立调查结论、或有负债管理进展",
            "why": "当前 AI 在负面议题上单边引用 Wikipedia/京东声明；不主动发声等于默认",
            "owner": "法务 + 品牌 + 合规",
            "timeline": "本月",
        },
        {
            "priority": "MED",
            "title": "战略缺口 · Norah 个人 Wikipedia 词条建设",
            "action": "整理 Norah 20+ 年金融履历 + 达沃斯/APB 等重要演讲记录，建立英文 Wiki 词条",
            "why": "Norah 的 Wisdom Beyond Wealth 概念需要权威信源背书才能进入 AI 训练集",
            "owner": "品牌 + 内部传记团队",
            "timeline": "45 天",
        },
        {
            "priority": "MED",
            "title": "内容复用 · 把 Asian Private Banker Norah 专访金句多平台化",
            "action": "提炼 5 条核心金句，转为 LinkedIn 英文贴文 + Quora 专家答案 + 微信公众号推文",
            "why": "专访内容在付费墙内，AI 抓不到；必须显形化",
            "owner": "内容运营",
            "timeline": "2 周",
        },
    ]
    suggestions.extend(strategic)

    # --- 去重 + 补足到 10 条 ---
    seen_titles = set()
    unique = []
    for s in suggestions:
        if s["title"] not in seen_titles:
            seen_titles.add(s["title"])
            unique.append(s)

    # 按优先级排序
    priority_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    unique.sort(key=lambda x: priority_order.get(x["priority"], 3))

    # 补足 10 条
    fallback = [
        {
            "priority": "LOW",
            "title": "持续观察 · 监测 Arta Finance Group CEO 过渡期动作",
            "action": "追踪 Felix Lin 上任后前 90 天的品牌定位变化",
            "why": "竞品领导层变动期是插位的最佳窗口",
            "owner": "竞品情报",
            "timeline": "90 天跟踪",
        },
        {
            "priority": "LOW",
            "title": "基础设施 · 检查 robots.txt 对 GPTBot / ClaudeBot / PerplexityBot 放行",
            "action": "技术团队 10 分钟即可完成",
            "why": "AI 爬虫放行是零成本最高杠杆动作",
            "owner": "技术",
            "timeline": "本周",
        },
    ]
    for f in fallback:
        if len(unique) >= 10:
            break
        if f["title"] not in seen_titles:
            unique.append(f)
            seen_titles.add(f["title"])

    return unique[:10]


def main():
    today_snap = load_snapshot(TODAY)
    if not today_snap:
        print(f"[ERROR] 今日数据未找到：{TODAY}.json", file=sys.stderr)
        sys.exit(1)

    yest_snap = load_snapshot(YESTERDAY)
    rankings = rank_changes(today_snap, yest_snap)
    highlights = extract_sentiment_highlights(today_snap)
    suggestions = generate_suggestions(rankings, today_snap)

    result = {
        **rankings,
        "sentiment_highlights": highlights,
        "suggestions_top10": suggestions,
        "raw_stock": today_snap.get("stock", {}),
        "raw_sentiment": today_snap.get("sentiment", {}),
        "top_mentions": today_snap.get("top_mentions", []),
    }

    out_path = os.path.join(DATA_DIR, f"rankings_{TODAY}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] 排序已保存 {out_path}")
    print(f"  Top 3 提升: {[g['label'] for g in rankings['top_gains']]}")
    print(f"  Top 3 下降: {[l['label'] for l in rankings['top_losses']]}")
    print(f"  建议数量: {len(suggestions)}")


if __name__ == "__main__":
    main()

"""
generate_and_send.py
====================
1. 读取 compute_rankings.py 的输出
2. 渲染 HTML 邮件模板
3. 通过 Gmail SMTP 发送至收件人

依赖环境变量（GitHub Secrets 中设置）：
- GMAIL_USER          —— 发件 Gmail 地址
- GMAIL_APP_PASSWORD  —— Gmail 应用专用密码（非登录密码）
- RECIPIENT_EMAIL     —— 收件人 (huqianhui@arkwealth.sg)
- DASHBOARD_URL       —— 看板的 GitHub Pages 公网地址
"""

import json
import os
import sys
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from jinja2 import Environment, FileSystemLoader
import pytz

SGT = pytz.timezone("Asia/Singapore")
TODAY = datetime.now(SGT).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(SGT) - timedelta(days=1)).strftime("%Y-%m-%d")

# Human-readable dates
TODAY_HUMAN = datetime.now(SGT).strftime("%Y年%m月%d日 周" + "一二三四五六日"[datetime.now(SGT).weekday()])
YESTERDAY_HUMAN = (datetime.now(SGT) - timedelta(days=1)).strftime("%m月%d日")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TEMPLATE_DIR = os.path.join(ROOT, "email_templates")


def load_rankings():
    path = os.path.join(DATA_DIR, f"rankings_{TODAY}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"排序数据未找到：{path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_snapshot():
    path = os.path.join(DATA_DIR, f"{TODAY}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_email(rankings: dict, snapshot: dict, dashboard_url: str) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    tpl = env.get_template("daily_email.html")

    # 汇总媒体提及总数
    total_mentions = sum(
        v.get("count", 0)
        for k, v in snapshot.get("news", {}).items()
        if k.startswith(("noah_", "sub_", "people_"))
    )

    # 股价字段加上默认值防御 —— Yahoo Finance 偶尔会返回空
    raw_stock = rankings.get("raw_stock", {}) or {}
    stock_safe = {
        "price": raw_stock.get("price", "N/A"),
        "prev_close": raw_stock.get("prev_close", "N/A"),
        "change_pct": raw_stock.get("change_pct", 0) or 0,
        "volume": raw_stock.get("volume", 0),
        "high_52w": raw_stock.get("high_52w", 0),
        "low_52w": raw_stock.get("low_52w", 0),
        "unavailable": "error" in raw_stock or not raw_stock.get("price"),
    }

    raw_sentiment = rankings.get("raw_sentiment", {}) or {}
    sentiment_safe = {
        "pos_pct": raw_sentiment.get("pos_pct", 0) or 0,
        "neg_pct": raw_sentiment.get("neg_pct", 0) or 0,
        "total": raw_sentiment.get("total", 0) or 0,
    }

    html = tpl.render(
        date=TODAY,
        date_human=TODAY_HUMAN,
        yesterday_human=YESTERDAY_HUMAN,
        collected_at=snapshot.get("collected_at", ""),
        dashboard_url=dashboard_url,
        stock=stock_safe,
        sentiment=sentiment_safe,
        total_mentions=total_mentions,
        top_gains=rankings.get("top_gains", []),
        top_losses=rankings.get("top_losses", []),
        positive_signals=rankings.get("sentiment_highlights", {}).get("positive_signals", []),
        negative_signals=rankings.get("sentiment_highlights", {}).get("negative_signals", []),
        top_mentions=rankings.get("top_mentions", []),
        suggestions_top10=rankings.get("suggestions_top10", []),
    )
    return html


def send_email(html_body: str):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL", "huqianhui@arkwealth.sg")

    if not gmail_user or not gmail_pass:
        print("[ERROR] 未设置 GMAIL_USER / GMAIL_APP_PASSWORD 环境变量", file=sys.stderr)
        print("[INFO] 未配置 SMTP，仅生成 HTML 预览（不发送）", file=sys.stderr)
        preview_path = os.path.join(ROOT, "last_email_preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"[OK] 邮件预览已保存：{preview_path}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"【诺亚品牌晨报】{TODAY_HUMAN}"
    msg["From"] = f"Noah Brand Daily <{gmail_user}>"
    msg["To"] = recipient
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    # 附加纯文本 fallback
    plain_fallback = (
        f"诺亚品牌晨报 {TODAY_HUMAN}\n\n"
        f"邮件包含丰富的 HTML 内容，请使用支持 HTML 的客户端查看。\n\n"
        f"完整看板：{os.environ.get('DASHBOARD_URL', '')}"
    )
    msg.attach(MIMEText(plain_fallback, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)
        print(f"[OK] 已发送至 {recipient}")
        return True
    except Exception as e:
        print(f"[ERROR] 邮件发送失败: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    rankings = load_rankings()
    snapshot = load_snapshot()
    dashboard_url = os.environ.get(
        "DASHBOARD_URL",
        "https://YOUR-USERNAME.github.io/noah-brand-daily/"
    )

    html = render_email(rankings, snapshot, dashboard_url)

    # 总是先本地保存一份预览（方便调试）
    preview_path = os.path.join(ROOT, "last_email_preview.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] 邮件预览已保存：{preview_path}")

    send_email(html)


if __name__ == "__main__":
    main()

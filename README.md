# 诺亚品牌建设日报 · Noah Brand Daily

> 每日 SGT 09:00 自动生成品牌建设晨报并发送至 `huqianhui@arkwealth.sg`
> 零维护成本 · 零部署成本（GitHub Actions + GitHub Pages 全免费）

---

## 📦 这套代码做什么

每天早上 9 点，你会在邮箱收到一封结构化的品牌晨报，包含：

1. **核心快照** —— 股价 / 媒体提及总量 / 正面情感占比 / 看板链接
2. **前 24 小时品牌提升 TOP 3** —— 显示哪些子品牌 / 人物 / 议题曝光上升
3. **前 24 小时品牌下降 TOP 3** —— 哪些指标需要关注
4. **舆情亮点** —— 正面 + 风险各 3 条，附原文链接
5. **高影响力提及 Feed** —— 权威媒体对诺亚的报道
6. **落地清单 TOP 10** —— 基于今日数据动态生成、带优先级和责任人的行动建议
7. **完整看板链接** —— 直达 GitHub Pages 托管的动态看板 v2

---

## 🏗 系统架构

```
GitHub 仓库（公开或私有均可）
├── dashboard/index.html                  ← GitHub Pages 托管的看板
├── data/
│   ├── 2026-04-18.json                   ← 每日原始数据快照
│   ├── rankings_2026-04-18.json          ← 每日对比排序结果
│   └── ...                               ← 自动累积，提供历史基线
├── scripts/
│   ├── collect_data.py                   ← 1. 采集数据（Google News/Yahoo Finance/Reddit）
│   ├── compute_rankings.py               ← 2. 对比昨日、排序 Top3
│   ├── generate_and_send.py              ← 3. 渲染 HTML + Gmail SMTP 发送
│   └── run_daily.py                      ← 主编排入口
├── email_templates/daily_email.html      ← 邮件 HTML 模板
└── .github/workflows/daily.yml           ← 每天 UTC 01:00 (SGT 09:00) 自动触发
```

---

## 🚀 30-45 分钟部署指南

### 第一步：注册 GitHub 账号（5 分钟）

1. 访问 <https://github.com/signup>
2. 用你的工作邮箱注册，用户名建议使用 `noah-brand-xxx` 或个人名（所有人都能在 URL 里看到）
3. 完成邮箱验证

### 第二步：创建仓库（3 分钟）

1. 右上角 `+` → **New repository**
2. 填写：
   - Repository name: `noah-brand-daily`
   - Description: `诺亚品牌建设每日监测`
   - **选择 Public**（GitHub Pages 免费版必须 public；若介意可选 Private 但需付费 GitHub Pro $4/月）
   - 勾选 "Add a README file"（可选）
3. 点击 **Create repository**

### 第三步：上传项目文件（5 分钟）

**方法 A · 网页拖拽上传（推荐新手）**

1. 进入刚创建的仓库主页
2. 点击 **Add file → Upload files**
3. 把本项目的所有文件夹和文件**拖入**浏览器（保持目录结构）：
   ```
   dashboard/
   data/
   email_templates/
   scripts/
   .github/
   .gitignore
   requirements.txt
   README.md
   ```
4. 底部提交信息填 `Initial deployment`
5. 点击 **Commit changes**

**方法 B · 用 GitHub Desktop（推荐长期维护）**

1. 下载 <https://desktop.github.com/>
2. 克隆仓库到本地 → 把项目文件夹内容复制进去 → Commit → Push

### 第四步：开启 GitHub Pages（5 分钟）

让你的看板拥有公网 URL。

1. 仓库主页点 **Settings** → 左栏 **Pages**
2. **Source** 选 "Deploy from a branch"
3. **Branch** 选 `main`，文件夹选 `/dashboard`
4. 点 **Save**
5. 等 1-2 分钟，页面顶部会显示：
   ```
   Your site is live at https://<你的用户名>.github.io/noah-brand-daily/
   ```
6. **记下这个 URL**，下一步要用

### 第五步：生成 Gmail 应用专用密码（10 分钟）

⚠️ **切勿使用你的 Gmail 登录密码**。必须生成专门的"应用密码"。

1. 如果你的 Gmail **未开启两步验证**：
   - 访问 <https://myaccount.google.com/security>
   - 找到 "2-Step Verification" 点击开启，按流程完成

2. 开启两步验证后：
   - 访问 <https://myaccount.google.com/apppasswords>
   - App name 填 `Noah Brand Daily`
   - 点击 **Create**
   - Google 会显示一个 16 位密码（形如 `abcd efgh ijkl mnop`）
   - **立刻复制**，关闭后再也看不到了

3. 如果你的公司邮箱不是 Gmail，两个替代方案：
   - 注册一个临时 Gmail 小号专门用于发送
   - 换用 SendGrid（免费档 100 封/天，见文末附录）

### 第六步：配置 GitHub Secrets（5 分钟）

让代码能访问你的 Gmail 密码，同时不把密码提交到公开仓库。

1. 仓库主页点 **Settings** → 左栏 **Secrets and variables** → **Actions**
2. 点 **New repository secret**，依次添加这 4 个：

| Secret 名称 | 值 | 示例 |
|---|---|---|
| `GMAIL_USER` | 发件 Gmail 地址 | `your.name@gmail.com` |
| `GMAIL_APP_PASSWORD` | 第五步生成的 16 位密码 | `abcd efgh ijkl mnop` |
| `RECIPIENT_EMAIL` | 收件人 | `huqianhui@arkwealth.sg` |
| `DASHBOARD_URL` | 第四步的 Pages URL | `https://你的用户名.github.io/noah-brand-daily/` |

### 第七步：首次手动触发测试（3 分钟）

1. 仓库主页点 **Actions** 标签
2. 左栏选 **Noah Brand Daily Report**
3. 右侧点 **Run workflow → Run workflow**
4. 等约 2-3 分钟，刷新页面看到绿色 ✓ 表示成功
5. 检查 `huqianhui@arkwealth.sg` 收件箱（也可能被 Gmail 判为 "Promotions" 或 "Spam"，记得加入白名单）

### 第八步：确认定时任务激活（0 分钟）

完成第七步后，定时任务已自动激活。之后每天 SGT 09:00 会自动运行。

> ⚠️ **GitHub Actions 已知时序特性**：cron 可能延迟 5-30 分钟，平均约 10 分钟。如需精确到分钟，需要改用付费服务。一般品牌晨报不需要这种精度。

---

## 🧪 本地测试（可选）

如果想在部署前先本地测试：

```bash
git clone https://github.com/<你的用户名>/noah-brand-daily.git
cd noah-brand-daily

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export GMAIL_USER="your.name@gmail.com"
export GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
export RECIPIENT_EMAIL="huqianhui@arkwealth.sg"
export DASHBOARD_URL="https://你的用户名.github.io/noah-brand-daily/"

# 执行全流程
python scripts/run_daily.py

# 或者只跑采集（查看数据）
python scripts/collect_data.py

# 或者生成预览 HTML 但不发送
unset GMAIL_USER GMAIL_APP_PASSWORD
python scripts/run_daily.py
# 浏览器打开 last_email_preview.html 查看
```

---

## 🛠 日常维护

### 查看历史数据
进入仓库 `data/` 目录能看到每天的 JSON 文件。一年下来约 0.5-1MB，GitHub 免费账号 5GB 额度绰绰有余。

### 修改监测关键词
编辑 `scripts/collect_data.py` 顶部的 `KEYWORDS` 字典，提交后下次运行生效。

### 修改收件人 / 抄送多人
- 单收件人：改 `RECIPIENT_EMAIL` secret
- 多收件人：把 `scripts/generate_and_send.py` 中的 `msg["To"]` 改成 `"email1@x.com, email2@y.com"`

### 调整发送时间
编辑 `.github/workflows/daily.yml` 中的 cron：
```yaml
- cron: '0 1 * * *'   # UTC 01:00 = SGT 09:00（默认）
- cron: '30 0 * * *'  # UTC 00:30 = SGT 08:30
```
[在线校验 cron](https://crontab.guru/)

### 查看运行日志
Actions → 选某次运行 → 点步骤展开日志。每步都有清晰的中文输出。

### 若某天邮件没收到
1. Actions 页面查看是否有红色失败标记
2. 点开失败的 Run → 看日志定位到哪一步
3. 下载附件 `email-preview-xxx.zip` 看 HTML 内容是否正常生成

---

## 🔍 数据源说明

| 数据源 | 用途 | 免费额度 | 可靠性 |
|---|---|---|---|
| Google News RSS | 全网媒体提及 | 无限（但每次抓 1 天内） | ⭐⭐⭐⭐ |
| Yahoo Finance (yfinance) | NOAH 股价 | 无限 | ⭐⭐⭐ 偶有限流 |
| Reddit JSON API | 社群讨论 | 免密钥模式限速温和 | ⭐⭐⭐⭐ |

**已知限制：**
- Google News 对某些中文关键词返回结果少 —— 这是 Google 算法而非代码问题
- Yahoo Finance 偶尔返回空（如本次测试）—— 模板已加默认值防御，邮件会正常发出但股价字段显示为"—"
- Reddit 在欧盟 IP 可能受限 —— GitHub Actions 机器在美国，一般不受影响

**未来升级路径（付费，非必需）：**
- NewsAPI.org（$449/月 businesses 档，10k请求/天，更精准）
- Meltwater / Brandwatch（$2000+/月，完整舆情监测）
- 自建微博/微信爬虫（需要独立开发）

---

## 📧 附录：SendGrid 替代 Gmail（可选）

如果不想用 Gmail，SendGrid 免费档每天 100 封，适合企业场景：

1. 注册 <https://sendgrid.com>，免费档
2. Settings → API Keys → Create API Key
3. 修改 `scripts/generate_and_send.py` 中的 `send_email` 函数：

```python
import requests
def send_via_sendgrid(html_body):
    api_key = os.environ["SENDGRID_API_KEY"]
    data = {
        "personalizations": [{"to": [{"email": os.environ["RECIPIENT_EMAIL"]}]}],
        "from": {"email": os.environ["SENDGRID_SENDER"]},
        "subject": f"【诺亚品牌晨报】{TODAY_HUMAN}",
        "content": [{"type": "text/html", "value": html_body}],
    }
    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}"},
        json=data,
    )
    return r.status_code < 300
```

4. 在 GitHub Secrets 添加：
   - `SENDGRID_API_KEY`
   - `SENDGRID_SENDER`（验证过的发件邮箱）

---

## 📂 文件清单

```
noah-brand-daily/
├── README.md                                ← 你正在看的这个文件
├── requirements.txt                         ← Python 依赖（6 个包）
├── .gitignore                               ← Git 忽略规则
├── .github/workflows/daily.yml              ← GitHub Actions 定时任务
├── dashboard/index.html                     ← 看板 v2（GitHub Pages 入口）
├── email_templates/daily_email.html         ← 邮件 HTML 模板
├── scripts/
│   ├── collect_data.py                      ← 数据采集
│   ├── compute_rankings.py                  ← 对比排序
│   ├── generate_and_send.py                 ← 邮件生成 + 发送
│   └── run_daily.py                         ← 主编排
└── data/                                    ← 每日 JSON 数据（自动生成）
    ├── 2026-04-18.json
    └── rankings_2026-04-18.json
```

---

## 🆘 FAQ

**Q: 第一天运行时，昨日数据没有，怎么比？**
A: 代码已处理这个情况 —— 第一天所有指标的"昨日值"默认为 0，第二天起才会有真正的对比。

**Q: 我想把看板设为私有（仅内部访问）？**
A: GitHub Pages 的 Private 需要 GitHub Team 套餐（$4/用户/月）。或者部署到 Cloudflare Pages + Access 免费方案。

**Q: Gmail 发到公司邮箱进垃圾邮件怎么办？**
A: 让 IT 把 `<你的Gmail地址>` 加入白名单；或改用 SendGrid 配合企业域名验证。

**Q: 如何扩展加入微信公众号阅读量监测？**
A: 微信没有官方 API，需要用清博/新榜等付费服务。进入 `collect_data.py` 加一个 `fetch_wechat_metrics()` 函数对接即可。

**Q: 若我离职或换人负责，如何交接？**
A: 代码全在 GitHub，新同事接手时只需要：
1. 成为仓库 collaborator
2. 更新 GMAIL_USER 和 GMAIL_APP_PASSWORD 这 2 个 Secrets
3. 其他无需变动

---

## 📝 版本历史

- **v1.0** (2026-04-18) · 初始版本：Google News + Yahoo Finance + Reddit 三源 + Gmail SMTP + GitHub Actions cron

---

## 🤝 维护责任

- 代码生成：Claude (Anthropic)
- 业务需求：Noah / ARK Wealth Brand Team
- 数据源监控：若某数据源接口变更（一年内可能 1-2 次），对应修改 `collect_data.py`

---

Built with ❤️ for 诺亚品牌团队 · 2026

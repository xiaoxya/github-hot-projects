"""
GitHub Weekly Hot Projects — 获取 GitHub 每周热门项目并通过 Lark 机器人推送

用法：
  python github_hot.py

首次使用前请在 config.json 中填入你的 Lark Webhook 地址。
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

# ── 配置 ──────────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
GITHUB_API = "https://api.github.com/search/repositories"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        log.error("config.json 不存在！请先复制 config.example.json 并填入配置。")
        sys.exit(1)

    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)

    if not cfg.get("lark_webhook_url") or "在此填入" in cfg["lark_webhook_url"]:
        log.error("请先在 config.json 中配置 lark_webhook_url！")
        sys.exit(1)

    return cfg


# ── GitHub 数据获取 ───────────────────────────────────────────────────────

def fetch_hot_projects(top_n=10, language="", proxy=""):
    """
    通过 GitHub Search API 获取过去 7 天内创建、star 增长最快的仓库。

    参数：
        top_n: 返回前 N 个
        language: 语言过滤（如 "python"），留空不限
        proxy: 代理地址（如 "http://127.0.0.1:7890"），留空不使用

    返回：仓库信息列表
    """
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"created:>={since}"

    if language:
        query += f"+language:{language}"

    params = {"q": query, "sort": "stars", "order": "desc", "per_page": top_n}
    headers = {"Accept": "application/vnd.github.v3+json"}
    proxies = {"http": proxy, "https": proxy} if proxy else None

    log.info("正在从 GitHub API 获取数据...")
    log.info(f"查询: {query}")

    resp = requests.get(GITHUB_API, params=params, headers=headers, proxies=proxies, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    repos = []
    for item in data.get("items", []):
        repos.append({
            "name": item["full_name"],
            "url": item["html_url"],
            "description": item.get("description") or "（暂无描述）",
            "stars": item["stargazers_count"],
            "forks": item["forks_count"],
            "language": item.get("language") or "N/A",
            "owner": item["owner"]["login"],
            "owner_url": item["owner"]["html_url"],
        })

    log.info(f"获取到 {len(repos)} 个项目")
    return repos


# ── Lark 消息推送 ────────────────────────────────────────────────────────

def build_lark_card(repos, top_n):
    """
    构建 Lark 消息卡片（官方 Card 格式，支持飞书/ Lark）。
    返回 POST 到 Webhook 的 JSON body。
    """
    # 标题行
    header_text = f"🔥 GitHub 本周热门项目 Top {top_n}"

    # 项目列表——每行一条
    elements = []
    for i, repo in enumerate(repos, 1):
        rank_icon = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"  {i}"

        stars_str = f"⭐ {repo['stars']:,}"
        forks_str = f"🍴 {repo['forks']:,}"
        lang_str = f"🔵 {repo['language']}"

        description = repo["description"]
        # 描述太长截断
        if len(description) > 120:
            description = description[:117] + "..."

        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**{rank_icon} [{repo['name']}]({repo['url']})**\n"
                    f"{description}\n"
                    f"{stars_str}　{forks_str}　{lang_str}"
                ),
            },
        })

        # 项目之间加一条分割线（最后一项不加）
        if i < len(repos):
            elements.append({"tag": "hr"})

    # 底部更新时间 + 来源提示
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"🕐 更新于 {now_str} · 数据来源: GitHub API"}],
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": header_text},
            "template": "blue",
        },
        "elements": elements,
    }

    return {"msg_type": "interactive", "card": card}


def send_to_lark(webhook_url, payload, proxy=""):
    """发送消息到 Lark 机器人"""
    proxies = {"http": proxy, "https": proxy} if proxy else None
    resp = requests.post(webhook_url, json=payload, proxies=proxies, timeout=30)
    result = resp.json()

    if result.get("code") == 0:
        log.info("✅ Lark 推送成功！")
    else:
        log.error(f"❌ Lark 推送失败: {result}")
        resp.raise_for_status()

    return result


# ── 主入口 ────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()

    top_n = cfg.get("top_n", 10)
    language = cfg.get("language", "")
    proxy = cfg.get("proxy", "")

    # 获取热门项目
    repos = fetch_hot_projects(top_n=top_n, language=language, proxy=proxy)
    if not repos:
        log.warning("没有获取到任何项目，跳过推送。")
        return

    # 构建卡片消息
    payload = build_lark_card(repos, top_n)

    # 推送到 Lark
    send_to_lark(cfg["lark_webhook_url"], payload, proxy=proxy)

    # 同时在终端打印摘要
    log.info("=" * 50)
    log.info(f"🔥 GitHub 本周热门 Top {top_n}")
    log.info("=" * 50)
    for i, repo in enumerate(repos, 1):
        print(f"\n{'🥇' if i==1 else '🥈' if i==2 else '🥉' if i==3 else f' {i}'}  "
              f"{repo['name']}")
        print(f"    ⭐ {repo['stars']:,}  🍴 {repo['forks']:,}  🔵 {repo['language']}")
        print(f"    {repo['url']}")
        print(f"    {repo['description'][:80]}")
    print()


if __name__ == "__main__":
    main()

"""
GitHub Weekly Hot Projects — 获取 GitHub 每周热门项目并通过 Lark / Bark 推送

用法：
  python github_hot.py

首次使用前请在 config.json 中填入至少一个推送渠道的配置（Lark 或 Bark）。
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
        log.error("config.json 不存在！")
        sys.exit(1)

    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)

    has_lark = cfg.get("lark_webhook_url") and "在此填入" not in cfg["lark_webhook_url"]
    has_bark = cfg.get("bark_device_key") and "在此填入" not in cfg["bark_device_key"]

    if not has_lark and not has_bark:
        log.error("请至少配置一个推送渠道（lark_webhook_url 或 bark_device_key）！")
        sys.exit(1)

    return cfg


# ── GitHub 数据获取 ───────────────────────────────────────────────────────

def fetch_hot_projects(top_n=20, language="", proxy=""):
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


# ── Bark 消息推送 ─────────────────────────────────────────────────────────

def build_bark_message(repos, top_n):
    """构建 Bark 推送的文本消息（简洁列表格式）"""
    lines = [f"🔥 GitHub 本周热门项目 Top {top_n}\n"]
    for i, repo in enumerate(repos, 1):
        rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}"
        desc = repo["description"]
        if len(desc) > 80:
            desc = desc[:77] + "..."
        lines.append(
            f"{rank} {repo['name']}\n"
            f"   ⭐{repo['stars']:,}  🍴{repo['forks']:,}  🔵{repo['language']}\n"
            f"   {desc}"
        )
    return "\n\n".join(lines)


def send_to_bark(device_key, repos, top_n, server="https://api.day.app", proxy=""):
    """
    发送消息到 Bark。

    使用 POST /push 接口（JSON body），避免长消息导致 URL 超长（431 错误）。

    参数：
        device_key: Bark 设备 Key
        repos: 仓库列表
        top_n: 用于标题的 Top N
        server: Bark 服务器地址（默认官方，可改为自建地址）
        proxy: 代理地址
    """
    title = f"🔥 GitHub 本周热门 Top {top_n}"
    body = build_bark_message(repos, top_n)

    url = f"{server}/push"
    payload = {
        "device_key": device_key,
        "title": title,
        "body": body,
        "sound": "birdsong",
        "isArchive": 1,
        "group": "GitHub热榜",
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None

    log.info("正在推送到 Bark...")
    resp = requests.post(url, json=payload, proxies=proxies, timeout=30)
    result = resp.json()

    if result.get("code") == 200:
        log.info(f"✅ Bark 推送成功！msg_id: {result.get('data', {}).get('msg_id', 'N/A')}")
    else:
        log.error(f"❌ Bark 推送失败: {result}")
        resp.raise_for_status()

    return result


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
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
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

    top_n = cfg.get("top_n", 20)
    language = cfg.get("language", "")
    proxy = cfg.get("proxy", "")

    # 获取热门项目
    repos = fetch_hot_projects(top_n=top_n, language=language, proxy=proxy)
    if not repos:
        log.warning("没有获取到任何项目，跳过推送。")
        return

    # ── 推送至各渠道 ──

    # Lark / 飞书
    lark_url = cfg.get("lark_webhook_url", "")
    if lark_url and "在此填入" not in lark_url:
        payload = build_lark_card(repos, top_n)
        send_to_lark(lark_url, payload, proxy=proxy)

    # Bark
    bark_key = cfg.get("bark_device_key", "")
    if bark_key and "在此填入" not in bark_key:
        bark_server = cfg.get("bark_server") or "https://api.day.app"
        send_to_bark(bark_key, repos, top_n, server=bark_server, proxy=proxy)

    # ── 同时在终端打印摘要 ──
    log.info("=" * 50)
    log.info(f"🔥 GitHub 本周热门 Top {top_n}")
    log.info("=" * 50)
    for i, repo in enumerate(repos, 1):
        rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f" {i}"
        print(f"\n{rank}  {repo['name']}")
        print(f"    ⭐ {repo['stars']:,}  🍴 {repo['forks']:,}  🔵 {repo['language']}")
        print(f"    {repo['url']}")
        print(f"    {repo['description'][:80]}")
    print()


if __name__ == "__main__":
    main()

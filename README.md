# 🔥 GitHub 热门项目推送

自动获取 **GitHub 每周最热门的项目**（按 Star 增长排序），支持通过 **Lark（飞书）机器人** 或 **Bark（iOS 推送）** 推送到你的设备。

## 效果预览

Lark 中收到的消息卡片效果：

```
╔══════════════════════════════════════════╗
║  🔥 GitHub 本周热门项目 Top 20          ║
╠══════════════════════════════════════════╣
║                                          ║
║  🥇 microsoft/xxx                        ║
║  一个 AI 驱动的代码助手                   ║
║  ⭐ 12,345  🍴 678  🔵 Python           ║
║  ─────────────────────────────           ║
║  🥈 openai/yyy                          ║
║  下一代推理模型                           ║
║  ⭐ 8,765  🍴 432  🔵 Rust             ║
║  ─────────────────────────────           ║
║  ...                                     ║
║  🕐 更新于 2026-07-26 09:00 UTC         ║
║  数据来源: GitHub API                    ║
╚══════════════════════════════════════════╝
```

## 快速开始

### 1. 安装依赖

本项目使用虚拟环境隔离依赖，无需系统安装。依赖已预装，如需重新安装：

```bash
cd /home/mo/claude/github-hot-projects
.venv/bin/pip install -r requirements.txt
```

### 2. 配置推送渠道

编辑 `config.json`，填入至少一个推送渠道的配置（也支持同时配置多个）。

#### Lark / 飞书

编辑 `config.json`，填入你的 Lark 机器人 Webhook 地址：

```json
{
  "lark_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/你的webhook地址"
}
```

> **如何获取 Lark Webhook？**
> 1. 在 Lark/飞书群中点击「设置」→「群机器人」→「添加机器人」
> 2. 选择「自定义机器人」（或 Webhook 机器人）
> 3. 复制生成的 Webhook URL
> 4. 粘贴到 `config.json` 中

#### Bark（iOS 推送）

Bark 是一款 iOS 推送工具，可以将消息直接推送到 iPhone/iPad。

```json
{
  "bark_device_key": "你的Bark设备Key"
}
```

> **如何获取 Bark Device Key？**
> 1. 在 App Store 下载 [Bark](https://apps.apple.com/app/bark-customed-notifications/id1403753865)
> 2. 打开 App，复制顶部显示的 Device Key
> 3. 粘贴到 `config.json` 的 `bark_device_key` 中
>
> 如需使用自建服务器，修改代码中的 `BARK_API` 变量即可。

### 3. 手动运行

```bash
./run.sh
```

或：

```bash
cd /home/mo/claude/github-hot-projects
.venv/bin/python github_hot.py
```

### 4. 设置定时推送（可选）

使用 cron 定时执行：

```bash
crontab -e
```

添加以下行（每天早上 9 点推送）：

```cron
0 9 * * * cd /home/mo/claude/github-hot-projects && ./run.sh >> run.log 2>&1
```

或每周一早上推送（周末热门汇总）：

```cron
0 9 * * 1 cd /home/mo/claude/github-hot-projects && ./run.sh >> run.log 2>&1
```

## 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `lark_webhook_url` | `""` | Lark/飞书 机器人 Webhook 地址 |
| `bark_device_key` | `""` | Bark iOS 推送 Device Key |
| `bark_server` | `https://api.day.app` | Bark 服务器地址（可改为自建地址） |
| `top_n` | `20` | 每次推送的项目数量 |
| `language` | `""` | 按编程语言过滤（如 `"python"`），留空不限 |
| `update_interval_hours` | `24` | 更新频率（仅参考，实际由 cron 控制） |
| `proxy` | `""` | HTTP 代理地址（如 `"http://127.0.0.1:7890"`），留空不使用 |

### 按语言过滤示例

如只想看 Python 项目：

```json
{
  "language": "python"
}
```

### 使用代理示例

```json
{
  "proxy": "http://127.0.0.1:7890"
}
```

## 部署到其他 Linux 主机

使用 `deploy.sh` 一键部署到远程主机：

```bash
# 基本用法
./deploy.sh user@host

# 自定义安装路径
./deploy.sh root@192.168.1.100 /home/pi/github-hot
```

脚本会自动完成：
1. rsync 同步项目文件（排除 venv、缓存、config.json）
2. 在目标主机创建 Python 虚拟环境并安装依赖
3. 生成 config.json 模板（不会覆盖已有配置）
4. 输出后续配置和 cron 设置命令

**手动部署**

如果不方便 rsync，也可以手动操作：

```bash
# 1. 打包
tar czf github-hot.tar.gz --exclude='.venv' --exclude='__pycache__' --exclude='.git' github-hot-projects/

# 2. 上传
scp github-hot.tar.gz user@host:/opt/

# 3. 在目标主机解压并安装
ssh user@host
cd /opt && tar xzf github-hot.tar.gz && cd github-hot-projects
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 4. 配置并测试
vim config.json
./run.sh
```

## 数据来源

- **API**: GitHub REST API (`/search/repositories`)
- **查询逻辑**: 过去 7 天内创建，按 Star 数量降序排列
- **限制**: GitHub API 未认证时每小时 60 次请求，认证后 5000 次/小时（本工具未使用 Token，个人使用绰绰有余）

## 文件结构

```
github-hot-projects/
├── github_hot.py       # 主程序
├── config.json         # 配置文件（不会被 git 跟踪）
├── requirements.txt    # Python 依赖
├── run.sh              # 一键运行脚本
├── deploy.sh           # 远程部署脚本
├── .venv/              # Python 虚拟环境
├── .gitignore
└── README.md           # 本文件
```

## 常见问题

<details>
<summary><b>Q: 运行报错 "ModuleNotFoundError: No module named requests"</b></summary>
请使用虚拟环境运行：<code>.venv/bin/python github_hot.py</code>，或先执行 <code>.venv/bin/pip install -r requirements.txt</code>
</details>

<details>
<summary><b>Q: Lark 没有收到消息</b></summary>
1. 检查 Webhook URL 是否正确
2. 确认机器人已在群中启用
3. 查看终端是否有错误输出
</details>

<details>
<summary><b>Q: 获取到的项目太少</b></summary>
GitHub API 可能返回少于 <code>top_n</code> 的项目，这是因为某些时间段内新项目较少。可以尝试调大 <code>created:>=</code> 的时间范围（修改代码中的 <code>days=7</code>）。
</details>

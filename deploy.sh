#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# deploy.sh — 将项目部署到远程 Linux 主机
#
# 用法:
#   ./deploy.sh user@host [remote_path]
#
# 示例:
#   ./deploy.sh root@192.168.1.100              # 默认路径 /opt/github-hot-projects
#   ./deploy.sh root@192.168.1.100 /home/pi/app  # 自定义路径
# ──────────────────────────────────────────────────────────
set -euo pipefail

REMOTE_TARGET="${1:-}"
REMOTE_PATH="${2:-/opt/github-hot-projects}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

if [[ -z "$REMOTE_TARGET" ]]; then
    echo "用法: ./deploy.sh user@host [remote_path]"
    echo ""
    echo "示例:"
    echo "  ./deploy.sh root@192.168.1.100"
    echo "  ./deploy.sh pi@raspberrypi.local /home/pi/github-hot"
    exit 1
fi

echo "============================================"
echo "  部署 GitHub 热门项目推送"
echo "  目标: ${REMOTE_TARGET}:${REMOTE_PATH}"
echo "============================================"
echo ""

# 1. rsync 项目文件（排除不需要的）
echo "📦 正在同步项目文件..."
rsync -avz --progress \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.git/' \
    --exclude 'config.json' \
    --exclude '*.log' \
    "${PROJECT_DIR}/" \
    "${REMOTE_TARGET}:${REMOTE_PATH}/"

# 2. config.json 单独处理（仅当目标不存在时才拷贝模板，避免覆盖已有配置）
echo ""
echo "📋 处理配置文件..."
ssh "${REMOTE_TARGET}" "
    if [[ ! -f ${REMOTE_PATH}/config.json ]]; then
        cat > ${REMOTE_PATH}/config.json <<'CONFEOF'
{
  \"lark_webhook_url\": \"\",
  \"bark_device_key\": \"\",
  \"bark_server\": \"https://api.day.app\",
  \"top_n\": 20,
  \"language\": \"\",
  \"update_interval_hours\": 24,
  \"proxy\": \"\"
}
CONFEOF
        echo '  ⚠️  已创建 config.json 模板，请编辑填入推送渠道配置'
    else
        echo '  ✅ config.json 已存在，保留原有配置'
    fi
"

# 3. 在远程主机上安装依赖
echo ""
echo "🐍 安装 Python 依赖..."
ssh "${REMOTE_TARGET}" "bash -s" << 'SETUPEOF'
set -e
PROJECT_DIR="$1"

cd "$PROJECT_DIR"

# 检测 Python3
if ! command -v python3 &>/dev/null; then
    echo "❌ 目标主机未安装 python3，请先安装: apt install python3 或 yum install python3"
    exit 1
fi
echo "  Python: $(python3 --version)"

# 创建虚拟环境
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
    echo "  ✅ 虚拟环境已创建"
else
    echo "  ✅ 虚拟环境已存在"
fi

# 安装依赖
.venv/bin/pip install -r requirements.txt -q
echo "  ✅ 依赖已安装"

# 验证
.venv/bin/python -c "import github_hot; print('  ✅ 脚本加载正常')"
SETEOF _ "$REMOTE_PATH"

# 4. 完成提示
echo ""
echo "============================================"
echo "  ✅ 部署完成！"
echo "============================================"
echo ""
echo "接下来在远程主机上操作："
echo ""
echo "  1. 编辑配置文件:"
echo "     ssh ${REMOTE_TARGET} 'vim ${REMOTE_PATH}/config.json'"
echo ""
echo "  2. 手动测试运行:"
echo "     ssh ${REMOTE_TARGET} 'cd ${REMOTE_PATH} && ./run.sh'"
echo ""
echo "  3. 设置定时任务（每天早上 9 点推送）:"
echo "     ssh ${REMOTE_TARGET} 'crontab -l 2>/dev/null; echo \"0 9 * * * cd ${REMOTE_PATH} && ./run.sh >> ${REMOTE_PATH}/run.log 2>&1\"' | ssh ${REMOTE_TARGET} 'crontab -'"
echo ""

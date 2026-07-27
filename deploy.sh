#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# deploy.sh — 部署项目（支持本机 / 远程）
#
# 用法:
#   ./deploy.sh --local                            # 本机部署
#   ./deploy.sh user@host [remote_path]             # 远程部署
#
# 示例:
#   ./deploy.sh --local
#   ./deploy.sh root@192.168.1.100
#   ./deploy.sh pi@raspberrypi.local /home/pi/github-hot
# ──────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

# ── setup_env — 在当前目录安装 venv + 依赖 ─────────────────
setup_env() {
    local target_dir="${1:-$PROJECT_DIR}"
    cd "$target_dir"

    # 检测 Python3
    if ! command -v python3 &>/dev/null; then
        echo "❌ 未安装 python3，请先安装: apt install python3 或 yum install python3"
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

    # 确保 pip 可用（精简系统可能没装 ensurepip）
    if ! .venv/bin/python3 -m pip --version &>/dev/null; then
        echo "  ⚠️  venv 缺少 pip，尝试安装..."
        .venv/bin/python3 -m ensurepip --upgrade 2>/dev/null || {
            echo "❌ 缺少 python3-venv / ensurepip，请先安装: apt install python3-venv"
            exit 1
        }
    fi

    # 安装依赖
    .venv/bin/python3 -m pip install -r requirements.txt -q
    echo "  ✅ 依赖已安装"

    # 验证
    .venv/bin/python -c "import github_hot; print('  ✅ 脚本加载正常')"
}

# ── setup_config — 如不存在则创建 config.json 模板 ─────────
setup_config() {
    local target_dir="${1:-$PROJECT_DIR}"
    if [[ -f "$target_dir/config.json" ]]; then
        echo "  ✅ config.json 已存在，保留原有配置"
        return
    fi
    cat > "$target_dir/config.json" <<'CONFEOF'
{
  "lark_webhook_url": "",
  "bark_device_key": "",
  "bark_server": "https://api.day.app",
  "top_n": 20,
  "language": "",
  "update_interval_hours": 24,
  "proxy": ""
}
CONFEOF
    echo "  ⚠️  已创建 config.json 模板，请编辑填入推送渠道配置"
}

# ── 入口 ──────────────────────────────────────────────────

MODE="${1:-}"

# ── 本机部署 ──
if [[ "$MODE" == "--local" ]]; then
    echo "============================================"
    echo "  本机部署 — GitHub 热门项目推送"
    echo "  路径: ${PROJECT_DIR}"
    echo "============================================"
    echo ""

    echo "📋 处理配置文件..."
    setup_config "$PROJECT_DIR"

    echo ""
    echo "🐍 安装 Python 依赖..."
    setup_env "$PROJECT_DIR"

    echo ""
    echo "============================================"
    echo "  ✅ 本机部署完成！"
    echo "============================================"
    echo ""
    echo "接下来："
    echo ""
    echo "  1. 编辑配置文件:"
    echo "     vim ${PROJECT_DIR}/config.json"
    echo ""
    echo "  2. 手动测试运行:"
    echo "     cd ${PROJECT_DIR} && .venv/bin/python github_hot.py"
    echo ""
    echo "  3. 设置定时任务（每天早上 9 点推送）:"
    echo "     (crontab -l 2>/dev/null; echo \"0 9 * * * cd ${PROJECT_DIR} && .venv/bin/python github_hot.py >> ${PROJECT_DIR}/run.log 2>&1\") | crontab -"
    echo ""
    exit 0
fi

# ── 远程部署 ──
REMOTE_TARGET="$MODE"
REMOTE_PATH="${2:-/opt/github-hot-projects}"

if [[ -z "$REMOTE_TARGET" || "$REMOTE_TARGET" == "--help" || "$REMOTE_TARGET" == "-h" ]]; then
    echo "用法:"
    echo "  ./deploy.sh --local                本机部署"
    echo "  ./deploy.sh user@host [remote_path] 远程部署"
    echo ""
    echo "示例:"
    echo "  ./deploy.sh --local"
    echo "  ./deploy.sh root@192.168.1.100"
    echo "  ./deploy.sh pi@raspberrypi.local /home/pi/github-hot"
    exit 0
fi

echo "============================================"
echo "  远程部署 — GitHub 热门项目推送"
echo "  目标: ${REMOTE_TARGET}:${REMOTE_PATH}"
echo "============================================"
echo ""

# 1. rsync 项目文件
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

# 2. config.json 远程处理
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

# 3. 远程安装依赖（通过 SSH 调用 setup_env）
echo ""
echo "🐍 安装 Python 依赖..."
ssh "${REMOTE_TARGET}" "bash -s" << 'SETUPEOF'
set -e
TARGET_DIR="$1"

cd "$TARGET_DIR"

if ! command -v python3 &>/dev/null; then
    echo "❌ 目标主机未安装 python3，请先安装: apt install python3 或 yum install python3"
    exit 1
fi
echo "  Python: $(python3 --version)"

if [[ ! -d .venv ]]; then
    python3 -m venv .venv
    echo "  ✅ 虚拟环境已创建"
else
    echo "  ✅ 虚拟环境已存在"
fi

if ! .venv/bin/python3 -m pip --version &>/dev/null; then
    echo "  ⚠️  venv 缺少 pip，尝试安装..."
    .venv/bin/python3 -m ensurepip --upgrade 2>/dev/null || {
        echo "❌ 目标主机缺少 python3-venv / ensurepip，请先安装: apt install python3-venv"
        exit 1
    }
fi

.venv/bin/python3 -m pip install -r requirements.txt -q
echo "  ✅ 依赖已安装"

.venv/bin/python -c "import github_hot; print('  ✅ 脚本加载正常')"
SETUPEOF _ "$REMOTE_PATH"

# 4. 完成提示
echo ""
echo "============================================"
echo "  ✅ 远程部署完成！"
echo "============================================"
echo ""
echo "接下来在远程主机上操作："
echo ""
echo "  1. 编辑配置文件:"
echo "     ssh ${REMOTE_TARGET} 'vim ${REMOTE_PATH}/config.json'"
echo ""
echo "  2. 手动测试运行:"
echo "     ssh ${REMOTE_TARGET} 'cd ${REMOTE_PATH} && .venv/bin/python github_hot.py'"
echo ""
echo "  3. 设置定时任务（每天早上 9 点推送）:"
echo "     ssh ${REMOTE_TARGET} '(crontab -l 2>/dev/null; echo \"0 9 * * * cd ${REMOTE_PATH} && .venv/bin/python github_hot.py >> ${REMOTE_PATH}/run.log 2>&1\") | crontab -'"
echo ""

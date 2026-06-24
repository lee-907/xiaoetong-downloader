#!/usr/bin/env bash
# ============================================================
# 小鹅通下载器 - Ubuntu 一键部署脚本
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; }

# ------ 权限检查 ------
if [[ "$(id -u)" -eq 0 ]]; then
    warn "检测到 root 用户，将以非 root 方式安装 Python 依赖"
fi

# ------ 工作目录 ------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/venv"

cd "$PROJECT_DIR"
log "项目目录: $PROJECT_DIR"

# ------ 1. 检查 Python ------
log "检查 Python 版本..."
if ! command -v python3 &>/dev/null; then
    err "未找到 python3，请先安装: sudo apt install python3"
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(echo "$PY_VER >= 3.8" | bc -l 2>/dev/null || python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)')" ]]; then
    :
fi
log "Python $PY_VER"

# ------ 2. 系统依赖 ------
log "安装系统依赖..."
SYSTEM_PKGS="ffmpeg python3-venv python3-pip"
MISSING=""
for pkg in $SYSTEM_PKGS; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done

if [[ -n "$MISSING" ]]; then
    log "需要安装:$MISSING"
    sudo apt update
    sudo apt install -y $MISSING
else
    log "系统依赖已就绪"
fi

# 验证 ffmpeg
if command -v ffmpeg &>/dev/null; then
    log "ffmpeg $(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')"
else
    err "ffmpeg 安装失败"
    exit 1
fi

# ------ 3. 虚拟环境 ------
if [[ ! -d "$VENV_DIR" ]]; then
    log "创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
else
    log "虚拟环境已存在，跳过创建"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
log "已激活虚拟环境"

# ------ 4. Python 依赖 ------
log "升级 pip..."
pip install --upgrade pip -q

log "安装 Python 依赖..."
pip install -r requirements.txt

# ------ 5. Playwright ------
log "安装 Playwright Chromium 及系统库..."
playwright install chromium
playwright install-deps

# ------ 6. 配置文件 ------
CONFIG="$PROJECT_DIR/config.json"
CONFIG_EXAMPLE="$PROJECT_DIR/config.json.example"
if [[ ! -f "$CONFIG" ]]; then
    if [[ -f "$CONFIG_EXAMPLE" ]]; then
        cp "$CONFIG_EXAMPLE" "$CONFIG"
        log "已创建 config.json，请编辑填入 app_id、cookie、product_id"
    else
        warn "config.json.example 不存在，请手动创建 config.json"
    fi
else
    log "config.json 已存在"
fi

# ------ 7. 环境验证 ------
log "验证环境..."
python -c "import ffmpy, m3u8, requests; print('核心依赖 OK')"
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

if ffmpeg -version &>/dev/null; then
    log "ffmpeg 可用"
else
    warn "ffmpeg 不可用，无法合并视频"
fi

# ====== 完成 ======
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  部署完成${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  配置文件: $CONFIG"
echo "  Cookie 获取: 浏览器 DevTools → Network → 复制请求 Cookie"
if [[ ! -f "$CONFIG" ]] || ! grep -q '"cookie"' "$CONFIG" 2>/dev/null; then
    echo "  ⚠ 请先编辑 config.json 填入必要参数"
elif grep -q 'your_app_id_here\|your_product_id_here\|"cookie":\s*""' "$CONFIG" 2>/dev/null; then
    echo "  ⚠ config.json 中仍有占位符，请填入真实值"
fi
echo ""
echo "  运行命令:"
echo "    source venv/bin/activate"
echo "    python main.py"
echo "    python main.py --help"
echo ""

# 免密 sudo 提示（用于后续 playwright install-deps 等场景）
if ! sudo -n true 2>/dev/null; then
    echo "  💡 提示: 后续若需安装系统包，可能需要 sudo"
fi

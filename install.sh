#!/bin/bash
# install.sh — MOSS-Image Gradio 一键部署（含中文界面 + 离线修复）
# 用法: bash install.sh [部署根目录，默认 $HOME/moss-image]
set -e
BASE="${1:-$HOME/moss-image}"
REPO="$BASE/repo"
MODELS="$BASE/models"
mkdir -p "$MODELS"
cd "$BASE"

echo "=== [1/6] 克隆官方仓库 ==="
if [ ! -d "$REPO/.git" ]; then
  git clone --depth 1 https://github.com/OpenMOSS/MOSS-Image.git "$REPO" \
    || git clone --depth 1 https://gh-proxy.com/https://github.com/OpenMOSS/MOSS-Image.git "$REPO"
fi

echo "=== [2/6] 创建 venv 并安装依赖 ==="
cd "$REPO"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
PIP_ARGS="-i https://pypi.tuna.tsinghua.edu.cn/simple"   # 国内镜像；海外可删掉
python -m pip install -U pip -q $PIP_ARGS
pip install -e '.[ui]' $PIP_ARGS
pip install -q -U huggingface_hub $PIP_ARGS
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"

echo "=== [3/6] 下载模型（diffusers 完整捆绑包，含编码器/VAE） ==="
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"   # 国内镜像；海外可 export HF_ENDPOINT=https://huggingface.co
export HF_HUB_DISABLE_XET=1   # hf-mirror 不代理 Xet CAS 协议，必须关闭，否则 401
if [ ! -f "$MODELS/MOSS-Image-Base/model_index.json" ]; then
  hf download OpenMOSS-Team/MOSS-Image-Base --local-dir "$MODELS/MOSS-Image-Base"
fi

echo "=== [4/6] 应用中文界面 + 离线修复补丁 ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/patch_zh.py" --repo "$REPO"

echo "=== [5/6] （可选）下载 NSFW 无限制 LoRA（ComfyUI 格式存档） ==="
# 若要将文本编码器换成无限制版，参见 README「无限制编码器」章节
hf download axiomofmind/Moss-image-nsfw-uncensored-lora \
  --local-dir "$MODELS/nsfw-lora" || echo "跳过（非必需）"

echo "=== [6/6] 完成 ==="
cat <<EOF

部署完成。启动：
  cd $REPO && source .venv/bin/activate
  CUDA_VISIBLE_DEVICES=0 python gradio_app.py \\
    --model $MODELS/MOSS-Image-Base --local-files-only \\
    --host 127.0.0.1 --port 7860 --output-dir $BASE/outputs

远程服务器访问：本地执行
  ssh -N -L 7860:127.0.0.1:7860 <user>@<server>
然后浏览器打开 http://127.0.0.1:7860
EOF

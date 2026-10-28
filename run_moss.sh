#!/bin/bash
# run_moss.sh — MOSS-Image Gradio 启动脚本（后台常驻 + 完全离线）
# 按需修改: BASE / GPU 编号 / 端口
BASE="${MOSS_HOME:-$HOME/moss-image}"
REPO="$BASE/repo"
MODEL="${MOSS_MODEL:-$BASE/models/MOSS-Image-Base}"
cd "$REPO"
source .venv/bin/activate
export CUDA_VISIBLE_DEVICES="${MOSS_GPU:-0}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_OFFLINE=1            # 完全离线；配合 patch_zh.py 的本地 pipeline 修复
exec python gradio_app.py \
  --model "$MODEL" \
  --local-files-only \
  --host 127.0.0.1 \
  --port "${MOSS_PORT:-7860}" \
  --output-dir "$BASE/outputs"

# 后台常驻启动方式:
#   setsid nohup bash run_moss.sh </dev/null > gradio.log 2>&1 &
# 停止:
#   pkill -f 'gradio_ap[p].py'    # [p] 写法防止 pkill 误杀自身所在命令行

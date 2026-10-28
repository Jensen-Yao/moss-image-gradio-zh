#!/usr/bin/env python3
"""
patch_zh.py — MOSS-Image Gradio 界面一键汉化 + 离线加载修复

功能：
  1. 将官方 OpenMOSS/MOSS-Image 的 gradio_app.py 界面文本替换为中文
  2. 修复离线运行（HF_HUB_OFFLINE=1 / --local-files-only）时
     custom_pipeline="pipeline_moss_image" 按 Hub 仓库名解析导致的
     "Cannot find an appropriate cached snapshot folder" 报错
     （改为指向模型目录内的 pipeline_moss_image.py 本地文件）

用法：
  python3 patch_zh.py --repo /path/to/MOSS-Image          # 打补丁
  python3 patch_zh.py --repo /path/to/MOSS-Image --revert # 还原英文原版
  python3 patch_zh.py --repo /path/to/MOSS-Image --check  # 只检查不修改

说明：
  - 原文件自动备份为 gradio_app.py.en / inference_runtime.py.en
  - 幂等：重复执行安全（已打补丁则跳过）
  - 补丁基于官方仓库 2026-10 版 gradio_app.py（commit 含 UI_ASSETS/prompt_defaults 结构），
    若上游字符串变动导致个别条目未命中，脚本会列出 MISS 清单但不会破坏文件
"""
import argparse
import py_compile
import shutil
import sys
from pathlib import Path

# (英文原文, 中文译文)。均为精确子串替换，按文件中出现顺序应用。
UI_PAIRS = [
    # ── 模型选择 ──
    ('label="Hugging Face model ID or local directory"', 'label="模型（HF ID 或本地目录）"'),
    # ── 提示词区 ──
    ('label="Prompt",', 'label="提示词",'),
    ('placeholder="Describe your image — subject, light, composition, style…",',
     'placeholder="描述画面：主体、光线、构图、风格…",'),
    ('label="Negative Prompt",', 'label="负面提示词",'),
    ('placeholder="What would you like to leave out?"', 'placeholder="想排除什么？"'),
    ('raise ValueError("Enter a prompt.")', 'raise ValueError("请输入提示词。")'),
    # ── 尺寸区 ──
    ('label="Resolution (M pixels)",', 'label="分辨率（百万像素）",'),
    ('label="Aspect ratio (W/H)",', 'label="宽高比 (W/H)",'),
    ('label="Width",', 'label="宽",'),
    ('label="Height",', 'label="高",'),
    ('label="Resolution presets",', 'label="分辨率预设",'),
    ('label="Aspect ratio presets",', 'label="比例预设",'),
    # ── 生成参数 ──
    ('label="Images", minimum=1', 'label="张数", minimum=1'),
    ('label="Seed",', 'label="种子",'),
    ('label="Steps"', 'label="步数"'),
    ('gr.Button("Random", size="sm", render=False)', 'gr.Button("随机", size="sm", render=False)'),
    # ── 高级设置 ──
    ('"Advanced settings"', '"高级设置"'),
    ('label="Memory mode",', 'label="显存模式",'),
    ('("GPU resident", "none"),', '("全部驻留 GPU", "none"),'),
    ('("Component", "model"),', '("按组件切换", "model"),'),
    ('("Sequential · fallback", "sequential"),', '("顺序换入（兜底）", "sequential"),'),
    ('label="Compile DiT",', 'label="编译 DiT",'),
    ('label="Skip layer mode",', 'label="跳层模式",'),
    ('choices=[("Off", "off"), ("Negative-branch skipping", "negative"),',
     'choices=[("关闭", "off"), ("负分支跳过", "negative"),'),
    ('("Standard SLG", "standard")],', '("标准 SLG", "standard")],'),
    ('label="Skip layers",', 'label="跳过层",'),
    ('info="Zero-based layer indices, separated by commas. Empty disables skipping.",',
     'info="从 0 开始的层号，逗号分隔；留空=不跳层。",'),
    ('info="Zero-based layer indices, separated by commas.",',
     'info="从 0 开始的层号，逗号分隔。",'),
    ('label="SLG layers",', 'label="SLG 层",'),
    ('label="Skip start"', 'label="跳层起点"'),
    ('label="Skip stop"', 'label="跳层终点"'),
    # ── 生成按钮 / 状态 ──
    ('gr.Button("Generate", variant="primary")', 'gr.Button("生成", variant="primary")'),
    ('label="Status", interactive=False', 'label="状态", interactive=False'),
    # ── 进度文案 ──
    ('"encode": "Encoding prompt",', '"encode": "编码提示词",'),
    ('"denoise": f"Sampling · step 0/{total_steps}",', '"denoise": f"采样 · 0/{total_steps} 步",'),
    ('"decode": "Decoding image",', '"decode": "解码图像",'),
    ('f"Sampling · step {completed}/{total_steps}"', 'f"采样 · {completed}/{total_steps} 步"'),
    ('desc="Loading model"', 'desc="加载模型"'),
    ('desc="Saving images and parameters"', 'desc="保存图像与参数"'),
    ('desc="Complete"', 'desc="完成"'),
    ('return "Model released. It will load again on the next generation."',
     'return "模型已释放，下次生成时重新加载。"'),
    ("f\"Saved {len(images)} image(s) · seed {config.seed} · {record['elapsed_seconds']:.1f}s\",",
     "f\"已保存 {len(images)} 张 · 种子 {config.seed} · {record['elapsed_seconds']:.1f} 秒\","),
    # ── 示例区 ──
    ('"## Examples"', '"## 示例"'),
    ('label="Examples",', 'label="示例库",'),
    ('label="Original Prompt",', 'label="原始提示词",'),
    ('label="Original settings",', 'label="原始参数",'),
    ('placeholder="Click an image to view its original prompt.",',
     'placeholder="点击示例图查看原始提示词。",'),
    # ── 示例参数面板（f-string 片段）──
    ('f"{config.width} × {config.height} · {config.steps} steps · CFG {config.cfg:g}\\n"',
     'f"{config.width} × {config.height} · {config.steps} 步 · CFG {config.cfg:g}\\n"'),
    ("f\"Euler · Seed {parameters.get('seed') if parameters.get('seed') is not None else 'unknown (random on generation)'}\\n\"",
     "f\"Euler · 种子 {parameters.get('seed') if parameters.get('seed') is not None else '随机'}\\n\""),
    ('f"Uncond skip {config.uncond_skip_layers or \'off\'} · "',
     'f"负分支跳层 {config.uncond_skip_layers or \'关\'} · "'),
    ('f"Standard SLG {config.slg_layers or \'off\'} (scale {config.slg_scale:g}) · "',
     'f"标准 SLG {config.slg_layers or \'关\'} (强度 {config.slg_scale:g}) · "'),
    ('f"Interval [{config.slg_start:g}, {config.slg_stop:g})"',
     'f"区间 [{config.slg_start:g}, {config.slg_stop:g})"'),
    # ── 错误提示 ──
    ('raise ValueError("Choose a complete local model bundle with all five components.")',
     'raise ValueError("请选择包含全部五个组件的完整本地模型目录。")'),
]

# 离线加载修复：custom_pipeline 指向本地文件而非 Hub 名
OFFLINE_OLD = '''def load_pipeline(model, local_files_only=False):
    return diffusers.DiffusionPipeline.from_pretrained(
        model_source(model),
        custom_pipeline="pipeline_moss_image",'''
OFFLINE_NEW = '''def load_pipeline(model, local_files_only=False):
    root = model_source(model)
    local_pipeline = str(Path(root) / "pipeline_moss_image.py")
    return diffusers.DiffusionPipeline.from_pretrained(
        root,
        custom_pipeline=local_pipeline,'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="MOSS-Image 仓库根目录（含 gradio_app.py / inference_runtime.py）")
    ap.add_argument("--revert", action="store_true", help="从 .en 备份还原英文原版")
    ap.add_argument("--check", action="store_true", help="只检查，不写入")
    args = ap.parse_args()
    repo = Path(args.repo).expanduser().resolve()
    ga, ir = repo / "gradio_app.py", repo / "inference_runtime.py"
    if not ga.is_file() or not ir.is_file():
        sys.exit(f"错误：{repo} 下未找到 gradio_app.py / inference_runtime.py")

    if args.revert:
        for f in (ga, ir):
            bak = f.with_suffix(".py.en")
            if bak.is_file():
                shutil.copy(bak, f)
                print(f"已还原 {f.name} <- {bak.name}")
            else:
                print(f"跳过 {f.name}（无 .en 备份）")
        return

    # ── 汉化 ──
    src = ga.read_text(encoding="utf-8")
    if "提示词" in src and "已保存" in src:
        print("gradio_app.py 已是中文版，跳过汉化")
    else:
        if not ga.with_suffix(".py.en").is_file():
            shutil.copy(ga, ga.with_suffix(".py.en"))
        miss = []
        for old, new in UI_PAIRS:
            if old not in src:
                miss.append(old[:60])
                continue
            src = src.replace(old, new)
        hit = len(UI_PAIRS) - len(miss)
        if not args.check:
            ga.write_text(src, encoding="utf-8")
        print(f"gradio_app.py 汉化 {hit}/{len(UI_PAIRS)} 条已应用" + ("（check 模式未写入）" if args.check else ""))
        for m in miss:
            print(f"  MISS: {m}")

    # ── 离线修复 ──
    src = ir.read_text(encoding="utf-8")
    if "local_pipeline" in src:
        print("inference_runtime.py 已含离线修复，跳过")
    elif OFFLINE_OLD in src:
        if not ir.with_suffix(".py.en").is_file():
            shutil.copy(ir, ir.with_suffix(".py.en"))
        if not args.check:
            ir.write_text(src.replace(OFFLINE_OLD, OFFLINE_NEW), encoding="utf-8")
        print("inference_runtime.py 离线加载修复已应用" + ("（check 模式未写入）" if args.check else ""))
    else:
        print("警告：inference_runtime.py 未匹配到 custom_pipeline 模式（上游可能已改动），跳过")

    # ── 语法校验 ──
    if not args.check:
        py_compile.compile(str(ga), doraise=True)
        py_compile.compile(str(ir), doraise=True)
        print("语法校验通过 SYNTAX_OK")


if __name__ == "__main__":
    main()

# MOSS-Image Gradio 中文汉化包

给 [OpenMOSS/MOSS-Image](https://github.com/OpenMOSS/MOSS-Image) 官方 Gradio 界面的**一键汉化 + 纯离线运行**补丁包。

官方 `gradio_app.py` 是英文界面，且按 README 在线方式使用没问题，但**纯本地/离线部署**（`HF_HUB_OFFLINE=1`、`--local-files-only`）会因 `custom_pipeline="pipeline_moss_image"` 按 Hub 仓库名解析而直接报错：

> ❌ Cannot find an appropriate cached snapshot folder for the specified revision on the local disk and outgoing traffic has been disabled…

本包解决这两件事，并在 **NVIDIA H800 上完成了端到端实测**（首次生成含冷加载 58 秒出图）：

- ✅ 界面全中文（53 条替换：主界面 / 高级设置 / 进度 / 状态 / 示例 / 错误提示）
- ✅ 离线加载修复（`custom_pipeline` 指向模型目录内本地文件）
- ✅ 幂等、可还原（`--revert`）、带语法校验的补丁脚本
- ✅ 中国大陆网络适配（hf-mirror + 关闭 Xet + pip 清华源，均已内置）

## 实测效果

![实测生图输出](docs/sample-output.png)

> 1216×832 · 30 步 · CFG 3.0 · 种子 42 · H800 PCIe · 含 30GB 模型冷加载共 58 秒
> 状态栏：`已保存 1 张 · 种子 42 · 57.5 秒`

详细数据与 9 个真实踩坑记录见 **[docs/test-record.md](docs/test-record.md)**。

## 快速开始（一键部署）

```bash
git clone https://github.com/Jensen-Yao/moss-image-gradio-zh.git
cd moss-image-gradio-zh
bash install.sh            # 默认装到 ~/moss-image，可传自定义目录
# 脚本最后会打印启动命令，启动后浏览器打开 http://127.0.0.1:7860
```

远程服务器加一条隧道即可本地访问：

```bash
ssh -N -L 7860:127.0.0.1:7860 <user>@<server>
```

## 只打补丁（已有官方仓库）

```bash
git clone --depth 1 https://github.com/OpenMOSS/MOSS-Image.git
python3 patch_zh.py --repo /path/to/MOSS-Image          # 汉化 + 离线修复
python3 patch_zh.py --repo /path/to/MOSS-Image --check  # 只检查
python3 patch_zh.py --repo /path/to/MOSS-Image --revert # 还原英文原版
```

补丁内容：

| 文件 | 改动 |
|---|---|
| `gradio_app.py` | 界面文本 53 条中文化（原文件备份为 `gradio_app.py.en`） |
| `inference_runtime.py` | `custom_pipeline` 由 Hub 名改为本地文件路径（备份为 `.py.en`） |

也可直接用现成 diff：`git apply patches/moss-image-zh-offline.patch`。

## 启动（完全离线）

```bash
cd /path/to/MOSS-Image && source .venv/bin/activate
export HF_HUB_OFFLINE=1
CUDA_VISIBLE_DEVICES=0 python gradio_app.py \
  --model /path/to/models/MOSS-Image-Base \
  --local-files-only \
  --host 127.0.0.1 --port 7860
```

或直接用模板脚本：`MOSS_HOME=~/moss-image bash run_moss.sh`（后台常驻写法见脚本注释）。

## 无限制文本编码器（可选进阶）

MOSS-Image 的文本编码器是标准 `AutoModel` 加载的 Qwen3.5-9B 文本模型，
可直接换用社区消融（abliterated）权重实现"无限制"提示词编码。**已实测可行**：

1. 下载纯文本版消融模型：[`lukey03/Qwen3.5-9B-abliterated`](https://hf-mirror.com/lukey03/Qwen3.5-9B-abliterated)
   （单文件 `model.safetensors` 17.9GB；**注意避开 VL 变体**如 huihui/wangzhang 同名款，见测试记录 §5.4）
2. 覆盖权重（保留捆绑包原 config/tokenizer，并先备份）：
   ```bash
   cp -r models/MOSS-Image-Base/text_encoder models/MOSS-Image-Base/text_encoder.orig
   cp lukey03/model.safetensors models/MOSS-Image-Base/text_encoder/
   ```
3. 还原：把 `text_encoder.orig` 内容拷回即可。

加载时出现的 333 个 `visual.*` 缺失 key 属正常（视觉塔不参与文本编码），端到端已验证。

## 常见问题

<details>
<summary>点「生成」报 Cannot find an appropriate cached snapshot folder</summary>

没打离线补丁。执行 `python3 patch_zh.py --repo <仓库>` 后重启服务。
</details>

<details>
<summary>hf 下载模型报 401 / cas-server.xethub.hf.co</summary>

Xet 协议被镜像拦截：`export HF_HUB_DISABLE_XET=1`。
</details>

<details>
<summary>首次生成很慢？</summary>

正常。模型懒加载，30GB 权重首次进 GPU 需 0.5~3 分钟（取决于盘速），之后常驻。
</details>

<details>
<summary>pkill 停服务把 SSH 一起杀了</summary>

模式加字符类防自匹配：`pkill -f 'gradio_ap[p].py'`。
</details>

## 兼容性

- 基于 OpenMOSS/MOSS-Image 2026-10 版（diffusers 0.42.1 / transformers 5.21.0 / gradio 6.30.0 / torch 2.14.1+cu130 / Python 3.12 实测）
- 上游字符串变动时脚本会打印 MISS 清单，不会破坏文件；欢迎提 issue 附上 MISS 输出

## License

MIT。上游 MOSS-Image 版权归 OpenMOSS 所有，本包仅包含补丁脚本与文档。

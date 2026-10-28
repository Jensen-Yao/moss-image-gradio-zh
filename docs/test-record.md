# MOSS-Image Gradio 汉化包 — 实际使用测试记录

> 全部数据来自 2026-10-28 真实部署与压测，非理论值。
> 测试人：Jensen-Yao（AI 协助） · 记录时间：2026-10-28 11:35（Asia/Shanghai）

---

## 1. 测试环境

| 项 | 值 |
|---|---|
| GPU | NVIDIA H800 PCIe 80GB（双卡，测试用 GPU1，与 ComfyUI 共卡） |
| 驱动/CUDA | CUDA 13.0 |
| 系统 | Ubuntu (Linux 6.x) / Python 3.12.3 |
| torch | 2.14.1+cu130 |
| diffusers | 0.42.1 |
| transformers | 5.21.0 |
| gradio | 6.30.0 |
| accelerate | 1.15.0 |
| 模型 | OpenMOSS-Team/MOSS-Image-Base（diffusers 捆绑包，~30GB） |
| 网络环境 | 中国大陆，HF 走 hf-mirror.com 镜像 |
| 部署目录 | /opt/.internal/lbd/moss-image/（仓库 clone + 独立 venv） |

---

## 2. 端到端生图实测（补丁后 · 含中文界面 + 离线修复）

**测试方式**：Gradio HTTP API（`POST /gradio_api/call/generate`），模拟浏览器点击「生成」。

```
TEST_START 2026-10-28 11:33:00
PROMPT  : 夜景赛博朋克街道，霓虹灯牌，一个穿黑色皮衣的短发女孩站在雨中回望镜头，电影感，景深
参数    : 1216×832(横) 30步 CFG 3.0 shift 5.0 种子42 跳层"22" 显存模式=按组件切换
event_id: c216b08ca73448aaa0c5b3fb99fb66ac
TEST_END  2026-10-28 11:33:58  elapsed=58s
```

| 指标 | 实测值 |
|---|---|
| 首次生成总耗时（**含 30GB 模型冷加载**） | **58 秒** |
| 管线内部计时（parameters.json `elapsed_seconds`） | **57.5 秒** |
| 采样器 / 精度 | Euler / DiT bfloat16 + VAE float32 |
| 生成后 GPU1 显存 | 42.1 GB（与同卡 ComfyUI 共存，模型按组件切换回 CPU） |
| 返回状态文案 | **「已保存 1 张 · 种子 42 · 57.5 秒」**（中文，汉化生效） |
| 管线加载模块 | `diffusers_modules.local.pipeline_moss_image`（**local** = 离线修复生效） |
| 输出 | 1 张 1216×832 PNG（见 `docs/sample-output.png`） |

> 对比：同一 H800 上官方英文版首次生成（未打补丁时）直接报错，见 §5.9。

![实测生图输出](sample-output.png)

生成元数据（`outputs/<uuid>/parameters.json`，摘录）：

```json
{
  "model": "MOSS-Image-Base",
  "pipeline_class": "MOSSImagePipeline",
  "pipeline_module": "diffusers_modules.local.pipeline_moss_image",
  "sampler": "Euler",
  "weight_dtype": "bfloat16",
  "gpu": "NVIDIA H800 PCIe",
  "elapsed_seconds": 57.518,
  "versions": {"torch": "2.14.1", "diffusers": "0.42.1",
               "transformers": "5.21.0", "accelerate": "1.15.0"}
}
```

---

## 3. 界面汉化实测

- 补丁脚本对上游文件逐条精确替换；**首轮实测命中 48/51**，3 条未命中为示例参数面板的
  f-string 片段（转义差异），v2 脚本已按源码原文补齐（现共 53 条替换规则）。
- 服务重启后经 Gradio `/config` 接口抓取组件文本验证：

```
$ curl -s http://127.0.0.1:7860/config | grep -o "提示词\|负面提示词\|分辨率预设\|跳层模式" | sort | uniq -c
      1 分辨率预设
      3 提示词
      2 负面提示词
      1 跳层模式
```

- 浏览器（需 Ctrl+F5 强刷清缓存）确认：主界面、高级设置折叠区、生成进度条
  （编码提示词 → 采样 x/y 步 → 解码图像）、完成状态、示例区均为中文。
- 未翻译：品牌名 MOSS-Image、CFG/Shift/Euler/SLG 等术语（有意保留）。

---

## 4. 无限制（abliterated）文本编码器替换实测

> 与本汉化包独立，但属同一次部署验证，一并记录。

| 步骤 | 实测结果 |
|---|---|
| 候选筛查 | `huihui-ai/Huihui-Qwen3.5-9B-abliterated`、`wangzhang/…` 均为 **VL 变体**（`Qwen3_5ForConditionalGeneration` + `text_config` 嵌套，权重含视觉塔）❌ 不可直接换入 |
| 选定 | `lukey03/Qwen3.5-9B-abliterated`：纯文本 `Qwen3_5ForCausalLM`，单文件 17.9GB BF16，含 `abliteration_meta.json` ✅ |
| 换法 | **只换权重**（`text_encoder/model.safetensors`），保留捆绑包原 config + tokenizer；原版备份为 `text_encoder.orig/` |
| 加载验证 | AutoModel 载入 **8.39B 参数**；missing=333 全部为 `visual.*`（视觉塔，纯文本 forward 不经过，随机初始化无影响）；unexpected=1 为 `lm_head.weight`（未共享词向量，多余但无害） |
| 功能验证 | 按管线同款调用（chat template + `use_cache=False`）编码中文提示词 → `last_hidden_state (1,17,4096) bf16`，**全有限值**，范数 544.5 ✅ |
| 端到端 | §2 的 58 秒生图即用此无限制编码器完成 ✅ |

---

## 5. 踩坑与修复记录（全部真实发生）

### 5.1 `huggingface-cli: command not found`
- 现象：`pip install huggingface_hub[cli]` 后命令不存在。
- 原因：huggingface_hub **2.3.0 起 CLI 更名**，`huggingface-cli` → `hf`；`[cli]` extra 也不存在了。
- 修复：统一改用 `hf download …`；`--local-dir-use-symlinks` 参数已废弃，一并移除。

### 5.2 hf-mirror 下载大文件 401 Unauthorized
- 现象：`hf download` 拉 LFS 大分片时报 `CAS Client Error: 401`，域名 `cas-server.xethub.hf.co`。
- 原因：新版 hf 默认走 **Xet 存储协议**，hf-mirror 只代理经典 HTTPS 端点，不代理 Xet CAS。
- 修复：`export HF_HUB_DISABLE_XET=1` 回退普通 HTTP 下载，速度 ~7MB/s 稳定。
- 已写入 `install.sh`。

### 5.3 断点文件导致「假完成」
- 现象：下载中断重跑后脚本直接判 `SETUP_DONE`，但 text_encoder/transformer 权重目录全空。
- 原因：完成判定只检查 `model_index.json`（小文件，首轮失败前已下载），守卫被绕过。
- 修复：完成校验必须逐一核对 `*.safetensors.index.json` 的 weight_map 中每个分片存在。

### 5.4 消融版选型陷阱：同名 ≠ 同构
- `Huihui-Qwen3.5-9B-abliterated` 等"Qwen3.5-9B"消融模型多为 **VL 检查点**
  （`ForConditionalGeneration` + 嵌套 `text_config`，权重前缀含 `model.language_model.*` 与视觉塔）。
- MOSS-Image 捆绑包的编码器是 `Qwen3_5Model`（文本基座），换入前必须核对
  `architectures` / `hidden_size` / 权重 key 前缀，纯文本版才能直接对齐。

### 5.5 单文件检查点使分片校验崩溃
- 现象：校验脚本读取 `model.safetensors.index.json` 报 FileNotFoundError，但 17GB 已下载完。
- 原因：lukey03 是**单文件** `model.safetensors`（17,907,663,008 字节），无索引文件。
- 修复：校验逻辑兼容「分片+索引」与「单文件 ≥10GB」两种形态。

### 5.6 `from_pretrained(..., output_loading_info=True).to('cuda')` 链式崩溃
- 现象：`AttributeError: 'tuple' object has no attribute 'to'`。
- 原因：`output_loading_info=True` 时返回 `(model, info)` 元组，`.to()` 作用到了元组上。
- 修复：拆成两行；同理 transformers 5.x 的 `missing_keys/unexpected_keys` 是 **set**，
  直接 `[:10]` 切片会 `TypeError: 'set' object is not subscriptable`，需先 `list()`。

### 5.7 333 个 `visual.*` 缺失 key 是否要紧？
- 结论：**不要紧**。捆绑包编码器 config 由 VL 检查点派生（含 `image_token_id`），
  AutoModel 按 `Qwen3_5Model` 实例化时携带可选视觉塔参数；MOSS 生图管线
  `encode_prompt()` 只喂 `input_ids/attention_mask`，不经过视觉塔，
  随机初始化权重永不参与前向。§4 的功能验证（有限值 + 合理范数）与 §2 端到端出图均为证。

### 5.8 pkill 自杀式误杀
- 现象：`ssh server "pkill -f finish_and_swap_and_run"` 无返回直接断连。
- 原因：`pkill -f` 匹配**完整命令行**，SSH 远端 `bash -c "… pkill -f finish_and_swap_and_run …"`
  自身命令行就含该模式，把自己杀了。
- 修复：模式中插入字符类，如 `pkill -f 'finish_and_swap_and_ru[n]'`；
  启动脚本同理（`gradio_ap[p].py`）。

### 5.9 ★ 本包核心修复：离线模式报 "Cannot find an appropriate cached snapshot folder"
- 现象（用户实测）：界面点「生成」即报 Error(2)：
  `Cannot find an appropriate cached snapshot folder for the specified revision …
  pass 'local_files_only=False' as input.`
- 原因：`inference_runtime.load_pipeline()` 写死 `custom_pipeline="pipeline_moss_image"`，
  diffusers 将其当作 **Hub 仓库名**解析；`HF_HUB_OFFLINE=1` + `--local-files-only` 下无法联网查找 → 报错。
  官方 README 的在线用法不触发此问题，纯本地部署必踩。
- 修复：`custom_pipeline` 改为指向模型目录内的本地文件
  `<model_dir>/pipeline_moss_image.py`（`model_source()` 本就要求捆绑包含此文件）。
- 验证：修复后 `parameters.json` 出现 `"pipeline_module": "diffusers_modules.local.pipeline_moss_image"`，
  §2 生图成功。

### 5.10 中国大陆网络三件套（汇总进 install.sh）
| 措施 | 作用 |
|---|---|
| `HF_ENDPOINT=https://hf-mirror.com` | HF 全量镜像 |
| `HF_HUB_DISABLE_XET=1` | 规避镜像不支持的 Xet 协议（§5.2） |
| pip 清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple` | 依赖安装提速 |

---

## 6. 测试结论

| 能力 | 结果 |
|---|---|
| 一键部署（clone → venv → 模型 → 补丁 → 启动） | ✅ 全流程可复现 |
| 中文界面 | ✅ 53 条替换规则，界面/进度/状态/示例全中文 |
| 完全离线运行（`HF_HUB_OFFLINE=1` + `--local-files-only`） | ✅ 修复后首次生成即成功 |
| H800 单卡（与 ComfyUI 共卡 40GB 空闲） | ✅ 首张 58s（含冷加载），之后常驻 |
| 1216×832 / 30 步 | ✅ 57.5s/张（含加载）；纯采样预估 <30s/张 |
| 无限制编码器替换 | ✅ 端到端验证通过 |

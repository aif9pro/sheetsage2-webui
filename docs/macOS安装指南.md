# SheetSage2 WebUI · macOS 安装指南

把一首歌的录音丢进去，自动扒出**主旋律 / 器乐 / 和弦 / 节拍 / 调性 / 段落**，
导出成 **Synthesizer V 工程（SVP）/ MIDI**。本指南只负责一件事：
**在 Mac 上从源码把它跑起来。**

> 整合包（网盘里那个 `start.bat`）是 **Windows 专用**的（便携 Python + ffmpeg 都是
> Windows x64 二进制），**Mac 上不能用**。Mac 请走本文的**源码方式**——一次性装好，
> 之后在项目目录里跑 `./start.sh` 即可。

---

## 0. 结论先行（30 秒版）

macOS 上没有 NVIDIA 显卡，程序会自动走 **CPU 推理**：能用、结果是准的，就是慢
（Apple Silicon 上 5 分钟的歌约 **10–30 分钟**，Intel 机器更久）。
如果你只是想尽快出谱、又手边有 Windows 机器，优先用整合包更快。

一次装好大约要 **4 GB 磁盘**（依赖 ~1 GB + 权重 ~2.6 GB）。全程联网，装完可离线跑。

**核心就 6 步**：装 Homebrew → 装 Python 3.12 + ffmpeg → 拉代码 → 建 venv 装依赖 →
下权重 → `./start.sh`。

---

## 1. 系统要求

| 项 | 要求 | 说明 |
| --- | --- | --- |
| 系统 | macOS 12 Monterey 或更新 | Apple Silicon（M 系列）与 Intel 都可 |
| 芯片 | Apple Silicon 或 Intel x64 | **没有 NVIDIA 显卡 → 一律 CPU 推理** |
| 内存 | 建议 ≥ 16 GB | 8 GB 也能跑，处理长歌时容易吃紧 |
| 磁盘 | 约 4 GB 空闲 | 依赖约 1 GB + 模型权重约 2.6 GB |
| 网络 | 安装阶段需要 | 下依赖 + 下权重；装完可完全离线 |
| 其他 | Python 3.12、ffmpeg、Git | 见下，用 Homebrew 一次装齐 |

速度参考（CPU，Apple Silicon M 系列）：5 分钟的 FullSong 约 **10–30 分钟**；
纯 Intel Mac 会更慢。这不是卡死——顶部进度条在动就正常。

---

## 2. 安装 Homebrew（已经装过就跳过）

Homebrew 是 Mac 上的包管理器，用来装 Python 和 ffmpeg。

```bash
# 检查有没有装
brew --version
```

如果提示 `command not found`，按提示装一次（国内网络若卡在外网，见文末「常见问题」）：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

装完按屏幕提示把 `brew` 加进 `PATH`（Apple Silicon 通常是
`eval "$(/opt/homebrew/bin/brew shellenv)"` 一行；把它写进 `~/.zprofile` 以后就常驻）。
再跑一次 `brew --version` 确认能输出版本号。

---

## 3. 安装 Python 3.12 与 ffmpeg

```bash
brew install python@3.12 ffmpeg
```

装完确认一下：

```bash
python3.12 --version     # 期望：Python 3.12.x
ffmpeg -version | head -1
```

> **ffmpeg 必须能在 PATH 上被找到**。程序内部（SheetSage2 的 vendored 代码）用的是
> `shutil.which("ffmpeg")`，只认 PATH。Homebrew 装的 ffmpeg 默认就在 PATH 上，
> 通常无需额外操作。如果 `ffmpeg -version` 没输出版本，`brew link ffmpeg` 一下。

---

## 4. 获取代码

```bash
git clone https://github.com/3253473591/sheetsage2-webui.git
cd sheetsage2-webui
```

> 路径里可以有中文和空格，但**不要放在 OneDrive / iCloud Drive / 网盘的同步目录**里
> （同步进程会在推理时锁文件、拖慢甚至打断任务）。

---

## 5. 建虚拟环境 + 装依赖

### 5.1 建虚拟环境

用系统自带的 `venv`：

```bash
python3.12 -m venv .venv
```

或者，如果你装了 [uv](https://github.com/astral-sh/uv)（`brew install uv`），更快：

```bash
uv venv --python 3.12 .venv
```

### 5.2 先装 PyTorch（Mac 版）

⚠️ **关键差异**：仓库里的 `requirements.txt` 把 torch 钉成了
`torch==2.10.0+cu130` —— 那个 `+cu130` 是 **NVIDIA CUDA 版，Mac 上装不了也别装**。
Mac 直接装 PyPI 上的标准版（自带 CPU + Apple GPU 的 MPS 支持，本项目走 CPU）：

```bash
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install torch torchaudio
```

> 不指定版本就是装当前最新的稳定版，通常没问题。想固定版本可以写
> `torch==2.10.0 torchaudio==2.10.0`（**不带** `+cu130` 后缀）；
> 但切记 **torch 与 torchaudio 的版本号必须完全一致**。

### 5.3 装其余依赖

**顺序很重要**：必须先装 torch，再装其余依赖。否则 `accelerate` 的元数据会把一个
不需要的 torch 版本拖下来，白等半天还装错。

Mac 用的清单是 `requirements-macos.txt`（= `requirements-base.txt` 去掉两个不参与
主流程的老原生包 `dynet38` / `nagisa`，它们在 Apple Silicon 上会尝试源码编译并失败）：

```bash
.venv/bin/python -m pip install -r requirements-macos.txt
```

装完自检一下能不能 import：

```bash
.venv/bin/python -c "import torch, torchaudio, transformers, fastapi; print('torch', torch.__version__, '| CUDA', torch.cuda.is_available())"
```

Mac 上 `CUDA` 这行应该是 `False`，**这是正常的**。

---

## 6. 下载模型权重（约 2.6 GB）

仓库**不带权重**（体积超限 + 许可是 CC BY-NC 4.0，与代码的 MIT 不同）。用脚本现取。

### 6.1 先在网页上同意（两个仓库都是 gated）

用浏览器登录 Hugging Face，分别打开下面两个页面，各点一次
**「Agree and access repository」**：

* <https://huggingface.co/m-a-p/SheetSage2>
* <https://huggingface.co/m-a-p/MERT-v2-FullSong>

### 6.2 本机登录

```bash
.venv/bin/python -m pip install -U huggingface_hub
.venv/bin/huggingface-cli login      # 新版也支持： .venv/bin/hf auth login
```

按提示粘贴自己的 **Access Token**（在 HF 的 Settings → Access Tokens 里建，读权限即可）。

### 6.3 下载

```bash
.venv/bin/python tools/download_models.py
```

断了直接重跑，已下好的会自动跳过。国内网络拉不动时先设镜像再重跑：

```bash
export HF_ENDPOINT=https://hf-mirror.com
.venv/bin/python tools/download_models.py
```

下完目录应长这样：

```
models/SheetSage2/          model.safetensors  config.json  ...
models/MERT-v2-FullSong/    model.safetensors  config.json  ...
```

---

## 7. 启动

```bash
./start.sh
```

浏览器会自动打开 <http://127.0.0.1:8777/>。**关掉这个终端窗口 = 停止服务。**

常用参数：

```bash
./start.sh --port 8898      # 换端口（8777 被占用时）
./start.sh --no-browser     # 不自动开浏览器
```

> 从 GitHub 下的是 zip（而不是 `git clone`）时，`start.sh` 可能没有可执行权限，
> 报 `permission denied`。执行一次即可：`chmod +x start.sh`。

等价的手动启动方式（不想用脚本时）：

```bash
.venv/bin/python -m app.server
```

---

## 8. 装完自检一下

```bash
.venv/bin/python tools/env_report.py
```

它会打印系统信息、解释器、ffmpeg 路径、权重目录是否存在等。重点看三条：

* **解释器** 指向本项目的 `.venv/bin/python`；
* **ffmpeg** 有路径（不是「未找到」）；
* **SheetSage2 权重 / MERT-v2-FullSong** 都 `exists`。

也可以直接开网页，看顶部**环境检测**面板：**红色叉是阻塞项**，缺权重或 ffmpeg 会
禁止开始扒谱；**黄色叹号是提醒**（例如「没有 NVIDIA 显卡」），不影响使用。

---

## 9. 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `zsh: command not found: brew` | Homebrew 没装或没加进 PATH | 见第 2 步；Apple Silicon 需 `eval "$(/opt/homebrew/bin/brew shellenv)"` |
| `permission denied: ./start.sh` | zip 下载丢了可执行位 | `chmod +x start.sh` |
| 报 `CUDA not available` / 一堆 `cuda` 报错 | 装了 CUDA 版 torch | Mac 只能 CPU 版：`pip uninstall torch torchaudio` 后按 5.2 重装（**不带** `+cu130`） |
| `RuntimeError: FFmpeg is required to read audio files` | PATH 上没有 ffmpeg | `brew install ffmpeg`；确认 `ffmpeg -version` 能输出版本 |
| 下权重报 `401` / `403` / `gated` / `authenticated` | 没在网页同意，或没登录 | 回到第 6 步：两个页面各点同意 + `huggingface-cli login` |
| 下权重 connection / timeout / resolve 失败 | 连不上 Hugging Face | `export HF_ENDPOINT=https://hf-mirror.com` 再重跑 |
| 装依赖卡在 `dynet38` / `nagisa` 编译报错 | 老原生包，Apple Silicon 上无轮子 | 用 `requirements-macos.txt`（已去掉这两个），别用 `requirements-base.txt` |
| `pip install torch` 报找不到匹配版本 | 用了 CUDA 后缀或换错 Python | 用 `python3.12` 建的 venv；装 `torch` 时不带本机标签 |
| 端口 8777 被占用 | 已经开着一个 SheetSage2 | 程序会直接打开那一个；要另起一个用 `./start.sh --port 8898` |
| 页面打开了但没声音 | 试听是浏览器离线渲染 | 先看浏览器是否静音 / 标签页是否被静音；与系统声卡无关 |
| `python3.12: command not found` | Python 3.12 没装好 | `brew install python@3.12`；或 `brew link python@3.12` |
| 装 Homebrew 卡住 | 外网 raw.githubusercontent.com 不通 | 换国内镜像脚本，或先在能上网的环境装；见 Homebrew 官方中文文档 |

还是不行时，把 `tools/env_report.py` 的输出 + 终端**最后 20 行报错**一起发出来，
比「它不工作」有用得多。也可参考仓库根的 [`ASK_AI.md`](../ASK_AI.md)（把报错贴给 AI 排查）。

---

## 10. 关于 GPU / Apple 芯片（MPS）的说明

* 本项目的设备判定（`app/worker.py`）**只看 NVIDIA CUDA**：有就上 GPU，没有就回 **CPU**。
  Mac 没有 NVIDIA 显卡，因此**一律走 CPU**。
* **不会**用 Apple 的 MPS 后端。不是因为 Mac 跑不了，而是主干模型
  MERT-v2-FullSong 在 MPS 上未做验证，贸然启用容易出现算子不支持或精度问题。
* 想固定设备：打开项目根目录的 `settings.json`，把 `"default_device"` 改成 `"cpu"`
  （默认 `"auto"` 在 Mac 上等价于 `cpu`）。改完重启 `./start.sh`。
* 没有显卡**不是错误**：环境检测里「CUDA 可用性」是黄色提醒，不影响出谱，只是慢。

---

## 11. 卸载 / 清理

本项目全在项目文件夹里，删掉即可，不写系统目录。若想更彻底：

```bash
# 删代码 + 虚拟环境 + 已下权重（权重最占地方，约 2.6 GB）
rm -rf sheetsage2-webui

# 可选：如果当初为它装的 Python / ffmpeg 也不要了
brew uninstall ffmpeg python@3.12
```

> `models/` 里那 2.6 GB 权重如果不打算再用，删掉它会瞬时省下一大块空间。

---

## 附：命令速查（照抄即可）

```bash
# 一次性安装
brew install python@3.12 ffmpeg
git clone https://github.com/3253473591/sheetsage2-webui.git
cd sheetsage2-webui
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install torch torchaudio
.venv/bin/python -m pip install -r requirements-macos.txt

# 下权重（先在这两个页面同意：
#   https://huggingface.co/m-a-p/SheetSage2
#   https://huggingface.co/m-a-p/MERT-v2-FullSong ）
.venv/bin/python -m pip install -U huggingface_hub
.venv/bin/huggingface-cli login
.venv/bin/python tools/download_models.py

# 启动
./start.sh
```

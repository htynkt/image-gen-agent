# 🎨 画灵屋 · 图片生成 Agent

> 一个能**陪你聊天、看懂图片、生成拼豆图和 AIGC 创意图**的个性化 AI 助手。
> 基于 **Agent Loop + Tool Use** 架构；**公众号对话框 + 小程序**双端。

这是一个**从零开始、渐进式学习**的 Agent 实战项目，参考 [LearnKuAI](https://github.com/xiaordong/LearnKuAI) 的阶段式路径搭建。

---

## ✨ 核心功能

| 能力 | 说明 |
|------|------|
| 🧩 **拼豆图纸** | 输入图片 → 按 Artkal 官方 159 色卡像素化 → 生成图纸（色号 + 红网格 + 材料清单）。**纯本地算法，零成本** |
| 🎨 **AIGC 创意图** | 输入提示语 → 调文生图大模型 → 生成全新图片 |
| 👀 **多模态对话** | 可以同时发**文字 + 图片**，AI 真的看图（gpt-4o 视觉），比如「把这个做成拼豆」 |
| 💬 **公众号对话框** | 聊天 / 问答 / 写文案 / 优化提示词 / 技巧咨询；生图引导去小程序 |
| 💁 **个性化 + 记忆** | 可配置称呼/语气/风格；按用户隔离历史，说「上次/之前」能调取 |
| 💰 **商业化就绪** | 模型分层降本、每用户配额限流、token 可观测 |

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| LLM | OpenAI 兼容接口（gpt-4o 多模态 + gpt-4o-mini 轻量对话 + 文生图） |
| 后端 | Python · FastAPI · Uvicorn（公众号 webhook + 小程序后端入口） |
| 前端 | 微信小程序（生图/拼豆，开发中） |
| 图像处理 | Pillow · NumPy · scikit-image（拼豆配色算法） |
| 配置 | python-dotenv · PyYAML |

---

## 📁 项目结构

```
first_agent/
├── agent.py                # 核心：Agent Loop + 工具 + 记忆 + 重试 + 轻量对话(chat_once)
├── backend/
│   ├── main.py             # FastAPI 服务：公众号 webhook + 预留小程序后端(/api/chat)
│   └── wechat.py           # 公众号对话框：欢迎语 + 关键词导航 + 轻量对话
├── skills/                 # 工具模块
│   ├── bead_art.py         # 拼豆图（本地算法，Artkal 159 色）
│   └── aigc_creative.py    # AIGC 创意图（文生图 API）
├── core/
│   ├── memory.py           # 记忆：profile / 历史(按用户隔离) / 上下文压缩
│   ├── logger.py           # 日志
│   └── quota.py            # 配额限流（每用户每日上限）
├── config/profile.yaml     # 个性化档案（称呼/语气/风格）
├── data/                   # 输入图 / 生成图 / 历史 / 日志 / 配额
└── requirements.txt
```

---

## 🚀 快速开始

### 1. 配置 API（自备 `.env`）

在项目根目录创建 `.env`：
```
API_KEY=你的key
BASE_URL=https://你的接口地址
```
> 需要一个 OpenAI 兼容的服务（同时支持 gpt-4o 对话 + 文生图）。
> ⚠️ `.env` 已在 `.gitignore` 中，不会上传到 git，可放心填自己的密钥。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

然后**二选一**即可👇

---

### 方式一：命令行直接跑（最快 · 纯文字对话）

在**项目根目录**执行：
```bash
python agent.py
```
直接在终端和 Agent 文字聊天，输 `quit` 退出。

- ✅ 最轻量，一行命令验证 Agent 核心（工具调用 / 记忆 / 重试）能否跑通
- ⚠️ 只支持文字；AIGC 生成的图会保存到 `data/outputs/`（自己去目录看）
- ⚠️ 上传图片 / 拼豆 / 看图，走小程序（见下）

### 方式二：启动后端服务（公众号 webhook + 小程序后端入口）

**终端**（项目根目录）：
```bash
uvicorn backend.main:app --reload --port 8000
```
验证：打开 http://localhost:8000/api/health → 看到 `{"status":"ok"}` 即成功。

> 这个后端既承载公众号 `/wechat`（对话框导航 + 轻量对话），也为小程序预留 `/api/chat`（生图/拼豆）。小程序前端开发中。

---

## 📲 公众号接入

`backend/wechat.py` 把 Agent 接入公众号对话框（复用 `agent_loop` / `chat_once`，零侵入）。

**对话框三层**：
1. **关注欢迎语**：一进来告诉用户能做什么；
2. **关键词导航**：用户说「生成图片/拼豆」→ 引导去菜单【创作】→ 小程序（**零 token**）；
3. **轻量对话**：聊天/问答/写描述/文案/咨询 → 单次调便宜模型（省 token）。

> 个人订阅号无客服消息接口，生图走小程序规避 5 秒超时。微信 2025 年底已把「开发接口管理」迁移到**微信开发者平台**（`developers.weixin.qq.com/platform/`），需配合内网穿透配置 `/wechat`。详见 `backend/wechat.py`。

---

## 📖 怎么用

| 入口 | 能做什么 |
|------|----------|
| 命令行 `python agent.py` | 纯文字对话 + AIGC 生图（图存 `data/outputs/`） |
| 公众号对话框 | 聊天 / 问答 / 写文案 / 优化提示词 / 技巧咨询；生图引导去菜单 |
| 小程序（开发中） | 生 AIGC 图 / 拼豆图纸（上传图、看图、保存到相册） |

---

## ⚙️ 可配置项

| 文件 | 配什么 |
|------|--------|
| `.env` | `API_KEY` / `BASE_URL` |
| `config/profile.yaml` | AI 怎么称呼你、语气、默认画风 |
| `agent.py` 的 `_HISTORY_KEYWORDS` | 触发「调取历史」的关键词（上次/之前/刚才…） |
| `agent.py` 的 `MODEL` / `CHEAP_MODEL` | 模型分层（多模态主力 / 轻量省钱） |
| `core/quota.py` 的 `DEFAULT_DAILY_LIMIT` | 每用户每日免费次数 |

---

## 💰 商业化设计

- **降本**：模型分层（纯文字走 gpt-4o-mini，约 4o 的 1/15）+ prompt caching + 历史按需加载；
- **控量**：每用户每日配额（`core/quota.py`），超额入口拦截不调模型；
- **变现**：公众号对话框引流 → 小程序生图（付费入口）。

---

## 🎓 这个项目怎么搭起来的（学习阶段）

1. **阶段 1** Agent Loop 基础骨架（while 循环 + tool_use）
2. **阶段 2** Tool Use 工具系统（拼豆图 + AIGC 创意图）
3. **阶段 3** Memory 记忆系统（个性化档案 + 对话持久化 + 上下文压缩）
4. **阶段 4** 生产增强（连接重试 + 日志 + 错误兜底）
5. **阶段 5** 前后端分离（曾用 Vue3 网页版，后废弃改小程序）
6. **阶段 6** 公众号接入 + 商业化（对话框导航、配额限流、模型分层）

---

## 🙏 致谢

- [LearnKuAI](https://github.com/xiaordong/LearnKuAI) —— Agent 学习路径参考
- [Artkal 拼豆色卡（Pixel-Beads）](https://www.pixel-beads.com/zh/artkal-bead-color-chart) —— 拼豆颜色数据来源

---

> 💡 这是一个学习项目，欢迎参考。如有问题欢迎提 issue。

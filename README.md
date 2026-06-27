# 🎨 图片生成 Agent

> 一个能**陪你聊天、看懂图片、生成拼豆图和 AIGC 创意图**的个性化 AI 助手。
> 基于 **Agent Loop + Tool Use** 架构，前后端分离（FastAPI + Vue3）。

这是一个**从零开始、渐进式学习**的 Agent 实战项目，参考 [LearnKuAI](https://github.com/xiaordong/LearnKuAI) 的阶段式路径搭建。

---

## ✨ 核心功能

| 能力 | 说明 |
|------|------|
| 🧩 **拼豆图纸** | 输入图片 → 按 Artkal 官方 159 色卡像素化 → 生成图纸（色号 + 红网格 + 材料清单）。**纯本地算法，零成本** |
| 🎨 **AIGC 创意图** | 输入提示语 → 调文生图大模型 → 生成全新图片 |
| 👀 **多模态对话** | 可以同时发**文字 + 图片**，AI 真的看图（gpt-4o 视觉），比如「把这个做成拼豆」 |
| 💁 **个性化** | 可配置称呼、语气、默认风格（`config/profile.yaml`） |
| 🧠 **记忆** | 保留你的语言习惯；说「上次/之前」时能调取历史对话 |
| 🔄 **稳健** | 对话/文生图自动重试、错误兜底、日志可查、长对话自动压缩 |

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| LLM | OpenAI 兼容接口（gpt-4o 多模态对话 + 文生图） |
| 后端 | Python · FastAPI · Uvicorn |
| 前端 | Vue3 · Vite |
| 图像处理 | Pillow · NumPy · scikit-image（拼豆配色算法） |
| 配置 | python-dotenv · PyYAML |

---

## 📁 项目结构

```
first_agent/
├── agent.py                # 核心：Agent Loop + 工具注册 + 记忆 + 重试
├── backend/
│   └── main.py             # FastAPI 后端（/api/chat，复用 agent_loop）
├── frontend/               # Vue3 + Vite 前端
│   ├── src/components/     # ChatWindow / MessageBubble
│   └── public/             # 头像（agent.png / user.png）
├── skills/                 # 工具模块
│   ├── bead_art.py         # 拼豆图（本地算法，Artkal 159 色）
│   └── aigc_creative.py    # AIGC 创意图（文生图 API）
├── core/
│   ├── memory.py           # 记忆：profile / 历史 / 上下文压缩
│   └── logger.py           # 日志
├── config/profile.yaml     # 个性化档案（称呼/语气/风格）
├── data/                   # 输入图 / 生成图 / 上传图 / 对话历史 / 日志
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

### 2. 启动后端（终端 1，在项目根目录）

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```
验证：打开 http://localhost:8000/api/health → 看到 `{"status":"ok"}` 即成功。

### 3. 启动前端（终端 2）

```bash
cd frontend
npm install
npm run dev
```

### 4. 打开界面

浏览器访问 **http://localhost:5173** 🎉

---

## 📖 怎么用

| 你输入 | Agent 干什么 |
|--------|-------------|
| 「画一只赛博朋克柴犬」 | 调 AIGC 生成创意图 |
| 上传图片 + 「做成拼豆」 | 看图 → 生成拼豆图纸（色号+清单） |
| 「把**上次**那张改成黑白」 | 引用历史 → 找到并修改 |
| 上传图片 + 「这张图里是什么」 | 直接看图回答 |

> 界面里生成的图可以**点击放大**、**一键下载**。

---

## ⚙️ 可配置项

| 文件 | 配什么 |
|------|--------|
| `.env` | `API_KEY` / `BASE_URL` |
| `config/profile.yaml` | AI 怎么称呼你、语气、默认画风 |
| `frontend/public/agent.png`、`user.png` | AI 和你的头像（圆形，正方形图最佳） |
| `agent.py` 的 `_HISTORY_KEYWORDS` | 触发「调取历史」的关键词（上次/之前/刚才…） |

---

## 🎓 这个项目怎么搭起来的（学习阶段）

分阶段渐进式开发，每个阶段一个 commit：

1. **阶段 1** Agent Loop 基础骨架（while 循环 + tool_use）
2. **阶段 2** Tool Use 工具系统（拼豆图 + AIGC 创意图）
3. **阶段 3** Memory 记忆系统（个性化档案 + 对话持久化 + 上下文压缩）
4. **阶段 4** 生产增强（连接重试 + 日志 + 错误兜底）
5. **阶段 5** 前后端分离（FastAPI + Vue3，多模态对话界面）

---

## 🙏 致谢

- [LearnKuAI](https://github.com/xiaordong/LearnKuAI) —— Agent 学习路径参考
- [Artkal 拼豆色卡（Pixel-Beads）](https://www.pixel-beads.com/zh/artkal-bead-color-chart) —— 拼豆颜色数据来源

---

> 💡 这是一个学习项目，欢迎参考。如有问题欢迎提 issue。

"""
FastAPI 后端服务
================
承载两件事：
  1. 公众号 webhook（/wechat，见 wechat.py）—— 对话框导航 + 轻量对话
  2. 预留小程序后端入口（/api/chat）—— 复用 agent_loop，供小程序调用生图/拼豆
（原 Vue3 网页版 frontend 已废弃，生图改走小程序。）

核心思想：通过 sys.path + os.chdir 复用根目录的 agent_loop，**不改它内部一行**。

启动（必须在【项目根目录】执行，保证 data/ 相对路径写对位置）：
    uvicorn backend.main:app --reload --port 8000
"""
import os        # 路径操作、改工作目录
import sys       # 修改 Python 的模块搜索路径
import re        # 正则：从回复里抽取图片路径
import uuid      # 生成唯一的上传文件名
import base64    # 解码前端传来的 base64 图片
import json      # 解析微信登录返回 / 读写 JSON
import urllib.request, urllib.parse  # 登录时调微信 jscode2session（标准库）
from pathlib import Path  # 面向对象的路径操作

# ============================================================
# 关键：让后端能 import 根目录的 agent，并保证相对路径写对位置
# ============================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # 本文件(backend/main.py)上一级 = 项目根
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)  # 把项目根加进模块搜索路径，下面才能 import agent
os.chdir(PROJECT_ROOT)  # 切换工作目录到项目根（agent/core/skills 都用 data/ 相对路径，cwd 必须对）

# 这一句会触发 agent.py 里的 load_dotenv() 和建 OpenAI client
from agent import agent_loop  # 复用 Agent 核心（业务逻辑零侵入）

from fastapi import FastAPI, HTTPException, File, UploadFile, Query, Form  # Web 框架 + 文件上传 + 查询参数 + 表单字段
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件
from fastapi.staticfiles import StaticFiles         # 把一个目录挂成静态文件服务
from pydantic import BaseModel                      # 定义请求体的数据结构（自动校验）
from core.gallery import (                          # 画廊系统（小程序主页瀑布流）
    seed_if_empty, CATEGORIES,
    list_by_category, search as gallery_search,
    toggle_favorite, list_favorites, annotate_liked, add_image,
)
from core.users import get_user, save_user          # 用户信息（昵称 / 头像）

app = FastAPI(title="图片生成 Agent API")  # 创建 FastAPI 应用实例

# ---- 公众号渠道：挂载微信适配层路由（复用 agent_loop，零侵入）----
from .wechat import router as wechat_router  # 相对导入：取【同包 backend】里的 wechat.py（避免和 site-packages 的第三方 wechat 包撞名）
app.include_router(wechat_router)           # 把 /wechat 路由挂到 app 上

# ---- 开发期 CORS 双保险（vite proxy 已经免跨域，这里再放行 5173）----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # 允许哪些前端地址访问
    allow_methods=["*"],  # 允许所有 HTTP 方法（GET/POST…）
    allow_headers=["*"],  # 允许所有请求头
)

DATA_DIR = Path("data").resolve()        # data 目录的绝对路径
UPLOAD_DIR = DATA_DIR / "uploads"        # 用户上传图的落盘处
OUTPUT_DIR = DATA_DIR / "outputs"        # Agent 生成的图存放处
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # 确保 uploads 目录存在（没有就建）
AVATAR_DIR = DATA_DIR / "avatars"             # 用户头像存放处
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# ---- 静态挂载：前端用 /files/... 就能直接取到图 ----
app.mount("/files/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")  # outputs → /files/outputs
app.mount("/files/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")  # uploads → /files/uploads
app.mount("/files/avatars", StaticFiles(directory=str(AVATAR_DIR)), name="avatars")  # avatars → /files/avatars

seed_if_empty()  # 首次启动：把 data/outputs/ 已有图入库（画廊种子数据）


@app.get("/api/health")  # 健康检查接口（GET /api/health）
def health():
    """探活 + 验证 import 链是否通"""
    return {"status": "ok"}  # 返回 ok，说明后端起来了、agent 也 import 成功


class ChatRequest(BaseModel):  # 用 Pydantic 定义 /api/chat 的请求体结构（自动校验字段）
    text: str = ""             # 文字内容（默认空串）
    image: str | None = None   # 图片：data URL（data:image/...;base64,...）或纯 base64（可选）
    user_id: str = "web"       # 用户标识（小程序传 openid，网页版默认 web）


# 从 reply 文本里抠出图片【绝对路径】的正则（Windows 反斜杠 / 正斜杠都兼容）
# 工具返回形如 "...已生成：D:\\...\\data\\outputs\\bead_pattern_3.png"
_PATH_RE = re.compile(r"[A-Za-z]:[\\\/][^\s：:，,。、）)]+\.(?:png|jpg|jpeg|webp)", re.I)


def _abs_to_url(abs_path: str) -> str | None:
    """把绝对路径转成前端可访问的 /files/... URL；不在 data/ 下则返回 None"""
    try:
        rel = Path(abs_path).resolve().relative_to(DATA_DIR)  # 算出它相对 data/ 的路径（如 outputs/xxx.png）
    except ValueError:                                        # 不在 data/ 目录下
        return None
    return "/files/" + rel.as_posix()  # 拼成 /files/outputs/xxx.png（统一用正斜杠）


@app.post("/api/chat")  # 主接口：POST /api/chat
def chat(req: ChatRequest):
    """主接口：收文字 + 可选图片 → 调 agent_loop → 返回 {reply, images}"""
    if not req.text and not req.image:  # 文字和图片都没给
        raise HTTPException(400, "text 和 image 至少给一个")  # 返回 400 错误

    # 1. 图片 base64 落盘到 data/uploads/
    image_path = None
    if req.image:                                       # 有图片
        b64 = req.image.split(",", 1)[-1]               # 去掉 "data:image/...;base64," 前缀，只留纯 base64
        ext = "jpg" if "jpeg" in req.image[:30].lower() else "png"  # 根据前缀判断扩展名
        fname = f"{uuid.uuid4().hex}.{ext}"             # 用 uuid 生成唯一文件名（如 3f9a....jpg）
        image_path = str(UPLOAD_DIR / fname)            # 拼出完整落盘路径
        with open(image_path, "wb") as f:               # 二进制写文件
            f.write(base64.b64decode(b64))              # base64 解码后写入磁盘

    # 2. 复用 agent_loop（不改它内部）
    try:
        reply = agent_loop(req.text, user_image=image_path, user_id=req.user_id)  # 按 user_id 隔离历史
    except Exception as e:                                    # Agent 执行出错
        raise HTTPException(500, f"agent 执行失败: {e}")       # 返回 500，不让前端看到堆栈

    # 3. 从 reply 抽出图片绝对路径 → 转成 /files URL（结构化返回，方便前端直接显示）
    images = []
    for m in _PATH_RE.findall(reply or ""):  # 用正则找出回复里所有的图片绝对路径
        url = _abs_to_url(m)                 # 每个转成前端可访问的 URL
        if url and url not in images:        # 有效且没重复
            images.append(url)

    return {"reply": reply, "images": images}  # 返回：文字回复 + 图片 URL 列表


# ============================================================
# 小程序接口：登录 + 画廊（分类/搜索/收藏）+ AI 问答(文件上传)
# ============================================================

class LoginRequest(BaseModel):
    code: str   # 小程序 wx.login 拿到的 code


@app.post("/api/login")
def login(req: LoginRequest):
    """小程序登录：用 wx.login 的 code 换 openid（调微信 jscode2session）。"""
    appid = os.getenv("WX_APPID", "")
    secret = os.getenv("WX_SECRET", "")
    if not appid or not secret:
        # 没配小程序密钥 → 用 code 造个临时 openid（开发期兜底，不阻塞前端调试）
        openid = "dev_" + req.code[:12]
        user = get_user(openid) or {}
        return {"openid": openid, "nickname": user.get("nickname", ""), "avatar": user.get("avatar", ""),
                "warning": "未配置 WX_APPID/WX_SECRET，使用临时 openid"}
    url = ("https://api.weixin.qq.com/sns/jscode2session"
           f"?appid={appid}&secret={secret}&js_code={urllib.parse.quote(req.code)}"
           "&grant_type=authorization_code")
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:    # 调微信接口换 openid
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise HTTPException(500, f"调微信登录失败: {e}")
    if "openid" not in data:
        raise HTTPException(400, f"微信登录失败: {data}")
    openid = data["openid"]
    user = get_user(openid) or {}
    return {"openid": openid, "nickname": user.get("nickname", ""), "avatar": user.get("avatar", "")}


@app.post("/api/profile")
def update_profile(openid: str = Form(""), nickname: str = Form(""), avatar: UploadFile | None = File(None)):
    """更新用户昵称 + 头像（头像上传文件存 data/avatars/，跨设备同步）。"""
    avatar_url = ""
    if avatar and avatar.filename:
        ext = (avatar.filename.split(".")[-1] or "png").lower()
        fname = f"{openid}.{ext}"
        with open(str(AVATAR_DIR / fname), "wb") as f:
            f.write(avatar.file.read())
        avatar_url = f"/files/avatars/{fname}"
    user = save_user(openid, nickname=nickname or None, avatar=avatar_url or None)
    return {"ok": True, "nickname": user.get("nickname", ""), "avatar": user.get("avatar", "")}


@app.get("/api/categories")
def categories():
    """主页分类导航列表。"""
    return {"categories": CATEGORIES}


@app.get("/api/gallery")
def gallery(category: str = Query("最热"), page: int = Query(1, ge=1), user_id: str = Query("")):
    """按分类分页列出图片（瀑布流）；user_id 用于标注该用户是否已收藏。"""
    items = list_by_category(category, page=page, page_size=20)
    if user_id:
        items = annotate_liked(items, user_id)
    return {"category": category, "page": page, "items": items}


@app.get("/api/search")
def search(kw: str = Query(""), user_id: str = Query("")):
    """搜索图片（标题/分类）。"""
    items = gallery_search(kw)
    if user_id:
        items = annotate_liked(items, user_id)
    return {"kw": kw, "items": items}


class FavoriteRequest(BaseModel):
    image_id: str
    user_id: str


@app.post("/api/favorite")
def favorite(req: FavoriteRequest):
    """切换收藏（收藏/取消）。"""
    liked, total = toggle_favorite(req.image_id, req.user_id)
    return {"liked": liked, "favorites": total}


@app.get("/api/favorites")
def favorites(user_id: str = Query(...)):
    """某用户的收藏列表。"""
    items = list_favorites(user_id)
    items = annotate_liked(items, user_id)
    return {"items": items}


@app.post("/api/chat_upload")
def chat_upload(text: str = "", user_id: str = Form("mini"), file: UploadFile | None = File(None)):
    """小程序 AI 问答：multipart 上传图片 + 文字 → 调 agent_loop → 返回 {reply, images}。
    小程序用 wx.uploadFile 发文件（不是 base64），故单独开这个接口。"""
    image_path = None
    if file:                                                # 有上传图片
        ext = (file.filename or "x.png").split(".")[-1].lower() or "png"
        fname = f"{uuid.uuid4().hex}.{ext}"
        image_path = str(UPLOAD_DIR / fname)
        with open(image_path, "wb") as f:
            f.write(file.file.read())                      # 落盘到 data/uploads/
    if not text and not image_path:
        raise HTTPException(400, "text 和 file 至少给一个")
    try:
        reply = agent_loop(text, user_image=image_path, user_id=user_id)  # 小程序入口：按 openid 隔离历史
    except Exception as e:
        raise HTTPException(500, f"agent 执行失败: {e}")
    images = []
    for m in _PATH_RE.findall(reply or ""):
        url = _abs_to_url(m)
        if url and url not in images:
            images.append(url)
    # 用户生成的图自动入库（按文件名含 bead 判断拼豆/AIGC）
    for img_url in images:
        fname = img_url.split("/")[-1]
        cat = "拼豆图" if "bead" in fname.lower() else "AIGC创意图"
        add_image(fname, os.path.splitext(fname)[0], cat, img_url, author="用户")
    return {"reply": reply, "images": images}

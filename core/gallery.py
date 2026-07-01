"""
画廊系统（小程序主页瀑布流）
============================
管理图片元数据：分类列表、搜索、收藏。
- data/gallery.json：图片元数据 [{id,title,category,url,author,favorites,created_at}]
- data/favorites.json：用户收藏 {user_id: [image_id, ...]}
- 首次启动 seed_if_empty()：扫 data/outputs/ 把已有图入库（bead→拼豆图，aigc→AIGC创意图）
"""
import json
import os
from datetime import datetime

GALLERY_PATH = "data/gallery.json"
FAVORITES_PATH = "data/favorites.json"
GALLERY_IMG_DIR = "data/outputs"   # 图片实际存放（复用 agent 生成目录）

# 主页分类导航（顺序即展示顺序）
CATEGORIES = ["最热", "拼豆图", "AIGC创意图", "风景图", "动漫人物图", "PS海报", "PS素材"]


def _load_json(path):
    """读 JSON；不存在/损坏返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_json(path, data):
    """写 JSON（确保目录存在）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_gallery():
    return _load_json(GALLERY_PATH) or []


def _load_favorites():
    return _load_json(FAVORITES_PATH) or {}


def _img_size(fname):
    """读图片宽高（Pillow）；失败返回 (1,1)。"""
    try:
        from PIL import Image
        with Image.open(os.path.join(GALLERY_IMG_DIR, fname)) as im:
            return im.size
    except Exception:
        return 1, 1


def seed_if_empty():
    """首次启动：扫 data/outputs/ 把已有图入库（按文件名归类）。"""
    if _load_gallery():               # 已有数据，跳过
        return
    items = []
    if os.path.exists(GALLERY_IMG_DIR):
        for fname in os.listdir(GALLERY_IMG_DIR):
            low = fname.lower()
            if not low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            if "bead" in low:
                cat = "拼豆图"
            elif "aigc" in low:
                cat = "AIGC创意图"
            else:
                cat = "AIGC创意图"    # 默认归 AIGC 创意图
            w, h = _img_size(fname)
            items.append({
                "id": fname,
                "title": os.path.splitext(fname)[0],
                "category": cat,
                "url": f"/files/outputs/{fname}",
                "author": "画灵屋",
                "favorites": 0,
                "width": w, "height": h,
                "created_at": datetime.now().isoformat(),
            })
    _save_json(GALLERY_PATH, items)


def add_image(image_id, title, category, url, author="用户"):
    """用户生成的图（AIGC/拼豆）入库。已存在则跳过。"""
    items = _load_gallery()
    if any(x["id"] == image_id for x in items):
        return
    fname = url.split("/")[-1]
    w, h = _img_size(fname)
    items.append({
        "id": image_id, "title": title, "category": category,
        "url": url, "author": author, "favorites": 0,
        "width": w, "height": h,
        "created_at": datetime.now().isoformat(),
    })
    _save_json(GALLERY_PATH, items)


def list_by_category(category, page=1, page_size=20):
    """按分类分页列出（'最热' 按收藏数降序）。"""
    items = _load_gallery()
    if category == "最热":
        pool = sorted(items, key=lambda x: x.get("favorites", 0), reverse=True)
    else:
        pool = [x for x in items if x.get("category") == category]
    start = (page - 1) * page_size
    return pool[start:start + page_size]


def search(kw):
    """按关键词搜索标题/分类。"""
    kw = (kw or "").strip()
    if not kw:
        return []
    items = _load_gallery()
    return [x for x in items if kw in x.get("title", "") or kw in x.get("category", "")]


def toggle_favorite(image_id, user_id):
    """切换某用户对某图的收藏；返回 (是否已收藏, 该图总收藏数)。"""
    items = _load_gallery()
    favs = _load_favorites()
    user_set = set(favs.get(user_id, []))
    if image_id in user_set:           # 已收藏 → 取消
        user_set.discard(image_id)
        liked = False
    else:                              # 未收藏 → 收藏
        user_set.add(image_id)
        liked = True
    favs[user_id] = list(user_set)
    _save_json(FAVORITES_PATH, favs)
    # 重算该图总收藏数（统计所有收藏了它的用户）
    total = sum(1 for ids in favs.values() if image_id in ids)
    for x in items:
        if x["id"] == image_id:
            x["favorites"] = total
            _save_json(GALLERY_PATH, items)
            break
    return liked, total


def list_favorites(user_id):
    """某用户收藏的图片列表。"""
    favs = _load_favorites()
    ids = favs.get(user_id, [])
    items = _load_gallery()
    return [x for x in items if x["id"] in ids]


def annotate_liked(items, user_id):
    """给图片列表加 'liked' 字段（是否被该用户收藏），供前端显示收藏状态。"""
    favs = _load_favorites()
    user_set = set(favs.get(user_id, []))
    for x in items:
        x["liked"] = x["id"] in user_set
    return items

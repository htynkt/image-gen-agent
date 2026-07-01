"""
用户信息存储（昵称 / 头像）
========================
data/users.json: {openid: {nickname, avatar, created_at}}
头像文件单独存在 data/avatars/{openid}.png，这里只存 url。
登录时顺带返回用户信息，前端据此显示头像/昵称。
"""
import json
import os
from datetime import datetime

USERS_PATH = "data/users.json"


def _load() -> dict:
    if not os.path.exists(USERS_PATH):
        return {}
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    with open(USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(openid: str) -> dict:
    """取某用户信息；没有返回 None。"""
    return _load().get(openid)


def save_user(openid: str, nickname: str = None, avatar: str = None) -> dict:
    """更新用户昵称/头像（只更新传了的字段）；返回更新后的用户信息。"""
    data = _load()
    u = data.get(openid, {})
    if nickname is not None:
        u["nickname"] = nickname
    if avatar is not None:
        u["avatar"] = avatar
    if "created_at" not in u:
        u["created_at"] = datetime.now().isoformat()
    data[openid] = u
    _save(data)
    return u

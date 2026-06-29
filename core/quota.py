"""
配额限流（商业化基础·第二步）
============================
每用户每日调用上限：超额在【入口】就拦截，不调大模型，省 token。
存储 data/quota.json：{user_id: {"date": "YYYY-MM-DD", "count": N}}，日期一变自动重置。
"""
import json                       # 读写配额文件
import os                         # 判断/创建目录
from datetime import date         # 取当天日期（跨天自动重置）

QUOTA_PATH = "data/quota.json"    # 配额文件存放路径
DEFAULT_DAILY_LIMIT = 3          # 每用户每日免费次数（可调；商业化后可分免费/会员档）


def _today() -> str:
    """返回当天日期字符串，如 '2026-06-28'（用于跨天重置判断）。"""
    return date.today().isoformat()


def _load() -> dict:
    """读配额文件；不存在/损坏则返回空字典（绝不因配额文件损坏而崩）。"""
    if not os.path.exists(QUOTA_PATH):
        return {}
    try:
        with open(QUOTA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    """写配额文件（确保目录存在）。"""
    os.makedirs(os.path.dirname(QUOTA_PATH), exist_ok=True)
    with open(QUOTA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_and_consume(user_id: str, limit: int = DEFAULT_DAILY_LIMIT):
    """
    检查并消耗 1 次配额（在 agent_loop 入口调用，所有渠道统一受限）。
    返回 (是否允许, 已用次数, 上限)：
      - 允许 → 计数 +1 并保存
      - 不允许 → 不计数，调用方应返回"额度用完"提示（不调模型）
    跨天自动重置：日期一变，计数归零。
    """
    today = _today()
    data = _load()
    rec = data.get(user_id)
    # 没有记录 或 日期变了 → 重置计数
    if not rec or rec.get("date") != today:
        rec = {"date": today, "count": 0}
    # 已达上限：不允许，且不计数（避免超额请求继续累加）
    if rec["count"] >= limit:
        return False, rec["count"], limit
    # 还有额度：计数 +1
    rec["count"] += 1
    data[user_id] = rec
    _save(data)
    return True, rec["count"], limit

"""
日志系统（阶段5：可观测性）
========================
把 Agent 运行时的关键事件写到文件（data/agent.log），事后能查：
  - 每次工具调用（名字 / 参数 / 成功 / 失败）
  - 各种错误（API 错误码、网络异常、重试）

用 Python 标准库 logging，不用装额外依赖。
控制台仍用现有的 print（给用户看），日志文件用于「事后排查」。
"""
import os
import logging

LOG_PATH = "data/agent.log"


def setup_logger(name: str = "agent", path: str = LOG_PATH) -> logging.Logger:
    """
    配置并返回一个 logger：写文件（data/agent.log）。
    多个模块用同一个 name 会共享（避免重复加 handler）。
    """
    logger = logging.getLogger(name)
    if logger.handlers:  # 已经配过了，直接返回（避免重复输出）
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件日志（追加写入，长期保留运行记录）
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger

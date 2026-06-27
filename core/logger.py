"""
日志系统（阶段5：可观测性）
========================
把 Agent 运行时的关键事件写到文件（data/agent.log），事后能查：
  - 每次工具调用（名字 / 参数 / 成功 / 失败）
  - 各种错误（API 错误码、网络异常、重试）

用 Python 标准库 logging，不用装额外依赖。
控制台用 print（给用户看实时进度），日志文件用于「事后排查」。
"""
import os        # 创建日志所在目录
import logging   # Python 标准库的日志模块

LOG_PATH = "data/agent.log"  # 日志文件的存放路径


def setup_logger(name: str = "agent", path: str = LOG_PATH) -> logging.Logger:
    """
    配置并返回一个 logger：把日志写到文件（data/agent.log）。
    多个模块用同一个 name 调用会拿到同一个 logger（避免重复加 handler 导致日志重复输出）。
    """
    logger = logging.getLogger(name)  # 按名字取/建一个 logger（同名的就是同一个）
    if logger.handlers:               # 如果它已经有 handler（说明之前已配过）
        return logger                  # 直接返回，不重复配置（否则同一条日志会输出多份）
    logger.setLevel(logging.INFO)     # 设置日志级别：INFO 及以上才记录（DEBUG 不记）

    fmt = logging.Formatter(          # 定义每条日志的输出格式
        "%(asctime)s | %(levelname)-7s | %(message)s",  # 时间 | 级别(左对齐7字符) | 内容
        datefmt="%Y-%m-%d %H:%M:%S",                     # 时间格式
    )

    os.makedirs(os.path.dirname(path), exist_ok=True)  # 确保日志目录（data/）存在
    fh = logging.FileHandler(path, encoding="utf-8")   # 创建文件 handler（追加写入，utf-8）
    fh.setFormatter(fmt)                               # 给 handler 套上上面的格式
    logger.addHandler(fh)                              # 把 handler 挂到 logger 上

    return logger  # 返回配好的 logger

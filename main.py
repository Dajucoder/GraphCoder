"""
GraphCoder 最小可运行入口
"""

import logging
import os

from src.api.cli import main

logger = logging.getLogger("graphcoder")
if not logger.handlers:
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)

if __name__ == "__main__":
    logger.info("启动命令行入口 cwd=%s", os.getcwd())
    main()

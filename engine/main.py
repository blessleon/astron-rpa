import os
import sys

import psutil
from astronverse.scheduler.__main__ import main

# from scripts.meta_build import MetaBuilder


def _kill_children():
    """退出前清理所有子进程（astron_router、browser_bridge 等进程）"""
    try:
        current = psutil.Process()
        for child in current.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception:
        pass


if __name__ == "__main__":
    # MetaBuilder()
    os.environ["DEBUG"] = "1"
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        _kill_children()
        sys.exit(0)

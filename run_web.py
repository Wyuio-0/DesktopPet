"""Google NotebookLM 网页版调试入口。

直接运行此脚本即可在默认浏览器打开独立网页端：
    python run_web.py
"""

import argparse
import sys
import os

# 确保项目根路径正确引入
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from web.server import run

def main():
    parser = argparse.ArgumentParser(description="Amiya NotebookLM Web 调试工作台")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="监听地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="监听端口 (默认 5050)")
    parser.add_argument("--no-browser", action="store_true", help="启动时不自动打开浏览器")
    args = parser.parse_args()

    try:
        run(host=args.host, port=args.port, open_browser=not args.no_browser)
    except KeyboardInterrupt:
        print("\n[NotebookLM Web] 服务已手动停止。")

if __name__ == "__main__":
    main()

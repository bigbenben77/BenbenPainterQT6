# run.py - 简化版
import sys
import os
import traceback

# 确保当前目录在 Python 路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"程序运行出错: {e}")
        traceback.print_exc()
        input("按任意键退出...")
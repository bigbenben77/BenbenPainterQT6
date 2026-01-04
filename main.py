# main.py - 简化版
import sys
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow


def main():
    """应用程序入口"""
    app = QApplication(sys.argv)

    # 设置应用属性
    app.setApplicationName("笨笨画图")
    app.setOrganizationName("笨笨工作室")

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
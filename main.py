import logging
import sys
import threading

from PyQt6.QtWidgets import QApplication, QMainWindow

from CalibBoardStitcher.Utils import logging_config
from QtUI.CalibBoardStitcherUI import CalibBoardStitcherUI
from Workflow.MainWorkflow import MainWorkflow


def main():
    # 初始化日志
    logging_config()

    # 创建停止信号
    stop_event = threading.Event()

    # 初始化UI
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    ui = CalibBoardStitcherUI()
    ui.setupUi(main_window)
    main_window.show()

    # 初始化工作流
    workflow = MainWorkflow(ui, stop_event)
    workflow.run()

    # 等待退出
    ret = app.exec()
    logging.info("Stitcher exit with code: {}".format(ret))
    stop_event.set()
    sys.exit(ret)


if __name__ == '__main__':
    main()

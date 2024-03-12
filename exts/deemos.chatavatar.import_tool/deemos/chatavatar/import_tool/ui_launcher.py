import sys
from PySide6.QtWidgets import QApplication
import Load_UI, web_funcs
import argparse

from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtCore import QUrl, QObject, Signal, QTimer

class Pinger(QObject):
    requestFinished = Signal(bool)  # 发送请求是否成功的信号

    def __init__(self, url, parent=None):
        super(Pinger, self).__init__(parent)
        self.url = url
        self.network_manager = QNetworkAccessManager(self)
        self.network_manager.finished.connect(self.onRequestFinished)

    def send_ping(self):
        req = QNetworkRequest(QUrl(self.url + "/ping"), transferTimeout=900)
        self.network_manager.get(req)

    def onRequestFinished(self, reply):
        if reply.error() != QNetworkReply.NoError:
            self.requestFinished.emit(False)
        else:
            self.requestFinished.emit(True)


def parse_args():
    parser = argparse.ArgumentParser(description='Process host and port.')
    parser.add_argument('--url', required=True, type=str, help='Request url')
    
    args = parser.parse_args()
    return args

def main(args):
    web_op_handler = web_funcs.WebFuncs(url=args.url)
    pinger = Pinger(url=args.url)
    pinger.requestFinished.connect(lambda success: app.quit() if not success else None)

    app = QApplication(sys.argv)
    window = Load_UI.CustomWindow(web_op_handler, "local")
    window.show()

    timer = QTimer()
    timer.timeout.connect(pinger.send_ping)
    timer.start(1000)

    sys.exit(app.exec())

if __name__ == '__main__':
    main(parse_args())
# -*- coding:utf-8 -*-
import sys
import os
import time
import json

from PySide6.QtCore import Qt, QThread, Signal, QDateTime
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QApplication,
    QLabel,
    QLineEdit,
    QSlider,
    QPushButton,
    QGridLayout,
    QDateTimeEdit
)
from config import global_config
from timer import Timer
from JdSession import Session
from utils import (
    send_wechat,
    get_random_useragent)
from log import logger

NUM_LABEL_FORMAT = '商品购买数量[{0}]个'
STOCK_LABEL_FORMAT = '库存查询间隔[{0}]毫秒'
DATA_FORMAT = '%H:%M:%S'

if getattr(sys, 'frozen', False):
    absPath = os.path.dirname(os.path.abspath(sys.executable))
elif __file__:
    absPath = os.path.dirname(os.path.abspath(__file__))


class JdBuyerUI(QWidget):

    def __init__(self):
        super().__init__()
        self.session = Session()
        self.ticketThread = TicketThread(self.session)
        self.ticketThread.ticketSignal.connect(self.ticketSignal)
        self.initUI()
        self.loadData()

    def loadData(self):
        with open(os.path.join(absPath, 'config.json'), "rb") as f:
            self.config = json.load(f)
        self.skuEdit.setText(self.config.get('skuId'))
        self.areaEdit.setText(self.config.get('areaId'))
        self.passwordEdit.setText(self.config.get('password'))
        self.numSlider.setValue(self.config.get('count'))
        self.stockSlider.setValue(self.config.get('stockInterval'))
        self.numLabel.setText(
            NUM_LABEL_FORMAT.format(self.config.get('count')))
        self.stockLabel.setText(STOCK_LABEL_FORMAT.format(
            self.config.get('stockInterval')))
        self.venderEdit.setText(self.config.get('venderId'))
        self.catEdit.setText(self.config.get('cat'))

    def saveData(self):
        with open(os.path.join(absPath, 'config.json'), 'w', encoding='utf-8') as f:
            # json.dump(my_list,f)
            # 直接显示中文,不以ASCII的方式显示
            # json.dump(my_list,f,ensure_ascii=False)
            # 显示缩进
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def initUI(self):
        grid = QGridLayout()
        grid.setSpacing(10)

        # 商品SKU
        skuLabel = QLabel('商品SKU')
        self.skuEdit = QLineEdit()
        grid.addWidget(skuLabel, 1, 1)
        grid.addWidget(self.skuEdit, 1, 2)

        # 区域ID
        areaLabel = QLabel('地区ID')
        self.areaEdit = QLineEdit()
        grid.addWidget(areaLabel, 2, 1)
        grid.addWidget(self.areaEdit, 2, 2)

        # 购买数量
        self.numLabel = QLabel(NUM_LABEL_FORMAT.format(1))
        self.numSlider = QSlider(Qt.Orientation.Horizontal, self)
        self.numSlider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.numSlider.setMinimum(1)
        self.numSlider.setMaximum(9)
        self.numSlider.valueChanged.connect(self.valuechange)
        grid.addWidget(self.numLabel, 1, 3)
        grid.addWidget(self.numSlider, 1, 4)

        # 商品查询间隔
        self.stockLabel = QLabel(STOCK_LABEL_FORMAT.format(3))
        self.stockSlider = QSlider(Qt.Orientation.Horizontal, self)
        self.stockSlider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.stockSlider.setMinimum(10)
        self.stockSlider.setMaximum(10000)
        self.stockSlider.valueChanged.connect(self.stockValuechange)
        grid.addWidget(self.stockLabel, 2, 3)
        grid.addWidget(self.stockSlider, 2, 4)

        # 支付密码
        passwordLabel = QLabel('支付密码')
        self.passwordEdit = QLineEdit()
        self.passwordEdit.setEchoMode(QLineEdit.EchoMode.Password)
        self.passwordEdit.setPlaceholderText('使用虚拟资产时填写')
        self.passwordEdit.textChanged.connect(self.textChanged)
        grid.addWidget(passwordLabel, 3, 1)
        grid.addWidget(self.passwordEdit, 3, 2)

        # 开始时间
        buyTimeLabel = QLabel('定时开始执行时间')
        self.buyTimeEdit = QDateTimeEdit(QDateTime.currentDateTime(), self)
        self.buyTimeEdit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        grid.addWidget(buyTimeLabel, 3, 3)
        grid.addWidget(self.buyTimeEdit, 3, 4)

        # 经销商ID
        venderLabel = QLabel('经销商ID')
        self.venderEdit = QLineEdit()
        grid.addWidget(venderLabel, 4, 1)
        grid.addWidget(self.venderEdit, 4, 2)

        # 商品分类码
        catLabel = QLabel('商品分类码')
        self.catEdit = QLineEdit()
        grid.addWidget(catLabel, 4, 3)
        grid.addWidget(self.catEdit, 4, 4)

        #商品链接
        urlLabel = QLabel('商品链接')
        self.urlEdit = QLineEdit()
        grid.addWidget(urlLabel, 5, 1)
        grid.addWidget(self.urlEdit, 5,2,1,3)

        # 控制按钮
        self.endButton = QPushButton("结束")
        self.endButton.clicked.connect(self.endClick)
        self.startButton = QPushButton("开始")
        self.startButton.clicked.connect(self.beginClick)
        grid.addWidget(self.endButton, 7, 1, 1, 2)
        grid.addWidget(self.startButton, 7, 3, 1, 2)

        self.endButton.setDisabled(True)

        # 信息展示
        self.infoLabel = QLabel()
        self.infoLabel.setText("当前登录状态是: {0}".format(
            '已登录' if self.session.isLogin else '未登录'))
        grid.addWidget(self.infoLabel, 8, 1, 2, 4)

        # 二维码
        self.qrLabel = QLabel()
        grid.addWidget(self.qrLabel, 12, 1, 1, 2)
        self.qrLabel.hide()

        self.setLayout(grid)

        # self.setGeometry(300, 300, 350, 300)
        self.setWindowTitle('小东猪手')
        self.show()
        self.resize(650,250)

    # 开启下单任务
    def startTask(self):
        #通过URL解析出需要的参数
        if self.urlEdit.text():
            urlconfig=self.session.getItemDetailbyUrl(self.urlEdit.text())
            if urlconfig:
                self.skuEdit.setText(urlconfig['skuId'])
                self.venderEdit.setText(urlconfig['venderId'])
                self.catEdit.setText(urlconfig['cat'])
        if not self.session.isLogin:
            self.qrLogin()
            self.infoLabel.setText('请使用京东扫码登录')
            return
        self.config['buyTime'] = self.buyTimeEdit.text()
        self.config['skuId'] = self.skuEdit.text()
        self.config['areaId'] = self.areaEdit.text()
        self.config['venderId'] = self.venderEdit.text()
        self.config['cat'] = self.catEdit.text()
        self.saveData()
        self.buyerThread = BuyerThread(self.session, self.config)
        self.buyerThread.infoSignal.connect(self.infoSignal)
        self.buyerThread.start()
        #self.buyerThread.run()

    # 扫码登录
    def qrLogin(self):
        res = self.session.getQRcode()
        if res:
            img = QImage.fromData(res)
            self.qrLabel.setPixmap(QPixmap.fromImage(img))
            self.qrLabel.show()
            self.ticketThread.start()
            #self.ticketThread.run()
        else:
            self.infoLabel.setText("二维码获取失败")

    # 异步线程信号
    def ticketSignal(self, sec):
        self.qrLabel.hide()
        if sec == '成功':
            self.startTask()
        else:
            # 失败
            self.infoLabel.setText(sec)
            self.resumeSatrtBtn()

    def infoSignal(self, sec):
        self.qrLabel.hide()
        self.infoLabel.setText(sec)
        if sec == '登录失效':
            self.qrLogin()
            self.infoLabel.setText('请使用京东扫码登录')
        if sec == '异常终止':
            self.infoLabel.setText('异常终止,详见日志')
            self.resumeSatrtBtn()
        #self.infoLabel.setText('{0} 测试显示..'.format(time.strftime(DATA_FORMAT, time.localtime())))

    # 按钮监听
    def beginClick(self):
        self.disableStartBtn()
        self.startTask()

    def endClick(self):
        self.handleStopBrn()

    def handleStopBrn(self):
        if self.session.isLogin:
            self.buyerThread.pause()
        else:
            self.ticketThread.pause()
        self.resumeSatrtBtn()

    def disableStartBtn(self):
        self.endButton.setDisabled(False)
        self.startButton.setDisabled(True)

    def resumeSatrtBtn(self):
        self.endButton.setDisabled(True)
        self.startButton.setDisabled(False)

    # 输入框监听
    def textChanged(self, text):
        password = self.passwordEdit.text()
        self.config['password'] = password
        self.session.paypassword = password

    # 滑块监控
    def valuechange(self):
        num = self.numSlider.value()
        self.config['count'] = num
        self.numLabel.setText(NUM_LABEL_FORMAT.format(num))

    def stockValuechange(self):
        stock = self.stockSlider.value()
        self.config['stockInterval'] = stock
        self.stockLabel.setText(STOCK_LABEL_FORMAT.format(stock))

# 登录监控线程


class TicketThread(QThread):
    """ check ticket
    """
    ticketSignal = Signal(str)

    def __init__(self, session):
        super().__init__()
        self.session = session
        self._isPause = False

    def pause(self):
        self._isPause = True

    def run(self):
        self._isPause = False
        ticket = None
        retry_times = 85
        for i in range(retry_times):
            if self._isPause:
                self.ticketSignal.emit('已取消登录')
                return
            ticket = self.session.getQRcodeTicket()
            if ticket:
                break
            time.sleep(2)
        else:
            self.ticketSignal.emit('二维码过期，请重新获取扫描')
            return

        # validate QR code ticket
        if not self.session.validateQRcodeTicket(ticket):
            self.ticketSignal.emit('二维码信息校验失败')
            return

        self.ticketSignal.emit('成功')
        self.session.isLogin = True
        self.session.saveCookies()
        #登陆状态保活,每5分钟重新加载Cookie访问订单页
        while True:
            time.sleep(300)
            try:
                self.session.loadCookies()
            except Exception:
                self.ticketSignal.emit('二维码过期，请重新获取扫描')
                return

# 商品监控线程


class BuyerThread(QThread):

    infoSignal = Signal(str)

    def __init__(self, session, taskParam):
        super().__init__()
        self.session = session
        self.taskParam = taskParam
        self._isPause = False
        self.random_useragent = global_config.getboolean('config', 'random_useragent')
        # 微信推送
        self.enableWx = global_config.getboolean('messenger', 'enable')
        self.scKey = global_config.get('messenger', 'sckey')

    def pause(self):
        self._isPause = True

    def run(self):
        sku_id = self.taskParam.get('skuId')
        area_id = self.taskParam.get('areaId')
        count = self.taskParam.get('count')
        stock_interval = self.taskParam.get('stockInterval')/1000
        buyTime = self.taskParam.get('buyTime')
        venderId = self.taskParam.get('venderId')
        cat = self.taskParam.get('cat')
        checkinterval = 0
        #self.session.fetchItemDetail(sku_id)
        submitRetry = 3
        submitInterval = 5

        timer = Timer(buyTime)
        self.infoSignal.emit('定时中，将于 {0} 开始执行'.format(buyTime))
        timer.start()

        while True:
            print('{0} 商品监控线程正在执行..'.format(time.strftime(DATA_FORMAT, time.localtime())))
            if not self.session.isLogin:
                print('{0} 已取消下单..'.format(time.strftime(DATA_FORMAT, time.localtime())))
                self.infoSignal.emit('登录失效')
                return
            if self._isPause:
                print('{0} 已取消下单..'.format(time.strftime(DATA_FORMAT, time.localtime())))
                self.infoSignal.emit('{0} 已取消下单'.format(
                    time.strftime(DATA_FORMAT, time.localtime())))
                return
            try:
                if self.random_useragent:
                    self.session.userAgent = get_random_useragent()
                    self.session.headers = {'User-Agent': self.session.userAgent}
                if not self.session.getItemStock(sku_id, count, area_id, venderId, cat):
                    #print('{0} 不满足下单条件..'.format(time.strftime(DATA_FORMAT, time.localtime())))
                    self.infoSignal.emit('{0} 不满足下单条件，{1}s后进行下一次查询'.format(
                        time.strftime(DATA_FORMAT, time.localtime()), stock_interval))
                else:
                    #print('{0} 满足下单条件..'.format(time.strftime(DATA_FORMAT, time.localtime())))
                    self.infoSignal.emit('{0} 满足下单条件，开始执行'.format(sku_id))
                    if not self.session.prepareCart(sku_id, count, area_id):
                        self.infoSignal.emit('{0} 加入购物车失败，{1}s后进行下一次查询'.format(
                            time.strftime(DATA_FORMAT, time.localtime()), stock_interval))
                    else:
                        if self.session.submitOrderWitchTry(submitRetry, submitInterval):
                            self.infoSignal.emit('下单成功')
                            if self.enableWx:
                                send_wechat(message='JdBuyerApp:您的商品已下单成功，请及时支付订单', desp='您的商品已下单成功，请及时支付订单', sckey=self.scKey)
                            return
            except Exception as e:
                logger.error(e)
                self.infoSignal.emit('异常终止')
                return

            time.sleep(stock_interval)


def main():

    app = QApplication(sys.argv)
    ui = JdBuyerUI()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

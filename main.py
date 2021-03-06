import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtCore import * 
import pyupbit 
import time
import datetime

VERSION = 0.2
COIN = "BTC"
FIAT = "KRW"
TICKER = f"{FIAT}-{COIN}"

f = open("./upbit.key")
lines = f.readlines()
f.close()

access = lines[0].strip()
secret = lines[1].strip()
upbit = pyupbit.Upbit(access, secret)


class Worker(QThread):
    timeout = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()

    def run(self):
        while True:
            balances = upbit.get_balances()

            krw_balance = None 
            btc_balance = None 
            for balance in balances:
                if balance['currency'] == "KRW" and balance['unit_currency'] == FIAT:
                    krw_balance= balance
                if balance['currency'] == COIN and balance['unit_currency'] == FIAT:
                    btc_balance= balance

            btc_price = pyupbit.get_current_price(TICKER)        
            self.timeout.emit((btc_price, krw_balance, btc_balance))
            self.sleep(1)


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # variables
        self.btc_cur_price = 0 
        self.krw_balance_data = None
        self.btc_balance_data = None
        self.initialized = False

        self.unit_seed = 0
        self.unit_max = 200
        self.unit_num = 200
        self.profit_ratio = 10
        self.order_data = 0 
        self.btc_avg_buy_price = 0

        # thread 
        self.worker = Worker()
        self.worker.timeout.connect(self.update_data)
        self.worker.start()
       
        self.setGeometry(100, 100, 650, 400)
        self.setWindowTitle(f"업비트 물타기봇 v{VERSION}")
        self.create_table_widget()

        widget = QWidget()
        layout = QVBoxLayout(widget)

        # top 
        layout_grid = QGridLayout()
        self.label1 = QLabel("총 보유자산")
        self.label2 = QLabel("유닛개수")
        self.label3 = QLabel("잔여 유닛개수")
        self.label4 = QLabel("하루 매수액")
        self.label5 = QLabel("매수시간")
        self.label6 = QLabel("익절률")

        self.lineedit_balance = QLineEdit()
        #self.lineedit_balance.setEnabled(False)

        self.lineedit2 = QLineEdit()
        self.lineedit3 = QLineEdit()
        self.lineedit4 = QLineEdit()
        self.timeedit  = QTimeEdit()
        self.timeedit.setTime(QTime(9, 0, 0))
        self.timeedit.setDisplayFormat('hh:mm:ss')
        self.lineedit6 = QLineEdit()

        #self.btn_unit_max = QPushButton("변경")
        #self.btn_profit_ratio = QPushButton("변경")

        layout_grid.addWidget(self.label1, 0, 0)
        layout_grid.addWidget(self.label2, 1, 0)
        layout_grid.addWidget(self.label3, 2, 0)
        layout_grid.addWidget(self.label4, 3, 0)
        layout_grid.addWidget(self.label5, 4, 0)
        layout_grid.addWidget(self.label6, 5, 0)

        layout_grid.addWidget(self.lineedit_balance, 0, 1)
        layout_grid.addWidget(self.lineedit2, 1, 1)
        layout_grid.addWidget(self.lineedit3, 2, 1)
        layout_grid.addWidget(self.lineedit4, 3, 1)
        layout_grid.addWidget(self.timeedit , 4, 1)
        layout_grid.addWidget(self.lineedit6, 5, 1)

        #layout_grid.addWidget(self.btn_unit_max, 1, 2)
        #layout_grid.addWidget(self.btn_profit_ratio, 5, 2)

        layout_hbox = QHBoxLayout()
        self.btn_start = QPushButton("무한매수 시작")
        self.btn_start.clicked.connect(self.start)

        self.btn_reload = QPushButton("데이터 불러오기")
        self.btn_reload.clicked.connect(self.reload)

        layout_hbox.addWidget(self.btn_start)
        layout_hbox.addWidget(self.btn_reload)
        layout_hbox.addStretch(2)

        self.plain_text = QPlainTextEdit()

        layout.addLayout(layout_grid)
        layout.addWidget(self.table_widget)
        layout.addWidget(self.plain_text)
        layout.addLayout(layout_hbox)
        self.setCentralWidget(widget)

        # timer 
        self.timer = QTimer()
        self.timer.start(1000)
        self.timer.timeout.connect(self.update_price)

        self.timer_order = QTimer()
        self.timer_order.start(1000)
        self.timer_order.timeout.connect(self.trigger_order)

    @pyqtSlot(tuple)
    def update_data(self, data):
        self.btc_cur_price    = data[0]     
        self.krw_balance_data = data[1]     
        self.btc_balance_data = data[2]     

        # initialize the seed when program start
        if self.initialized is False:
            self.initialize_unit_seed()
            self.initialized = True 
 
    def reload(self):
        """database로부터 주요 파라미터를 로드하는 함수
        """
        with open("database.txt", "r") as f:
            lines = f.readlines()
            self.unit_num = int(lines[0].strip())
            self.unit_seed = float(lines[1].strip()) 
            self.plain_text.appendPlainText("database 로드 완료")

    def start(self):
        """무한매수 시작 버튼에 대한 slot
        """
        self.order()

    def trigger_order(self):
        """매 초마다 호출되면서 매수 시간이 되면 order 메소드 호출
        """
        now = datetime.datetime.now()
        self.statusBar().showMessage(str(now)[:19])

        order_time = self.timeedit.time() 
        current_time = QTime.currentTime()
        diff = current_time.secsTo(order_time)

        if 0 <= diff < 4:
            # 지정가 매도 주문 취소
            self.cancel_order()

            # 비트코인 잔고가 0이면 거래일 익절을 의미
            # 새로 파라미터 초기화 
            btc_balance = upbit.get_balance(TICKER)
            if btc_balance == 0:
                self.initialize_unit_seed()

            time.sleep(2)
            self.order()
            time.sleep(2)

    def order(self):
        # buy bitcoin when current price is less than average buy price 
        if self.btc_avg_buy_price == 0 or self.btc_cur_price < self.btc_avg_buy_price:
            upbit.buy_market_order(TICKER, self.unit_seed)
            self.unit_num -= 1

        # 매수 후 평단 재계산 
        # 지정가 매도 
        balance_dict = upbit.get_balance(TICKER, verbose=True)
        self.btc_avg_buy_price = float(balance_dict['avg_buy_price'])
        volume = balance_dict['balance']

        price = self.btc_avg_buy_price * (1 + self.profit_ratio * 0.01)
        # 호가 규칙 적용 
        price = pyupbit.get_tick_size(price)
        self.order_data = upbit.sell_limit_order(TICKER, price, volume)
        print(self.order_data)

        # backup 
        with open("database.txt", "w") as f:
            f.write(str(self.unit_num) + '\n')
            f.write(str(self.unit_seed) + '\n')
            self.plain_text.appendPlainText("database 쓰기 완료")

    def cancel_order(self):
        try:
            uuid = self.order_data['uuid']
            upbit.cancel_order(uuid)
        except:
            pass

    def initialize_unit_seed(self):
        krw = float(self.krw_balance_data['balance'])
        self.unit_seed = krw / self.unit_max
        self.unit_num = self.unit_max

    def update_price(self):
        # 비트코인 매수 평규가 
        try:
            self.btc_avg_buy_price = float(self.btc_balance_data['avg_buy_price'])
        except:
            self.btc_avg_buy_price = 0 

        # 현재가
        item = QTableWidgetItem(format(int(self.btc_cur_price), ","))
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 1, item) 

        # 매수평균가
        item = QTableWidgetItem(format(int(self.btc_avg_buy_price), ","))
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 2, item) 

        # 보유수량 
        try:
            amount = float(self.btc_balance_data['balance']) + float(self.btc_balance_data['locked'])
        except:
            amount = 0
        item = QTableWidgetItem(f"{amount:.8f}")
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 3, item) 

        # 평가금액 
        est_price = amount * self.btc_cur_price 
        item = QTableWidgetItem(format(int(est_price), ","))
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 4, item) 

        # 평가손익 
        if self.btc_avg_buy_price == 0:
            percent = 0
        else:
            percent = (self.btc_cur_price - self.btc_avg_buy_price) / self.btc_cur_price * 100
        item = QTableWidgetItem(f"{percent:.2f} %")
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 5, item) 

        # 총보유자산 
        # 원화 및 BTC만 고려함. 
        try:
            krw = float(self.krw_balance_data['balance']) + float(self.krw_balance_data['locked'])
        except:
            krw = 0

        try:
            btc = float(self.btc_balance_data['balance']) + float(self.btc_balance_data['locked'])
        except:
            btc = 0
        total = krw + self.btc_cur_price * btc 
        total = int(total)
        self.lineedit_balance.setText(format(total, ","))

        # 유닛개수
        self.lineedit2.setText(str(self.unit_max))
        # 잔여 유닛개수
        self.lineedit3.setText(str(self.unit_num))
        # 하루 매수액
        self.lineedit4.setText(f"{self.unit_seed:.1f}")
        # 익적률
        self.lineedit6.setText(str(self.profit_ratio))

    def create_table_widget(self):
        # table widget
        self.table_widget = QTableWidget()
        labels = ['보유코인', '현재가', '매수평균가', '보유수량', '평가금액', '평가손익']
        self.table_widget.setColumnCount(len(labels))
        self.table_widget.setRowCount(1)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setHorizontalHeaderLabels(labels)

        item = QTableWidgetItem("비트코인")
        item.setTextAlignment(int(Qt.AlignCenter|Qt.AlignVCenter))
        self.table_widget.setItem(0, 0, item) 


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    app.exec_()
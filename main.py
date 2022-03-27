from audioop import avg
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtCore import * 
import pyupbit 
import time

f = open("./upbit.key")
lines = f.readlines()
f.close()

access = lines[0].strip()
secret = lines[1].strip()
upbit = pyupbit.Upbit(access, secret)


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # variables
        self.unit_seed = 0
        self.unit_max = 200
        self.unit_num = 200
        self.profit_ratio = 10
        self.order_data = 0 
        self.btc_avg_buy_price = 0
        self.initialize_unit_seed()

        self.setGeometry(100, 100, 600, 300)
        self.setWindowTitle("Cost Averaging Upbit (Bitcoin) v1.0")
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
        layout_hbox.addWidget(self.btn_start)
        layout_hbox.addStretch(2)

        self.plain_text = QPlainTextEdit()

        layout.addLayout(layout_grid)
        layout.addWidget(self.table_widget)
        layout.addWidget(self.plain_text)
        layout.addLayout(layout_hbox)
        self.setCentralWidget(widget)

        # timer 
        self.timer = QTimer()
        self.timer.start(2000)
        self.timer.timeout.connect(self.update_price)

        self.timer_order = QTimer()
        self.timer_order.start(1000)
        self.timer_order.timeout.connect(self.trigger_order)

    def start(self):
        self.order()

    def trigger_order(self):
        """매 초마다 호출되면서 매수 시간이 되면 order 메소드 호출
        """
        order_time = self.timeedit.time() 
        current_time = QTime.currentTime()
        diff = current_time.secsTo(order_time)

        if 0 <= diff < 4:
            self.cancel_order()
            time.sleep(2)
            self.order()
            time.sleep(2)

    def order(self):
        btc_price = pyupbit.get_current_price("KRW-BTC")        

        # 평단가가 현재가보다 낮으면 매수
        if self.btc_avg_buy_price < btc_price:
            self.order_data = upbit.buy_market_order("KRW-BTC", self.unit_seed)
            self.unit_num -= 1

        # 매수 후 평단 재계산 
        # 지정가 매도 
        self.btc_avg_buy_price, volume = self.get_avg_buy_price("KRW-BTC") 
        price = self.btc_avg_buy_price * (1 + self.profit_ratio * 0.01)
        price = int(price)
        upbit.sell_limit_order("KRW-BTC", price, volume)

    def cancel_order(self):
        try:
            uuid = self.order_data['uuid']
            upbit.cancel_order(uuid)
        except:
            pass

    def initialize_unit_seed(self):
        krw = upbit.get_balance_t("KRW")
        self.unit_seed = krw / self.unit_max

    def get_avg_buy_price(self, ticker: str):
        """_summary_

        Args:
            ticker (str): "KRW-BTC" 
        """
        avg_buy_price = 0
        volume = 0
        fiat, coin = ticker.split("-")
        balances = upbit.get_balances()
        for balance in balances:
            if balance['currency'] == coin and balance['unit_currency'] == fiat:
                avg_buy_price = int(balance['avg_buy_price']) 
                volume = float(balance['balance'])
                break

        return avg_buy_price, volume

    def update_price(self):
        btc_price = pyupbit.get_current_price("KRW-BTC")        
        self.btc_avg_buy_price, volume = self.get_avg_buy_price("KRW-BTC") 

        item = QTableWidgetItem(format(btc_price, ","))
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 1, item) 

        item = QTableWidgetItem(format(self.btc_avg_buy_price, ","))
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 2, item) 

        # 평가손익 
        percent = (btc_price - self.btc_avg_buy_price) / btc_price * 100
        item = QTableWidgetItem(f"{percent:.2f} %")
        item.setTextAlignment(int(Qt.AlignRight|Qt.AlignVCenter))
        self.table_widget.setItem(0, 3, item) 

        # 총보유자산 
        # 원화 및 BTC만 고려함. 
        krw = upbit.get_balance_t("KRW")
        btc = upbit.get_balance_t("BTC") 
        total = krw + btc_price * btc 
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
        labels = ['보유코인', '현재가', '매수평균가', '평가손익']
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
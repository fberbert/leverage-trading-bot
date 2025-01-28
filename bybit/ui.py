# ui.py

import time
import json
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QCheckBox,
    QRadioButton, QButtonGroup
)
from PyQt5.QtGui import QFont, QColor, QBrush
from PyQt5.QtCore import Qt, QTimer

from sound import SoundPlayer
from websocket_client import PriceWebsocketClient
from api import (
    fetch_open_positions,
    fetch_high_low_prices,
    close_position_market,
    open_new_position_market,
    decide_trade_direction,
    get_account_overview
)
from utils import send_email_notification


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.selected_symbol = 'XBTUSDTM'
        self.binance_symbol = 'BTCUSDT'
        self.default_leverage = 20
        self.default_stop_loss = -3.5
        self.stop_loss_price = ''  # Novo campo Stop Loss Price
        self.auto_calc_trailing_stop = True
        self.trailing_stop_1_15 = 1.5
        self.trailing_stop_16_30 = 5
        self.trailing_stop_31_50 = 8
        self.trailing_stop_above_50 = 10
        self.alert_price_above = 0
        self.alert_price_below = 0
        self.default_contract_qty = 1
        self.rsi_period = 14
        self.use_sma = True
        self.use_rsi = True
        self.use_volume = False
        self.use_high_low = True
        self.auto_open_new_position = False
        self.auto_close_positions = True
        self.granularity = '5'
        self.margin_calls = 0
        self.fetch_open_positions_empty_count = 0

        # NOVO CAMPO: IGNORAR MOEDAS
        # Aqui vamos armazenar a string com as moedas a ignorar no formato "TRUMP,TESTE,ETC"
        self.ignore_coins_sl = ''  # Texto inicial
        self.ignore_coins_sl_list = []  # Lista (parsed) para fazer a checagem
        self.ignore_coins_tp = ''  # Texto inicial
        self.ignore_coins_tp_list = []  # Lista (parsed) para fazer a checagem

        self.position_trackers = {}
        self.load_position_trackers()

        self.monitoring_signal = False
        self.decision_value = 'wait'
        self.sma_value = ''
        self.rsi_value = ''
        self.volume_value = ''
        self.high_low_value = ''
        self.first_run = True

        self.price_alert_above = 0
        self.price_alert_below = 0
        self.last_price = 0
        self.alert_above_triggered = False
        self.alert_below_triggered = False
        self.last_updated_price_time = 0

        # Trade direction option ('both', 'buy', 'sell')
        self.trade_direction_option = 'both'

        # Carregar configs
        self.load_configurations()
        self.init_ui()

        # Ajusta radio buttons conforme config
        if self.trade_direction_option == 'both':
            self.trade_direction_both.setChecked(True)
        elif self.trade_direction_option == 'buy':
            self.trade_direction_buy.setChecked(True)
        elif self.trade_direction_option == 'sell':
            self.trade_direction_sell.setChecked(True)

        # Ajusta interface dos trailing stops
        self.toggle_input_opacity(self.auto_calc_trailing_stop)

        # Sons
        self.sound_player = SoundPlayer("correct-chime.mp3")
        self.sound_closed_position_win = SoundPlayer("closed-position-win.mp3")
        self.sound_closed_position_lose = SoundPlayer("closed-position-lose.mp3")
        self.sound_price_above = SoundPlayer("price-above.mp3")
        self.sound_price_below = SoundPlayer("price-below.mp3")
        self.sound_open_position = SoundPlayer("coin.mp3")

        # Websocket de preços
        self.price_ws_client = PriceWebsocketClient(self.selected_symbol)
        self.price_ws_client.price_updated.connect(self.update_price_label)
        self.price_ws_client.start()
        self.sound_player.play_sound()

    def init_ui(self):
        self.setWindowTitle("Leverage Trading Bot")
        self.setGeometry(0, 0, 1240, 800)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #ffffff;
            }
            QLineEdit, QComboBox, QPushButton, QTableWidget {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QCheckBox, QRadioButton {
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                border: 1px solid #5a5a5a;
                background: none;
            }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {
                background-color: #55ff55;
            }
        """)

        # High/Low Labels
        self.last_hour_label = QLabel("Última Hora: ")
        self.last_hour_label.setFont(QFont("Arial", 8))
        self.last_hour_label.setStyleSheet("color: #cccccc;")

        self.high_label = QLabel("High: N/A")
        self.high_label.setStyleSheet("color: #00ff00;")
        self.low_label = QLabel("Low: N/A")
        self.low_label.setStyleSheet("color: #ff3333;")
        high_low_layout = QHBoxLayout()
        high_low_layout.addWidget(self.last_hour_label)
        high_low_layout.addWidget(self.high_label)
        high_low_layout.addStretch()
        high_low_layout.addWidget(self.low_label)
        main_layout.addLayout(high_low_layout)

        # Price Label
        self.price_label = QLabel(f"{self.selected_symbol} $0.00")
        self.price_label.setFont(QFont("Arial", 24))
        self.price_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.price_label)

        # Configuration Layouts
        config_hbox = QHBoxLayout()
        config_left_layout = QFormLayout()
        config_right_layout = QFormLayout()

        # ------ LEFT CONFIGURATIONS ------
        leverage_label = QLabel("Leverage:")
        leverage_label.setFont(QFont("Arial", 12))
        self.leverage_input = QLineEdit(str(self.default_leverage))
        self.leverage_input.setFont(QFont("Arial", 12))
        self.leverage_input.setFixedWidth(100)
        self.leverage_input.textChanged.connect(self.check_parameters_changes)
        config_left_layout.addRow(leverage_label, self.leverage_input)

        default_stop_loss_label = QLabel("Stop Loss Padrão (%):")
        default_stop_loss_label.setFont(QFont("Arial", 12))
        self.default_stop_loss_input = QLineEdit(str(self.default_stop_loss))
        self.default_stop_loss_input.setFont(QFont("Arial", 12))
        self.default_stop_loss_input.setFixedWidth(100)
        config_left_layout.addRow(default_stop_loss_label, self.default_stop_loss_input)

        # Novo campo Stop Loss Price
        stop_loss_price_label = QLabel("Stop Loss Price:")
        stop_loss_price_label.setFont(QFont("Arial", 12))
        self.stop_loss_price_input = QLineEdit(str(self.stop_loss_price))
        self.stop_loss_price_input.setFont(QFont("Arial", 12))
        self.stop_loss_price_input.setFixedWidth(100)
        config_left_layout.addRow(stop_loss_price_label, self.stop_loss_price_input)

        auto_calc_trailing_stop_label = QLabel("Auto Calc Trailing Stop:")
        auto_calc_trailing_stop_label.setFont(QFont("Arial", 12))
        self.auto_calc_trailing_stop_checkbox = QCheckBox()
        self.auto_calc_trailing_stop_checkbox.setChecked(self.auto_calc_trailing_stop)
        self.auto_calc_trailing_stop_checkbox.stateChanged.connect(
            lambda state: self.toggle_auto_calc_trailing_stop(state, self.auto_calc_trailing_stop_checkbox)
        )
        config_left_layout.addRow(auto_calc_trailing_stop_label, self.auto_calc_trailing_stop_checkbox)

        trailing_stop_1_15_label = QLabel("Trailing Stop 5-15%:")
        trailing_stop_1_15_label.setFont(QFont("Arial", 12))
        self.trailing_stop_1_15_input = QLineEdit(str(self.trailing_stop_1_15))
        self.trailing_stop_1_15_input.setFont(QFont("Arial", 12))
        self.trailing_stop_1_15_input.setFixedWidth(100)
        config_left_layout.addRow(trailing_stop_1_15_label, self.trailing_stop_1_15_input)

        trailing_stop_16_30_label = QLabel("Trailing Stop 16-30%:")
        trailing_stop_16_30_label.setFont(QFont("Arial", 12))
        self.trailing_stop_16_30_input = QLineEdit(str(self.trailing_stop_16_30))
        self.trailing_stop_16_30_input.setFont(QFont("Arial", 12))
        self.trailing_stop_16_30_input.setFixedWidth(100)
        config_left_layout.addRow(trailing_stop_16_30_label, self.trailing_stop_16_30_input)

        trailing_stop_31_50_label = QLabel("Trailing Stop 31-50%:")
        trailing_stop_31_50_label.setFont(QFont("Arial", 12))
        self.trailing_stop_31_50_input = QLineEdit(str(self.trailing_stop_31_50))
        self.trailing_stop_31_50_input.setFont(QFont("Arial", 12))
        self.trailing_stop_31_50_input.setFixedWidth(100)
        config_left_layout.addRow(trailing_stop_31_50_label, self.trailing_stop_31_50_input)

        trailing_stop_above_50_label = QLabel("Trailing Stop Acima de 50%:")
        trailing_stop_above_50_label.setFont(QFont("Arial", 12))
        self.trailing_stop_above_50_input = QLineEdit(str(self.trailing_stop_above_50))
        self.trailing_stop_above_50_input.setFont(QFont("Arial", 12))
        self.trailing_stop_above_50_input.setFixedWidth(100)
        config_left_layout.addRow(trailing_stop_above_50_label, self.trailing_stop_above_50_input)

        # ------ RIGHT CONFIGURATIONS ------
        alert_price_above_label = QLabel("Preço de Alerta Acima:")
        alert_price_above_label.setFont(QFont("Arial", 12))
        self.alert_entry_above = QLineEdit(str(self.alert_price_above))
        self.alert_entry_above.setFont(QFont("Arial", 12))
        self.alert_entry_above.setFixedWidth(100)
        config_right_layout.addRow(alert_price_above_label, self.alert_entry_above)

        alert_price_below_label = QLabel("Preço de Alerta Abaixo:")
        alert_price_below_label.setFont(QFont("Arial", 12))
        self.alert_entry_below = QLineEdit(str(self.alert_price_below))
        self.alert_entry_below.setFont(QFont("Arial", 12))
        self.alert_entry_below.setFixedWidth(100)
        config_right_layout.addRow(alert_price_below_label, self.alert_entry_below)

        default_contract_qty_label = QLabel("Quantidade de Contratos:")
        default_contract_qty_label.setFont(QFont("Arial", 12))
        self.default_contract_qty_input = QLineEdit(str(self.default_contract_qty))
        self.default_contract_qty_input.setFont(QFont("Arial", 12))
        self.default_contract_qty_input.setFixedWidth(100)
        self.default_contract_qty_input.textChanged.connect(self.check_parameters_changes)
        config_right_layout.addRow(default_contract_qty_label, self.default_contract_qty_input)

        rsi_label = QLabel("Período RSI:")
        rsi_label.setFont(QFont("Arial", 12))
        self.rsi_period_input = QLineEdit(str(self.rsi_period))
        self.rsi_period_input.setFont(QFont("Arial", 12))
        self.rsi_period_input.setFixedWidth(100)
        self.rsi_period_input.textChanged.connect(self.check_parameters_changes)
        config_right_layout.addRow(rsi_label, self.rsi_period_input)

        granularity_layout = QHBoxLayout()
        granularity_layout.setContentsMargins(0, 0, 0, 0)
        granularity_layout.setSpacing(0)

        granularity_label = QLabel("Granularidade:")
        granularity_label.setFont(QFont("Arial", 12))
        granularity_layout.addWidget(granularity_label)
        granularity_layout.addSpacing(70)

        self.granularity_1m_checkbox = QCheckBox("1m")
        self.granularity_1m_checkbox.setFont(QFont("Arial", 12))
        self.granularity_1m_checkbox.setChecked(self.granularity == '1')
        self.granularity_1m_checkbox.setStyleSheet("QCheckBox { color: white; margin-right: 20px;}")
        self.granularity_1m_checkbox.stateChanged.connect(
            lambda state: self.select_granularity(state, self.granularity_1m_checkbox)
        )
        granularity_layout.addWidget(self.granularity_1m_checkbox)

        self.granularity_5m_checkbox = QCheckBox("5m")
        self.granularity_5m_checkbox.setFont(QFont("Arial", 12))
        self.granularity_5m_checkbox.setChecked(self.granularity == '5')
        self.granularity_5m_checkbox.setStyleSheet("QCheckBox { color: white; margin-right: 20px;}")
        self.granularity_5m_checkbox.stateChanged.connect(
            lambda state: self.select_granularity(state, self.granularity_5m_checkbox)
        )
        granularity_layout.addWidget(self.granularity_5m_checkbox)

        granularity_layout.addStretch()

        # Campo de Chamadas de Margem
        margin_calls_label = QLabel("Chamadas de Margem:")
        margin_calls_label.setFont(QFont("Arial", 12))
        self.margin_calls_input = QLineEdit(str(self.margin_calls))
        self.margin_calls_input.setFont(QFont("Arial", 12))
        self.margin_calls_input.setFixedWidth(100)
        self.margin_calls_input.textChanged.connect(self.check_parameters_changes)

        self.used_margin_calls_label = QLabel("(0)")
        self.used_margin_calls_label.setFont(QFont("Arial", 12))
        self.used_margin_calls_label.setStyleSheet("color: #ffffff;")

        margin_calls_layout = QHBoxLayout()
        margin_calls_layout.addWidget(self.margin_calls_input)
        margin_calls_layout.addWidget(self.used_margin_calls_label)

        config_right_layout.addRow(margin_calls_label, margin_calls_layout)
        config_right_layout.addRow(granularity_layout)

        # ---- NOVO CAMPO: IGNORAR MOEDAS ----
        # Será um QLineEdit para a string de moedas ignoradas
        ignore_coins_sl_label = QLabel("Ignorar Stop Loss:")
        ignore_coins_sl_label.setFont(QFont("Arial", 12))
        self.ignore_coins_sl_input = QLineEdit(str(self.ignore_coins_sl))
        self.ignore_coins_sl_input.setFont(QFont("Arial", 12))
        self.ignore_coins_sl_input.setFixedWidth(200)
        # Vamos conectar a mesma check_parameters_changes para salvar dinamicamente
        # self.ignore_coins_sl_input.textChanged.connect(self.check_parameters_changes)
        config_right_layout.addRow(ignore_coins_sl_label, self.ignore_coins_sl_input)

        ignore_coins_tp_label = QLabel("Ignorar Take Profit:")
        ignore_coins_tp_label.setFont(QFont("Arial", 12))
        self.ignore_coins_tp_input = QLineEdit(str(self.ignore_coins_tp))
        self.ignore_coins_tp_input.setFont(QFont("Arial", 12))
        self.ignore_coins_tp_input.setFixedWidth(200)
        # Vamos conectar a mesma check_parameters_changes para salvar dinamicamente
        # self.ignore_coins_tp_input.textChanged.connect(self.check_parameters_changes)
        config_right_layout.addRow(ignore_coins_tp_label, self.ignore_coins_tp_input)
        # ---- FIM NOVO CAMPO ----

        config_hbox.addLayout(config_left_layout)
        config_hbox.addLayout(config_right_layout)

        main_layout.addLayout(config_hbox)

        # Buttons
        self.save_config_button = QPushButton("Salvar configurações")
        self.save_config_button.setStyleSheet("min-height: 30px;")
        self.save_config_button.clicked.connect(self.check_parameters_changes)
        self.buy_market_button = QPushButton("Buy Market")
        self.buy_market_button.setStyleSheet("min-height: 30px;")
        self.buy_market_button.clicked.connect(self.buy_market)
        self.sell_market_button = QPushButton("Sell Market")
        self.sell_market_button.setStyleSheet("min-height: 30px;")
        self.sell_market_button.clicked.connect(self.sell_market)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_config_button)
        button_layout.addWidget(self.buy_market_button)
        button_layout.addWidget(self.sell_market_button)
        main_layout.addLayout(button_layout)

        # Auto Open Checkbox and Balance Label
        self.auto_open_checkbox = QCheckBox("Abrir nova posição automaticamente")
        self.auto_open_checkbox.setFont(QFont("Arial", 12))
        self.auto_open_checkbox.setChecked(self.auto_open_new_position)
        self.auto_open_checkbox.stateChanged.connect(lambda state: self.toggle_auto_open(state, self.auto_open_checkbox))
        self.auto_open_checkbox.setStyleSheet("QCheckBox { color: white; margin-left: 20px;}")

        # Auto close positions checkbox
        self.auto_close_checkbox = QCheckBox("Fechar posições automaticamente")
        self.auto_close_checkbox.setFont(QFont("Arial", 12))
        self.auto_close_checkbox.setChecked(self.auto_close_positions)
        self.auto_close_checkbox.stateChanged.connect(lambda state: self.toggle_auto_close(state, self.auto_close_checkbox))

        self.balance_prelabel = QLabel("Saldo: ")
        self.balance_prelabel.setFont(QFont("Arial", 12))
        self.balance_prelabel.setStyleSheet("color: #ffffff;")
        self.balance_label = QLabel("N/A")
        self.balance_label.setFont(QFont("Arial", 12))
        self.balance_label.setStyleSheet("color: #ffffff;")

        balance_layout = QHBoxLayout()
        balance_layout.addWidget(self.auto_open_checkbox)
        balance_layout.addWidget(self.auto_close_checkbox)
        balance_layout.addStretch()
        balance_layout.addWidget(self.balance_prelabel)
        balance_layout.addWidget(self.balance_label)

        main_layout.addLayout(balance_layout)

        # Indicator Layouts
        indicator_layout = QVBoxLayout()
        indicator_layout.setContentsMargins(150, 20, 150, 0)

        indicator_layout_line1 = QHBoxLayout()
        indicator_layout_line1.addStretch()

        self.use_sma_checkbox = QCheckBox()
        self.use_sma_checkbox.setChecked(self.use_sma)
        self.use_sma_checkbox.setText(self.sma_value)
        self.use_sma_checkbox.setFont(QFont("Arial", 12))
        self.use_sma_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'sma'))
        self.use_sma_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")
        indicator_layout_line1.addWidget(self.use_sma_checkbox)

        self.use_rsi_checkbox = QCheckBox()
        self.use_rsi_checkbox.setChecked(self.use_rsi)
        self.use_rsi_checkbox.setText(self.rsi_value)
        self.use_rsi_checkbox.setFont(QFont("Arial", 12))
        self.use_rsi_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'rsi'))
        self.use_rsi_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")
        indicator_layout_line1.addWidget(self.use_rsi_checkbox)
        indicator_layout_line1.addStretch()
        indicator_layout.addLayout(indicator_layout_line1)

        indicator_layout_line2 = QHBoxLayout()
        indicator_layout_line2.addStretch()

        self.use_volume_checkbox = QCheckBox()
        self.use_volume_checkbox.setChecked(self.use_volume)
        self.use_volume_checkbox.setText(self.volume_value)
        self.use_volume_checkbox.setFont(QFont("Arial", 12))
        self.use_volume_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'volume'))
        self.use_volume_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")
        indicator_layout_line2.addWidget(self.use_volume_checkbox)

        self.use_high_low_checkbox = QCheckBox()
        self.use_high_low_checkbox.setChecked(self.use_high_low)
        self.use_high_low_checkbox.setText(self.high_low_value)
        self.use_high_low_checkbox.setFont(QFont("Arial", 12))
        self.use_high_low_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'high_low'))
        self.use_high_low_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")
        indicator_layout_line2.addWidget(self.use_high_low_checkbox)
        indicator_layout_line2.addStretch()
        indicator_layout.addLayout(indicator_layout_line2)

        main_layout.addLayout(indicator_layout)

        # Trade Direction Radio Buttons
        trade_direction_layout = QHBoxLayout()
        trade_direction_layout.setContentsMargins(150, 20, 150, 0)
        trade_direction_layout.addStretch()

        trade_direction_label = QLabel("Direção de Trade:")
        trade_direction_label.setFont(QFont("Arial", 12))
        trade_direction_label.setStyleSheet("color: #ffffff;")
        trade_direction_layout.addWidget(trade_direction_label)

        self.trade_direction_group = QButtonGroup(self)
        self.trade_direction_both = QRadioButton("Both")
        self.trade_direction_both.setFont(QFont("Arial", 12))
        self.trade_direction_both.setChecked(True)
        self.trade_direction_both.toggled.connect(self.update_trade_direction_option)
        trade_direction_layout.addWidget(self.trade_direction_both)
        self.trade_direction_group.addButton(self.trade_direction_both)

        self.trade_direction_buy = QRadioButton("Buy")
        self.trade_direction_buy.setFont(QFont("Arial", 12))
        self.trade_direction_buy.toggled.connect(self.update_trade_direction_option)
        trade_direction_layout.addWidget(self.trade_direction_buy)
        self.trade_direction_group.addButton(self.trade_direction_buy)

        self.trade_direction_sell = QRadioButton("Sell")
        self.trade_direction_sell.setFont(QFont("Arial", 12))
        self.trade_direction_sell.toggled.connect(self.update_trade_direction_option)
        trade_direction_layout.addWidget(self.trade_direction_sell)
        self.trade_direction_group.addButton(self.trade_direction_sell)

        trade_direction_layout.addStretch()
        main_layout.addLayout(trade_direction_layout)

        # Positions Table
        self.positions_table = QTableWidget()
        self.positions_table.setRowCount(0)
        columns = [
            "Contrato", "Qtd", "Entry / Market", "Preço de Liq.",
            "Margem", "PNL Não Realizado", "Taxas", "Trigger", "Ações"
        ]
        self.positions_table.setColumnCount(len(columns))
        self.positions_table.setHorizontalHeaderLabels(columns)
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.positions_table.setColumnWidth(0, 230)
        self.positions_table.setColumnWidth(1, 100)
        self.positions_table.setColumnWidth(2, 200)
        self.positions_table.setColumnWidth(3, 80)
        self.positions_table.setColumnWidth(4, 100)
        self.positions_table.setColumnWidth(5, 170)
        self.positions_table.setColumnWidth(6, 130)
        self.positions_table.setColumnWidth(7, 80)
        self.positions_table.setColumnWidth(8, 120)

        main_layout.addWidget(self.positions_table)
        self.setLayout(main_layout)

        # Timers
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetch_open_positions)
        self.timer.start(1000)

        self.auto_close_timer = QTimer()
        self.auto_close_timer.timeout.connect(self.check_auto_close_positions)
        self.auto_close_timer.start(1000)

        self.high_low_timer = QTimer()
        self.high_low_timer.timeout.connect(self.fetch_high_low_prices)
        self.high_low_timer.start(60000)
        self.fetch_high_low_prices()

        self.get_indicators_timer = QTimer()
        self.get_indicators_timer.timeout.connect(self.check_decision_indicators)
        self.get_indicators_timer.start(5000)

        self.balance_timer = QTimer()
        self.balance_timer.timeout.connect(self.update_balance_label)
        self.balance_timer.start(60000)
        self.update_balance_label()

    def update_trade_direction_option(self):
        if self.trade_direction_both.isChecked():
            self.trade_direction_option = 'both'
        elif self.trade_direction_buy.isChecked():
            self.trade_direction_option = 'buy'
        elif self.trade_direction_sell.isChecked():
            self.trade_direction_option = 'sell'
        self.check_parameters_changes()

    def toggle_auto_open(self, state, checkbox=None):
        if checkbox == self.auto_open_checkbox:
            self.auto_open_new_position = state == Qt.Checked
        self.check_parameters_changes()

    def toggle_auto_close(self, state, checkbox=None):
        if checkbox == self.auto_close_checkbox:
            self.auto_close_positions = state == Qt.Checked
        self.check_parameters_changes()

    def toggle_input_opacity(self, isChecked):
        # trailing input opacity
        if isChecked:
            self.trailing_stop_1_15_input.setStyleSheet("background-color: #333333; color: #666666;")
            self.trailing_stop_16_30_input.setStyleSheet("background-color: #333333; color: #666666;")
            self.trailing_stop_31_50_input.setStyleSheet("background-color: #333333; color: #666666;")
            self.trailing_stop_above_50_input.setStyleSheet("background-color: #333333; color: #666666;")
        else:
            self.trailing_stop_1_15_input.setStyleSheet("background-color: #1e1e1e; color: white;")
            self.trailing_stop_16_30_input.setStyleSheet("background-color: #1e1e1e; color: white;")
            self.trailing_stop_31_50_input.setStyleSheet("background-color: #1e1e1e; color: white;")
            self.trailing_stop_above_50_input.setStyleSheet("background-color: #1e1e1e; color: white;")

    def toggle_auto_calc_trailing_stop(self, state, checkbox):
        print(f"Auto Calc Trailing Stop: {state}")
        self.auto_calc_trailing_stop = state == Qt.Checked
        self.check_parameters_changes()

        # disable trailing stop inputs if auto calc is enabled
        self.trailing_stop_1_15_input.setEnabled(not self.auto_calc_trailing_stop)
        self.trailing_stop_16_30_input.setEnabled(not self.auto_calc_trailing_stop)
        self.trailing_stop_31_50_input.setEnabled(not self.auto_calc_trailing_stop)
        self.trailing_stop_above_50_input.setEnabled(not self.auto_calc_trailing_stop)
        self.toggle_input_opacity(self.auto_calc_trailing_stop)

    def toggle_indicator(self, state, indicator):
        if indicator == 'sma':
            self.use_sma = state == Qt.Checked
        elif indicator == 'rsi':
            self.use_rsi = state == Qt.Checked
        elif indicator == 'volume':
            self.use_volume = state == Qt.Checked
        elif indicator == 'high_low':
            self.use_high_low = state == Qt.Checked
        self.check_parameters_changes()

    def select_granularity(self, state, checkbox):
        if checkbox == self.granularity_1m_checkbox:
            self.granularity_5m_checkbox.setChecked(False)
            if state != Qt.Checked:
                self.granularity_1m_checkbox.setChecked(True)
            self.granularity = '1'
        elif checkbox == self.granularity_5m_checkbox:
            self.granularity_1m_checkbox.setChecked(False)
            if state != Qt.Checked:
                self.granularity_5m_checkbox.setChecked(True)
            self.granularity = '5'
        self.check_parameters_changes()

    def reset_alerts(self):
        self.alert_above_triggered = False
        self.alert_below_triggered = False

    def check_parameters_changes(self):
        """
        Valida e salva as configurações sempre que algum QLineEdit/QCheckBox muda.
        """
        try:
            new_leverage = int(self.leverage_input.text())
            new_default_stop_loss = float(self.default_stop_loss_input.text())
            new_stop_loss_price = self.stop_loss_price_input.text()
            new_auto_calc_trailing_stop = self.auto_calc_trailing_stop_checkbox.isChecked()
            new_trailing_stop_1_15 = float(self.trailing_stop_1_15_input.text())
            new_trailing_stop_16_30 = float(self.trailing_stop_16_30_input.text())
            new_trailing_stop_31_50 = float(self.trailing_stop_31_50_input.text())
            new_trailing_stop_above_50 = float(self.trailing_stop_above_50_input.text())
            new_alert_price_above = float(self.alert_entry_above.text())
            new_alert_price_below = float(self.alert_entry_below.text())
            new_default_contract_qty = int(self.default_contract_qty_input.text())
            new_rsi_period = int(self.rsi_period_input.text())
            new_margin_calls = int(self.margin_calls_input.text())

            # Novo: ignorar moedas
            new_ignore_coins_sl = self.ignore_coins_sl_input.text().strip()
            # parse e salva em self.ignore_coins_list
            ignore_list_sl = [c.strip() for c in new_ignore_coins_sl.split(',') if c.strip()]

            new_ignore_coins_tp = self.ignore_coins_tp_input.text().strip()
            ignore_list_tp = [c.strip() for c in new_ignore_coins_tp.split(',') if c.strip()]

            self.default_leverage = new_leverage
            self.default_stop_loss = new_default_stop_loss
            self.stop_loss_price = new_stop_loss_price
            self.auto_calc_trailing_stop = new_auto_calc_trailing_stop
            self.trailing_stop_1_15 = new_trailing_stop_1_15
            self.trailing_stop_16_30 = new_trailing_stop_16_30
            self.trailing_stop_31_50 = new_trailing_stop_31_50
            self.trailing_stop_above_50 = new_trailing_stop_above_50
            self.alert_price_above = new_alert_price_above
            self.alert_price_below = new_alert_price_below
            self.default_contract_qty = new_default_contract_qty
            self.rsi_period = new_rsi_period
            self.margin_calls = new_margin_calls

            # Guarda e parseia ignore_coins
            self.ignore_coins_sl = new_ignore_coins_sl
            self.ignore_coins_sl_list = ignore_list_sl

            self.ignore_coins_tp = new_ignore_coins_tp
            self.ignore_coins_tp_list = ignore_list_tp

            self.reset_alerts()

            # Feedback de sucesso no botão
            self.save_config_button.setStyleSheet("background-color: #00ff00; color: black; min-height: 30px;")
            self.save_config_button.setText("Salvo com sucesso!")
            QTimer.singleShot(500, lambda: self.save_config_button.setStyleSheet("min-height: 30px;"))
            QTimer.singleShot(500, lambda: self.save_config_button.setText("Salvar configurações"))

            self.save_configurations()

        except ValueError as e:
            print(f"Erro ao salvar configurações. Verifique os valores inseridos: {e}")
            self.save_config_button.setStyleSheet("background-color: #ff0000; color: black; min-height: 30px;")
            self.save_config_button.setText("Ocorreu um erro!")
            QTimer.singleShot(500, lambda: self.save_config_button.setStyleSheet("min-height: 30px;"))
            QTimer.singleShot(500, lambda: self.save_config_button.setText("Salvar configurações"))

    def fetch_open_positions(self):
        try:
            data = fetch_open_positions()
            if data is not None:
                self.update_positions_display(data)

                if data:
                    self.monitoring_signal = False
                    self.fetch_open_positions_empty_count = 0
                else:
                    self.fetch_open_positions_empty_count += 1

                # Se não há posições, e auto_open_new_position estiver ativo, tentamos abrir
                if not data and self.auto_open_new_position and not self.monitoring_signal and self.fetch_open_positions_empty_count > 3:
                    print(f"Empty count: {self.fetch_open_positions_empty_count}, abrindo nova posição...")
                    self.open_new_position_after_close(None)
            else:
                print("Erro ao obter posições: dados da API são None.")
        except Exception as e:
            print(f"Erro ao obter posições: {e}")
            self.monitoring_signal = False

    def fetch_high_low_prices(self):
        high_price, low_price = fetch_high_low_prices(self.selected_symbol)
        if high_price is not None and low_price is not None:
            self.high_label.setText(f"High: ${high_price:,.2f}")
            self.low_label.setText(f"Low: ${low_price:,.2f}")
        else:
            self.high_label.setText("High: N/A")
            self.low_label.setText("Low: N/A")

    def update_positions_display(self, positions):
        self.positions_table.setRowCount(0)
        current_positions_ids = set()

        for position in positions:
            row_position = self.positions_table.rowCount()
            self.positions_table.insertRow(row_position)

            avg_entry_price = position.get('avgEntryPrice', 0)
            real_leverage = position.get('realLeverage', 0)
            maint_margin = position.get('maintMargin', 0)
            realised_pnl_value = position.get('realisedPnl', 0)

            if avg_entry_price != 0:
                qtd = (real_leverage * maint_margin) / avg_entry_price
            else:
                qtd = 0

            entry_mark_price = f"{avg_entry_price} / {position.get('markPrice', 0)}"

            pos_margin = position.get('posMargin', 0)
            unrealised_pnl_value = position.get('unrealisedPnl', 0)

            fee_percent = 0.06 * 2 * real_leverage
            total_fees_percent = fee_percent

            if pos_margin != 0:
                pnl_percent = (unrealised_pnl_value / pos_margin) * 100
                pnl_percent -= total_fees_percent
            else:
                pnl_percent = 0.0

            fee_rate = 0.0006 * 2
            total_fees_paid = fee_rate * real_leverage * maint_margin
            adjusted_unrealised_pnl_value = unrealised_pnl_value - total_fees_paid

            unrealised_pnl = f"{adjusted_unrealised_pnl_value:.2f} ({pnl_percent:.2f}%)"

            contract_type = position.get('symbol', '')
            current_qty = position.get('currentQty', 0)
            if current_qty < 0:
                position_direction = "SHORT"
                direction_color = 'red'
                qtd = -qtd
            else:
                position_direction = "LONG"
                direction_color = 'green'

            leverage_text = f"- {int(real_leverage)}x"

            contract_widget = QWidget()
            contract_layout = QHBoxLayout()
            contract_layout.setContentsMargins(0, 0, 0, 0)
            contract_layout.setSpacing(5)

            contract_label = QLabel(contract_type)
            contract_label.setStyleSheet("color: white;")

            direction_label = QLabel(position_direction)
            direction_label.setStyleSheet(f"color: {direction_color};")

            leverage_label = QLabel(leverage_text)
            leverage_label.setStyleSheet("color: white;")

            contract_layout.addWidget(contract_label)
            contract_layout.addWidget(direction_label)
            contract_layout.addWidget(leverage_label)

            contract_widget.setLayout(contract_layout)
            contract_widget.setStyleSheet("background-color: transparent;")

            liquidation_price = position.get('liquidationPrice', 'N/A')

            qtd_usdt = abs(qtd * avg_entry_price)
            amount_item = QTableWidgetItem(f"{qtd_usdt:.2f}")
            amount_item.setTextAlignment(Qt.AlignCenter)
            amount_item.setForeground(QBrush(QColor('white')))

            entry_mark_item = QTableWidgetItem(entry_mark_price)
            entry_mark_item.setTextAlignment(Qt.AlignCenter)
            entry_mark_item.setForeground(QBrush(QColor('white')))

            if isinstance(liquidation_price, (int, float)):
                liq_price_str = f"{liquidation_price:.2f}"
            else:
                liq_price_str = str(liquidation_price)
            liq_price_item = QTableWidgetItem(liq_price_str)
            liq_price_item.setTextAlignment(Qt.AlignCenter)
            liq_price_item.setForeground(QBrush(QColor('gold')))

            margin_item = QTableWidgetItem(f"{pos_margin:.2f} USDT")
            margin_item.setTextAlignment(Qt.AlignCenter)
            margin_item.setForeground(QBrush(QColor('white')))

            unrealised_pnl_item = QTableWidgetItem(unrealised_pnl)
            unrealised_pnl_item.setTextAlignment(Qt.AlignCenter)
            if adjusted_unrealised_pnl_value > 0:
                unrealised_pnl_item.setForeground(QBrush(QColor('green')))
            else:
                unrealised_pnl_item.setForeground(QBrush(QColor('red')))

            fees_item = QTableWidgetItem(f"{total_fees_paid:.2f} USDT")
            fees_item.setTextAlignment(Qt.AlignCenter)
            fees_item.setForeground(QBrush(QColor('yellow')))

            position_id = position.get('symbol')
            stop_loss_percent = self.position_trackers.get(position_id, {}).get('trigger_stop_loss_percent', self.default_stop_loss)
            stop_loss_item = QTableWidgetItem(f"{stop_loss_percent:.2f}%")
            stop_loss_item.setTextAlignment(Qt.AlignCenter)
            if stop_loss_percent < 0:
                stop_loss_item.setForeground(QBrush(QColor('red')))
            else:
                stop_loss_item.setForeground(QBrush(QColor('green')))

            self.positions_table.setCellWidget(row_position, 0, contract_widget)
            self.positions_table.setItem(row_position, 1, amount_item)
            self.positions_table.setItem(row_position, 2, entry_mark_item)
            self.positions_table.setItem(row_position, 3, liq_price_item)
            self.positions_table.setItem(row_position, 4, margin_item)
            self.positions_table.setItem(row_position, 5, unrealised_pnl_item)
            self.positions_table.setItem(row_position, 6, fees_item)
            self.positions_table.setItem(row_position, 7, stop_loss_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(0)
            market_button = QPushButton("Fechar Posição")
            market_button.setStyleSheet("height: 100%;")
            market_button.clicked.connect(lambda _, pos=position: self.close_position_market(pos))
            actions_layout.addWidget(market_button)
            actions_widget.setLayout(actions_layout)
            self.positions_table.setCellWidget(row_position, 8, actions_widget)

            current_positions_ids.add(position_id)
            if position_id not in self.position_trackers:
                self.position_trackers[position_id] = {
                    'position': position,
                    'max_pnl_percent': pnl_percent if pnl_percent >= 10 else 0,
                    'trigger_stop_loss_percent': self.default_stop_loss,
                    'used_margin_calls': 0
                }
                self.save_position_trackers()
                self.update_used_margin_calls_label(0)
            else:
                tracker = self.position_trackers[position_id]
                tracker['position'] = position
                used_calls = tracker.get('used_margin_calls', 0)
                self.update_used_margin_calls_label(used_calls)

        # Remove trackers que não estão mais em posições abertas
        for pid in list(self.position_trackers.keys()):
            if pid not in current_positions_ids:
                del self.position_trackers[pid]
                self.save_position_trackers()

    def check_auto_close_positions(self):
        positions_to_delete = []

        position_trackers_copy = list(self.position_trackers.items())
        for symbol, tracker in position_trackers_copy:
            position = tracker['position']
            position_id = position['symbol']
            pos_margin = position.get('posMargin', 1)
            unrealised_pnl = position.get('unrealisedPnl', 0)
            real_leverage = position.get('realLeverage', 0)
            avg_entry_price = position.get('avgEntryPrice', 0)
            current_qty = position.get('currentQty', 0)

            if pos_margin == 0:
                continue

            pnl_percent = (unrealised_pnl / pos_margin) * 100
            fee_percent = 0.06 * 2 * real_leverage
            pnl_percent -= fee_percent

            current_trigger = tracker.get('trigger_stop_loss_percent', self.default_stop_loss)
            calculated_stop_loss = self.default_stop_loss

            # Lógica do trailing stop
            # converter pnl_percent para float
            pnl_percent = float(pnl_percent)

            # print(f"pnl_percent: {pnl_percent:.2f} | auto_calc_trailing_stop: {self.auto_calc_trailing_stop} | {self.trailing_stop_1_15}")
            if not self.auto_calc_trailing_stop:
                # print("Calculando stop loss manualmente...")
                if 0.5 <= pnl_percent <= 3 and real_leverage >= 20:
                    calculated_stop_loss = calculated_stop_loss
                elif 4 <= pnl_percent < 5:
                    # calculated_stop_loss = pnl_percent * 0.5
                    # calculated_stop_loss = calculated_stop_loss
                    calculated_stop_loss = 2
                elif 5 <= pnl_percent <= 15.9:
                    if (pnl_percent - self.trailing_stop_1_15) > 2 and pnl_percent > 0:
                        tmp_calculated_stop_loss = pnl_percent - self.trailing_stop_1_15
                        if tmp_calculated_stop_loss > calculated_stop_loss:
                            calculated_stop_loss = tmp_calculated_stop_loss
                elif 16 <= pnl_percent <= 30:
                    calculated_stop_loss = pnl_percent - self.trailing_stop_16_30
                elif 31 <= pnl_percent <= 50:
                    calculated_stop_loss = pnl_percent - self.trailing_stop_31_50
                elif pnl_percent > 50:
                    calculated_stop_loss = pnl_percent - self.trailing_stop_above_50
            else:
                if pnl_percent >= 1:
                    calculated_stop_loss = pnl_percent * 0.5

            if calculated_stop_loss > current_trigger or (pnl_percent < 0 and calculated_stop_loss < current_trigger):
                tracker['trigger_stop_loss_percent'] = calculated_stop_loss
                print(f"Trigger atualizado para {calculated_stop_loss:.2f}% | PNL Atual: {pnl_percent:.2f}%")

            if pnl_percent > tracker.get('max_pnl_percent', 0):
                tracker['max_pnl_percent'] = pnl_percent
            elif pnl_percent < 0 and pnl_percent < tracker.get('max_pnl_percent', 0):
                tracker['max_pnl_percent'] = pnl_percent

            # Verificar Stop Loss Price
            if self.stop_loss_price != '':
                try:
                    stop_loss_price = float(self.stop_loss_price)
                    current_price = self.last_price

                    if current_qty > 0:  # Long
                        if stop_loss_price >= avg_entry_price:
                            # Take Profit
                            if current_price >= stop_loss_price:
                                print(f"Stop Loss Price atingido (Take Profit) para posição LONG em {stop_loss_price}")
                                if self.auto_close_positions:
                                    self.close_position_market(position)
                                    positions_to_delete.append(symbol)
                                continue
                        else:
                            # Stop Loss
                            if current_price <= stop_loss_price:
                                print(f"Stop Loss Price atingido (Stop Loss) para posição LONG em {stop_loss_price}")
                                if self.auto_close_positions:
                                    self.close_position_market(position)
                                    positions_to_delete.append(symbol)
                                continue
                    else:  # Short
                        if stop_loss_price <= avg_entry_price:
                            # Take Profit
                            if current_price <= stop_loss_price:
                                print(f"Stop Loss Price atingido (Take Profit) para posição SHORT em {stop_loss_price}")
                                if self.auto_close_positions:
                                    self.close_position_market(position)
                                    positions_to_delete.append(symbol)
                                continue
                        else:
                            # Stop Loss
                            if current_price >= stop_loss_price:
                                print(f"Stop Loss Price atingido (Stop Loss) para posição SHORT em {stop_loss_price}")
                                if self.auto_close_positions:
                                    self.close_position_market(position)
                                    positions_to_delete.append(symbol)
                                continue
                except ValueError:
                    print("Valor inválido para Stop Loss Price. Ignorando.")

            # verificar se a moeda é ignorada
            sl_ignored = False
            for coin in self.ignore_coins_sl_list:
                if coin and symbol.startswith(coin):
                    sl_ignored = True

            tp_ignored = False
            for coin in self.ignore_coins_tp_list:
                if coin and symbol.startswith(coin):
                    tp_ignored = True

            # Verificar Stop Loss Percentual
            delete_position = False
            if pnl_percent <= tracker['trigger_stop_loss_percent'] and self.auto_close_positions:
                if pnl_percent >= 0:
                    if not tp_ignored:
                        self.close_position_market(position)
                        message = f"{position['symbol']} - LUCRO de {pnl_percent:.2f}%"
                        self.show_alert_message(message)
                        self.sound_closed_position_win.play_sound()
                        delete_position = True

                        if self.auto_open_new_position:
                            self.open_new_position_after_close(position)

                else:
                    if not sl_ignored:
                        self.close_position_market(position)
                        message = f"{position['symbol']} - Prejuízo de {pnl_percent:.2f}%"
                        self.show_closed_positions_message(message)
                        self.sound_closed_position_lose.play_sound()
                        delete_position = True

                        if self.auto_open_new_position:
                            self.open_new_position_after_close(position)

            if delete_position:
                positions_to_delete.append(symbol)

        must_update = False
        for pid in positions_to_delete:
            if pid in self.position_trackers:
                del self.position_trackers[pid]
                print(f"Posição {pid} fechada automaticamente.")
                must_update = True

        if must_update:
            self.save_position_trackers()

    def open_new_position_after_close(self, closed_position):
        symbol = self.selected_symbol
        leverage = self.default_leverage
        size = self.default_contract_qty

        print("Iniciando monitoramento de sinais para nova posição...")
        self.monitor_trade_signals(symbol, size, leverage)

    def monitor_trade_signals(self, symbol, size, leverage):
        if self.monitoring_signal:
            return
        self.monitoring_signal = True

        def check_signal():
            if not self.monitoring_signal:
                return

            side = self.decision_value
            # Check trade direction
            if self.trade_direction_option != 'both' and side != self.trade_direction_option and side in ['buy', 'sell']:
                print(f"Sinal {side.upper()} não corresponde à direção selecionada ({self.trade_direction_option.upper()}).")
                self.monitoring_signal = False
                return

            if side in ['buy', 'sell']:
                print(f"Sinal identificado: {side.upper()}. Armazenando preço atual e aguardando 1 minuto.")
                stored_price = self.last_price

                def after_wait():
                    if not self.monitoring_signal:
                        return

                    current_price = self.last_price
                    if side == 'buy':
                        if current_price > stored_price:
                            print(f"O preço aumentou de {stored_price} para {current_price}. Abrindo posição BUY.")
                            position_details = open_new_position_market(symbol, side, size, leverage)
                            if position_details:
                                self.position_trackers[symbol] = {
                                    'position': position_details,
                                    'max_pnl_percent': 0,
                                    'trigger_stop_loss_percent': self.default_stop_loss,
                                    'used_margin_calls': 0
                                }
                                self.save_position_trackers()
                                self.sound_open_position.play_sound()
                                subject = f"Nova posição aberta: {symbol}"
                                message = f"Nova posição aberta: {symbol} - {side.upper()} {leverage}x com {size} contratos."
                                send_email_notification(subject, message)
                            else:
                                print("Falha ao abrir nova posição.")
                        else:
                            print(f"O preço {current_price} não aumentou após 1 minuto. Não abrindo posição BUY.")
                    elif side == 'sell':
                        if current_price < stored_price:
                            print(f"O preço diminuiu de {stored_price} para {current_price}. Abrindo posição SELL.")
                            position_details = open_new_position_market(symbol, side, size, leverage)
                            if position_details:
                                self.position_trackers[symbol] = {
                                    'position': position_details,
                                    'max_pnl_percent': 0,
                                    'trigger_stop_loss_percent': self.default_stop_loss,
                                    'used_margin_calls': 0
                                }
                                self.save_position_trackers()
                                self.sound_open_position.play_sound()
                                subject = f"Nova posição aberta: {symbol}"
                                message = f"Nova posição aberta: {symbol} - {side.upper()} {leverage}x com {size} contratos."
                                send_email_notification(subject, message)
                            else:
                                print("Falha ao abrir nova posição.")
                        else:
                            print(f"O preço {current_price} não diminuiu após 1 minuto. Não abrindo posição SELL.")
                    else:
                        print("Sinal não identificado após 1 minuto.")
                    self.monitoring_signal = False
                    self.update_balance_label()

                # Aguarda 30 segundos
                QTimer.singleShot(30000, after_wait)
            else:
                QTimer.singleShot(5000, check_signal)

        check_signal()

    def check_decision_indicators(self):
        granularity = int(self.granularity)
        decisions = decide_trade_direction(
            self.binance_symbol, self.rsi_period, self.use_sma,
            self.use_rsi, self.use_volume, granularity, self.use_high_low
        )
        self.decision_value = decisions['decision']
        self.sma_value = f"SMA: {decisions['sma']}"
        self.rsi_value = f"RSI: {decisions['rsi']}"
        self.volume_value = f"Volume: {decisions['volume']}"
        self.high_low_value = f"High/Low: {decisions['high_low']}"
        self.use_sma_checkbox.setText(self.sma_value)
        self.use_rsi_checkbox.setText(self.rsi_value)
        self.use_volume_checkbox.setText(self.volume_value)
        self.use_high_low_checkbox.setText(self.high_low_value)

    def show_alert_message(self, message):
        print(message)
        if 'LUCRO' in message:
            self.sound_closed_position_win.play_sound()
        elif 'Prejuízo' in message:
            self.sound_closed_position_lose.play_sound()
        elif 'acima' in message:
            self.sound_price_above.play_sound()
        else:
            self.sound_price_below.play_sound()

    def show_closed_positions_message(self, message):
        print(message)

    def close_position_market(self, position):
        """
        Fechar posição:
        Primeiro, checa se 'symbol' está em ignore_coins_list.
        Se estiver, não fecha a posição. 
        """
        symbol = position.get('symbol', '')

        avg_entry_price = position.get('avgEntryPrice', 0)
        real_leverage = position.get('realLeverage', 0)
        maint_margin = position.get('maintMargin', 0)
        pos_margin = position.get('posMargin', 0)
        unrealised_pnl_value = position.get('unrealisedPnl', 0)
        realised_pnl_value = position.get('realisedPnl', 0)
        current_qty = position.get('currentQty', 0)
        mark_price = position.get('markPrice', 0)

        fee_percent = 0.06 * 2 * real_leverage
        total_fees_percent = fee_percent

        if pos_margin != 0:
            pnl_percent = (unrealised_pnl_value / pos_margin) * 100
            pnl_percent -= total_fees_percent
        else:
            pnl_percent = 0.0

        fee_rate = 0.0006 * 2
        total_fees_paid = fee_rate * real_leverage * maint_margin
        adjusted_unrealised_pnl_value = unrealised_pnl_value - total_fees_paid

        if current_qty < 0:
            position_direction = "SHORT"
        else:
            position_direction = "LONG"

        if avg_entry_price != 0:
            qtd = (real_leverage * maint_margin) / avg_entry_price
        else:
            qtd = 0
        qtd_usdt = abs(qtd * avg_entry_price)

        lucro_prejuizo = "Lucro" if adjusted_unrealised_pnl_value > 0 else "Prejuízo"

        # Verificar se alguma das moedas ignoradas bate com o início do symbol
        if lucro_prejuizo == "Prejuízo":
            for coin in self.ignore_coins_sl_list:
                if coin and symbol.startswith(coin):
                    print(f"Não fechar posições no prejuízo de {coin}. Symbol: {symbol}")
                    return
        else:
            for coin in self.ignore_coins_tp_list:
                if coin and symbol.startswith(coin):
                    print(f"Não fechar posições no lucro de {coin}. Symbol: {symbol}")
                    return

        print(f"Fechando posição: {symbol}")

        subject = f"Posição Fechada {lucro_prejuizo}: {symbol}"
        message = (
            f"Detalhes da posição fechada:\n"
            f"Contrato: {symbol}\n"
            f"Direção: {position_direction}\n"
            f"Quantidade: {qtd_usdt:.2f} USDT\n"
            f"Preço de entrada: {avg_entry_price}\n"
            f"Preço de saída: {mark_price}\n"
            f"Margem: {pos_margin:.2f} USDT\n"
            f"Alavancagem: {real_leverage}x\n"
            f"Lucro/Prejuízo: {adjusted_unrealised_pnl_value:.2f} USDT ({pnl_percent:.2f}%)\n"
        )

        send_email_notification(subject, message)
        close_position_market(position)

        if symbol in self.position_trackers:
            del self.position_trackers[symbol]
            self.save_position_trackers()
            self.update_used_margin_calls_label(0)

        self.update_balance_label()

    def update_price_label(self, price):
        previous_price = self.last_price
        self.last_price = price
        formatted_price = f"{self.selected_symbol} ${price:,.2f}"
        self.price_label.setText(formatted_price)

        current_time = time.time()
        time_since_last_update = current_time - self.last_updated_price_time

        if time_since_last_update >= 1:
            if price > previous_price:
                self.price_label.setStyleSheet("color: #00ff00;")
            elif price < previous_price:
                self.price_label.setStyleSheet("color: #ff3333;")
            else:
                self.price_label.setStyleSheet("color: #ffffff;")
            self.last_updated_price_time = current_time

        # Alerts de preço
        if self.alert_price_above > 0 and price >= self.alert_price_above:
            if not self.alert_above_triggered:
                self.alert_above_triggered = True
                print("ALERTA: Preço acima do valor definido")
                self.sound_price_above.play_sound()
                self.show_alert_message(f"Alerta: Preço acima de {self.alert_price_above}")
        else:
            self.alert_above_triggered = False

        if self.alert_price_below > 0 and price <= self.alert_price_below:
            if not self.alert_below_triggered:
                self.alert_below_triggered = True
                print("ALERTA: Preço abaixo do valor definido")
                self.sound_price_below.play_sound()
                self.show_alert_message(f"Alerta: Preço abaixo de {self.alert_price_below}")
        else:
            self.alert_below_triggered = False

        if self.first_run:
            self.price_alert_above = price * 1.01
            self.price_alert_below = price * 0.99
            self.alert_entry_above.setText(str(int(self.price_alert_above)))
            self.alert_entry_below.setText(str(int(self.price_alert_below)))
            self.first_run = False

    def buy_market(self):
        symbol = self.selected_symbol
        leverage = self.default_leverage
        size = self.default_contract_qty

        position_details = open_new_position_market(symbol, 'buy', size, leverage)
        if position_details:
            self.position_trackers[symbol] = {
                'position': position_details,
                'max_pnl_percent': 0,
                'trigger_stop_loss_percent': self.default_stop_loss,
                'used_margin_calls': 0
            }
            self.save_position_trackers()
            self.sound_open_position.play_sound()
            self.update_used_margin_calls_label(0)
            self.monitoring_signal = False

            subject = f"Nova posição aberta: {symbol}"
            message = f"Nova posição aberta: {symbol} - BUY {leverage}x com {size} contratos."
            send_email_notification(subject, message)
        else:
            print("Falha ao abrir posição BUY.")
        self.monitoring_signal = False

    def sell_market(self):
        symbol = self.selected_symbol
        leverage = self.default_leverage
        size = self.default_contract_qty

        position_details = open_new_position_market(symbol, 'sell', size, leverage)
        if position_details:
            self.position_trackers[symbol] = {
                'position': position_details,
                'max_pnl_percent': 0,
                'trigger_stop_loss_percent': self.default_stop_loss,
                'used_margin_calls': 0
            }
            self.save_position_trackers()
            self.sound_open_position.play_sound()
            self.update_used_margin_calls_label(0)
            self.monitoring_signal = False

            subject = f"Nova posição aberta: {symbol}"
            message = f"Nova posição aberta: {symbol} - SELL {leverage}x com {size} contratos."
            send_email_notification(subject, message)
        else:
            print("Falha ao abrir posição SELL.")
        self.monitoring_signal = False

    def load_configurations(self):
        try:
            with open('configurations.json', 'r') as f:
                config = json.load(f)
                self.default_leverage = config.get('default_leverage', self.default_leverage)
                self.default_stop_loss = config.get('default_stop_loss', self.default_stop_loss)
                self.stop_loss_price = config.get('stop_loss_price', self.stop_loss_price)
                self.auto_calc_trailing_stop = config.get('auto_calc_trailing_stop', self.auto_calc_trailing_stop)
                self.trailing_stop_1_15 = config.get('trailing_stop_1_15', self.trailing_stop_1_15)
                self.trailing_stop_16_30 = config.get('trailing_stop_16_30', self.trailing_stop_16_30)
                self.trailing_stop_31_50 = config.get('trailing_stop_31_50', self.trailing_stop_31_50)
                self.trailing_stop_above_50 = config.get('trailing_stop_above_50', self.trailing_stop_above_50)
                self.alert_price_above = config.get('alert_price_above', self.alert_price_above)
                self.alert_price_below = config.get('alert_price_below', self.alert_price_below)
                self.default_contract_qty = config.get('default_contract_qty', self.default_contract_qty)
                self.rsi_period = config.get('rsi_period', self.rsi_period)
                self.use_sma = config['use_sma']
                self.use_rsi = config['use_rsi']
                self.use_volume = config['use_volume']
                self.use_high_low = config['use_high_low']
                self.granularity = config.get('granularity', self.granularity)
                self.selected_symbol = config.get('selected_symbol', self.selected_symbol)
                self.auto_open_new_position = config.get('auto_open_new_position', self.auto_open_new_position)
                self.auto_close_positions = config.get('auto_close_positions', self.auto_close_positions)
                self.margin_calls = config.get('margin_calls', self.margin_calls)
                self.trade_direction_option = config.get('trade_direction_option', self.trade_direction_option)

                # Novo: ignorar moedas
                self.ignore_coins_sl = config.get('ignore_coins_sl', self.ignore_coins_sl)
                self.ignore_coins_sl_list = [c.strip() for c in self.ignore_coins_sl.split(',') if c.strip()]

                self.ignore_coins_tp = config.get('ignore_coins_tp', self.ignore_coins_tp)
                self.ignore_coins_tp_list = [c.strip() for c in self.ignore_coins_tp.split(',') if c.strip()]

            print("Configurações carregadas com sucesso.")
        except FileNotFoundError:
            print("Arquivo de configurações não encontrado. Usando configurações padrão.")
        except Exception as e:
            print(f"Erro ao carregar configurações: {e}")

    def save_configurations(self):
        try:
            config = {
                'default_leverage': self.default_leverage,
                'default_stop_loss': self.default_stop_loss,
                'stop_loss_price': self.stop_loss_price,
                'auto_calc_trailing_stop': self.auto_calc_trailing_stop,
                'trailing_stop_1_15': self.trailing_stop_1_15,
                'trailing_stop_16_30': self.trailing_stop_16_30,
                'trailing_stop_31_50': self.trailing_stop_31_50,
                'trailing_stop_above_50': self.trailing_stop_above_50,
                'alert_price_above': self.alert_price_above,
                'alert_price_below': self.alert_price_below,
                'default_contract_qty': self.default_contract_qty,
                'rsi_period': self.rsi_period,
                'use_sma': self.use_sma,
                'use_rsi': self.use_rsi,
                'use_volume': self.use_volume,
                'use_high_low': self.use_high_low,
                'granularity': self.granularity,
                'selected_symbol': self.selected_symbol,
                'auto_open_new_position': self.auto_open_new_position,
                'auto_close_positions': self.auto_close_positions,
                'margin_calls': self.margin_calls,
                'trade_direction_option': self.trade_direction_option,
                # salva ignore_coins
                'ignore_coins_sl': self.ignore_coins_sl,
                'ignore_coins_tp': self.ignore_coins_tp
            }
            with open('configurations.json', 'w') as f:
                json.dump(config, f)
            print("Configurações salvas com sucesso.")
        except Exception as e:
            print(f"Erro ao salvar configurações: {e}")

    def load_position_trackers(self):
        try:
            with open('position_trackers.json', 'r') as f:
                self.position_trackers = json.load(f)
            print("Position trackers carregados com sucesso.")
        except FileNotFoundError:
            print("Arquivo de position trackers não encontrado. Iniciando novo.")
            self.position_trackers = {}
        except Exception as e:
            print(f"Erro ao carregar position trackers: {e}")
            self.position_trackers = {}

    def save_position_trackers(self):
        try:
            with open('position_trackers.json', 'w') as f:
                json.dump(self.position_trackers, f)
            print("Position trackers salvos com sucesso.")
        except Exception as e:
            print(f"Erro ao salvar position trackers: {e}")

    def update_balance_label(self):
        account_info = get_account_overview()
        if account_info:
            usdt_balance = float(account_info.get('availableBalance', 0))
            self.balance_label.setText(f"${usdt_balance:.2f}")
            if usdt_balance < 0:
                self.balance_label.setStyleSheet("color: #ff3333;")
            else:
                self.balance_label.setStyleSheet("color: #00ff00;")
        else:
            self.balance_label.setText("Saldo: N/A")

    def update_used_margin_calls_label(self, used_calls):
        self.used_margin_calls_label.setText(f"({used_calls})")


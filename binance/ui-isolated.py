# ui.py

import time
import json
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QCheckBox
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
    get_margin_account_balance
)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Initialize variables
        self.selected_symbol = 'BTCUSDT'  # Fixed trading pair
        self.default_leverage = 10
        self.default_stop_loss = -3.0  # Default stop loss in percentage
        self.trailing_stop_16_30 = 3
        self.trailing_stop_31_50 = 5
        self.trailing_stop_above_50 = 10
        self.alert_price_above = 0
        self.alert_price_below = 0
        self.default_usd_amount = 10
        self.rsi_period = 14
        self.use_sma = True
        self.use_rsi = True
        self.use_volume = False
        self.auto_open_new_position = False
        self.granularity = '5'

        self.position_trackers = {}
        self.load_position_trackers()

        self.monitoring_signal = False
        self.decision_value = 'wait'
        self.sma_value = ''
        self.rsi_value = ''
        self.volume_value = ''
        self.first_run = True

        self.price_alert_above = 0
        self.price_alert_below = 0
        self.last_price = 0
        self.alert_above_triggered = False
        self.alert_below_triggered = False
        self.last_updated_price_time = 0

        # Carrega as configurações do arquivo
        self.load_configurations()

        # Initialize UI components
        self.init_ui()

        # Initialize sounds
        self.sound_player = SoundPlayer("correct-chime.mp3")  # Initialize sound player
        self.sound_closed_position_win = SoundPlayer("closed-position-win.mp3")
        self.sound_closed_position_lose = SoundPlayer("closed-position-lose.mp3")
        self.sound_price_above = SoundPlayer("price-above.mp3")
        self.sound_price_below = SoundPlayer("price-below.mp3")
        self.sound_open_position = SoundPlayer("coin.mp3")

        # Start price websocket client
        self.price_ws_client = PriceWebsocketClient(self.selected_symbol)
        self.price_ws_client.price_updated.connect(self.update_price_label)
        self.price_ws_client.start()
        self.sound_player.play_sound()

    def init_ui(self):
        self.setWindowTitle("Leverage Trading Bot")
        self.setGeometry(0, 0, 1240, 600)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Apply dark theme
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
            QCheckBox {
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QCheckBox::indicator {
                border: 1px solid #5a5a5a;
                background: none;
            }
            QCheckBox::indicator:checked {
                background-color: #55ff55;
            }
        """)

        # High and Low labels
        self.last_hour_label = QLabel("Last Hour: ")
        self.last_hour_label.setFont(QFont("Arial", 8))
        self.last_hour_label.setStyleSheet("color: #cccccc;")

        self.high_label = QLabel("High: N/A")
        self.high_label.setStyleSheet("color: #00ff00;")
        self.low_label = QLabel("Low: N/A")
        self.low_label.setStyleSheet("color: #ff3333;")
        high_low_layout = QHBoxLayout()
        high_low_layout.addWidget(self.last_hour_label)
        high_low_layout.addWidget(self.high_label)
        # add spacing between high and low labels
        high_low_layout.addStretch()
        high_low_layout.addWidget(self.low_label)
        main_layout.addLayout(high_low_layout)

        # Price label
        self.price_label = QLabel(f"{self.selected_symbol} $0.00")
        self.price_label.setFont(QFont("Arial", 24))
        self.price_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.price_label)

        # Configuration inputs
        config_hbox = QHBoxLayout()
        config_left_layout = QFormLayout()
        config_right_layout = QFormLayout()

        # Leverage
        leverage_label = QLabel("Leverage:")
        leverage_label.setFont(QFont("Arial", 12))
        self.leverage_input = QLineEdit(str(self.default_leverage))
        self.leverage_input.setFont(QFont("Arial", 12))
        self.leverage_input.setFixedWidth(100)
        self.leverage_input.textChanged.connect(self.check_parameters_changes)
        config_left_layout.addRow(leverage_label, self.leverage_input)

        # Default Stop Loss
        default_stop_loss_label = QLabel("Default Stop Loss (%):")
        default_stop_loss_label.setFont(QFont("Arial", 12))
        self.default_stop_loss_input = QLineEdit(str(self.default_stop_loss))
        self.default_stop_loss_input.setFont(QFont("Arial", 12))
        self.default_stop_loss_input.setFixedWidth(100)
        self.default_stop_loss_input.textChanged.connect(self.check_parameters_changes)
        config_left_layout.addRow(default_stop_loss_label, self.default_stop_loss_input)

        # Trailing Stops
        trailing_stop_16_30_label = QLabel("Trailing Stop 16-30%:")
        trailing_stop_16_30_label.setFont(QFont("Arial", 12))
        self.trailing_stop_16_30_input = QLineEdit(str(self.trailing_stop_16_30))
        self.trailing_stop_16_30_input.setFont(QFont("Arial", 12))
        self.trailing_stop_16_30_input.setFixedWidth(100)
        self.trailing_stop_16_30_input.textChanged.connect(self.check_parameters_changes)
        config_left_layout.addRow(trailing_stop_16_30_label, self.trailing_stop_16_30_input)

        trailing_stop_31_50_label = QLabel("Trailing Stop 31-50%:")
        trailing_stop_31_50_label.setFont(QFont("Arial", 12))
        self.trailing_stop_31_50_input = QLineEdit(str(self.trailing_stop_31_50))
        self.trailing_stop_31_50_input.setFont(QFont("Arial", 12))
        self.trailing_stop_31_50_input.setFixedWidth(100)
        self.trailing_stop_31_50_input.textChanged.connect(self.check_parameters_changes)
        config_left_layout.addRow(trailing_stop_31_50_label, self.trailing_stop_31_50_input)

        trailing_stop_above_50_label = QLabel("Trailing Stop Above 50%:")
        trailing_stop_above_50_label.setFont(QFont("Arial", 12))
        self.trailing_stop_above_50_input = QLineEdit(str(self.trailing_stop_above_50))
        self.trailing_stop_above_50_input.setFont(QFont("Arial", 12))
        self.trailing_stop_above_50_input.setFixedWidth(100)
        self.trailing_stop_above_50_input.textChanged.connect(self.check_parameters_changes)
        config_left_layout.addRow(trailing_stop_above_50_label, self.trailing_stop_above_50_input)

        # Alert Prices
        alert_price_above_label = QLabel("Alert Price Above:")
        alert_price_above_label.setFont(QFont("Arial", 12))
        self.alert_entry_above = QLineEdit(str(self.alert_price_above))
        self.alert_entry_above.setFont(QFont("Arial", 12))
        self.alert_entry_above.setFixedWidth(100)
        config_right_layout.addRow(alert_price_above_label, self.alert_entry_above)

        alert_price_below_label = QLabel("Alert Price Below:")
        alert_price_below_label.setFont(QFont("Arial", 12))
        self.alert_entry_below = QLineEdit(str(self.alert_price_below))
        self.alert_entry_below.setFont(QFont("Arial", 12))
        self.alert_entry_below.setFixedWidth(100)
        config_right_layout.addRow(alert_price_below_label, self.alert_entry_below)

        # Default USD Amount
        default_usd_amount_label = QLabel("Trade Amount (USD):")
        default_usd_amount_label.setFont(QFont("Arial", 12))
        self.default_usd_amount_input = QLineEdit(str(self.default_usd_amount))
        self.default_usd_amount_input.setFont(QFont("Arial", 12))
        self.default_usd_amount_input.setFixedWidth(100)
        self.default_usd_amount_input.textChanged.connect(self.check_parameters_changes)
        config_right_layout.addRow(default_usd_amount_label, self.default_usd_amount_input)

        # Input for RSI period
        rsi_label = QLabel("RSI period:")
        rsi_label.setFont(QFont("Arial", 12))
        self.rsi_period_input = QLineEdit(str(self.rsi_period))
        self.rsi_period_input.setFont(QFont("Arial", 12))
        self.rsi_period_input.setFixedWidth(100)
        self.rsi_period_input.textChanged.connect(self.check_parameters_changes)
        config_right_layout.addRow(rsi_label, self.rsi_period_input)

        # Granularity radio buttons
        granularity_layout = QHBoxLayout()
        granularity_layout.setContentsMargins(0, 0, 0, 0)
        granularity_layout.setSpacing(0)

        granularity_label = QLabel("Granularity:")
        granularity_label.setFont(QFont("Arial", 12))
        granularity_layout.addWidget(granularity_label)
        granularity_layout.addSpacing(70)

        self.granularity_1m_checkbox = QCheckBox("1m")
        self.granularity_1m_checkbox.setFont(QFont("Arial", 12))
        self.granularity_1m_checkbox.setChecked(self.granularity == '1')
        self.granularity_1m_checkbox.setStyleSheet("QCheckBox { color: white; margin-right: 20px;}")
        self.granularity_1m_checkbox.stateChanged.connect(lambda state: self.select_granularity(state, self.granularity_1m_checkbox))
        granularity_layout.addWidget(self.granularity_1m_checkbox)

        self.granularity_5m_checkbox = QCheckBox("5m")
        self.granularity_5m_checkbox.setFont(QFont("Arial", 12))
        self.granularity_5m_checkbox.setChecked(self.granularity == '5')
        self.granularity_5m_checkbox.setStyleSheet("QCheckBox { color: white; margin-right: 20px;}")
        self.granularity_5m_checkbox.stateChanged.connect(lambda state: self.select_granularity(state, self.granularity_5m_checkbox))
        granularity_layout.addWidget(self.granularity_5m_checkbox)

        granularity_layout.addStretch()
        config_right_layout.addRow(granularity_layout)

        # Add layouts to config_hbox
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

        # Checkbox to automatically open new positions
        self.auto_open_checkbox = QCheckBox("Abrir nova posição automaticamente")
        self.auto_open_checkbox.setFont(QFont("Arial", 12))
        self.auto_open_checkbox.setChecked(self.auto_open_new_position)
        self.auto_open_checkbox.stateChanged.connect(lambda state: self.toggle_auto_open(state, self.auto_open_checkbox))

        self.auto_open_checkbox.setStyleSheet("QCheckBox { color: white; margin-left: 20px;}")

        # Label para o saldo
        self.balance_prelabel = QLabel("Saldo: ")
        self.balance_prelabel.setFont(QFont("Arial", 12))
        self.balance_prelabel.setStyleSheet("color: #ffffff;")
        self.balance_label = QLabel("N/A")
        self.balance_label.setFont(QFont("Arial", 12))
        self.balance_label.setStyleSheet("color: #ffffff;")

        # Layout horizontal para alinhar checkbox e label
        balance_layout = QHBoxLayout()
        balance_layout.addWidget(self.auto_open_checkbox)
        balance_layout.addStretch()
        balance_layout.addWidget(self.balance_prelabel)
        balance_layout.addWidget(self.balance_label)

        main_layout.addLayout(balance_layout)

        # SMA, RSI, and Volume
        indicator_layout = QHBoxLayout()
        indicator_layout.setContentsMargins(150, 20, 150, 0)

        self.use_sma_checkbox = QCheckBox()
        self.use_sma_checkbox.setChecked(self.use_sma)
        self.use_sma_checkbox.setText(self.sma_value)
        self.use_sma_checkbox.setFont(QFont("Arial", 12))
        self.use_sma_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'sma'))
        self.use_sma_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")

        indicator_layout.addWidget(self.use_sma_checkbox)

        self.use_rsi_checkbox = QCheckBox()
        self.use_rsi_checkbox.setChecked(self.use_rsi)
        self.use_rsi_checkbox.setText(self.rsi_value)
        self.use_rsi_checkbox.setFont(QFont("Arial", 12))
        self.use_rsi_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'rsi'))
        self.use_rsi_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")

        indicator_layout.addWidget(self.use_rsi_checkbox)

        self.use_volume_checkbox = QCheckBox()
        self.use_volume_checkbox.setChecked(self.use_volume)
        self.use_volume_checkbox.setText(self.volume_value)
        self.use_volume_checkbox.setFont(QFont("Arial", 12))
        self.use_volume_checkbox.stateChanged.connect(lambda state: self.toggle_indicator(state, 'volume'))
        self.use_volume_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")

        indicator_layout.addWidget(self.use_volume_checkbox)
        indicator_layout.addStretch()
        main_layout.addLayout(indicator_layout)

        # Positions table
        self.positions_table = QTableWidget()
        self.positions_table.setRowCount(0)
        columns = ["Contract", "Amount", "Entry/Mark Price", "Margin", "Unrealized PNL", "Trigger", "Actions"]
        self.positions_table.setColumnCount(len(columns))
        self.positions_table.setHorizontalHeaderLabels(columns)
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.positions_table)

        self.setLayout(main_layout)

        # Configure timers
        self.timer = QTimer()
        self.timer.timeout.connect(self.fetch_open_positions)
        self.timer.start(1000)

        self.auto_close_timer = QTimer()
        self.auto_close_timer.timeout.connect(self.check_auto_close_positions)
        self.auto_close_timer.start(1000)

        # Timer to get High/Low prices every minute
        self.high_low_timer = QTimer()
        self.high_low_timer.timeout.connect(self.fetch_high_low_prices)
        self.high_low_timer.start(60000)  # Every 60 seconds
        self.fetch_high_low_prices()  # Initial fetch

        self.get_indicators_timer = QTimer()
        self.get_indicators_timer.timeout.connect(self.check_decision_indicators)
        self.get_indicators_timer.start(5000)

        # Timer para atualizar o saldo
        self.balance_timer = QTimer()
        self.balance_timer.timeout.connect(self.update_balance_label)
        self.balance_timer.start(60000)  # Atualiza a cada 60 segundos
        self.update_balance_label()  # Primeira atualização

    def toggle_auto_open(self, state, checkbox=None):
        """
        Updates the corresponding flags based on the checkbox state.
        """
        if checkbox == self.auto_open_checkbox:
            self.auto_open_new_position = state == Qt.Checked
        self.check_parameters_changes()  # Auto-save configurations

    def toggle_indicator(self, state, indicator):
        """
        Toggles the use of an indicator based on checkbox state.
        """
        if indicator == 'sma':
            self.use_sma = state == Qt.Checked
        elif indicator == 'rsi':
            self.use_rsi = state == Qt.Checked
        elif indicator == 'volume':
            self.use_volume = state == Qt.Checked
        self.check_parameters_changes()  # Auto-save configurations

    def select_granularity(self, state, checkbox):
        # Check which checkbox was clicked and adjust states
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
        self.check_parameters_changes()  # Auto-save configurations

    def reset_alerts(self):
        self.alert_above_triggered = False
        self.alert_below_triggered = False

    def check_parameters_changes(self):
        """Updates variables based on inputs."""
        try:
            new_leverage = int(self.leverage_input.text())
            new_default_stop_loss = float(self.default_stop_loss_input.text())
            new_trailing_stop_16_30 = float(self.trailing_stop_16_30_input.text())
            new_trailing_stop_31_50 = float(self.trailing_stop_31_50_input.text())
            new_trailing_stop_above_50 = float(self.trailing_stop_above_50_input.text())
            new_alert_price_above = float(self.alert_entry_above.text())
            new_alert_price_below = float(self.alert_entry_below.text())
            new_default_usd_amount = float(self.default_usd_amount_input.text())
            new_rsi_period = int(self.rsi_period_input.text())

            self.default_leverage = new_leverage
            self.default_stop_loss = new_default_stop_loss
            self.trailing_stop_16_30 = new_trailing_stop_16_30
            self.trailing_stop_31_50 = new_trailing_stop_31_50
            self.trailing_stop_above_50 = new_trailing_stop_above_50
            self.alert_price_above = new_alert_price_above
            self.alert_price_below = new_alert_price_below
            self.default_usd_amount = new_default_usd_amount
            self.rsi_period = new_rsi_period
            self.reset_alerts()

            # Visual indicator on the button
            self.save_config_button.setStyleSheet("background-color: #00ff00; color: black; min-height: 30px;")
            self.save_config_button.setText("Salvo com sucesso!")
            QTimer.singleShot(500, lambda: self.save_config_button.setStyleSheet("min-height: 30px;"))
            QTimer.singleShot(500, lambda: self.save_config_button.setText("Salvar configurações"))

            # Save configurations to file
            self.save_configurations()

        except ValueError as e:
            print(f"Erro ao salvar configurações. Verifique os valores inseridos: {e}")
            self.save_config_button.setStyleSheet("background-color: #ff0000; color: black; min-height: 30px;")
            self.save_config_button.setText("Ocorreu um erro!")
            QTimer.singleShot(500, lambda: self.save_config_button.setStyleSheet("min-height: 30px;"))
            QTimer.singleShot(500, lambda: self.save_config_button.setText("Salvar configurações"))

    def fetch_open_positions(self):
        try:
            data = fetch_open_positions(self.position_trackers)
            self.update_positions_display(data)

            if data:
                self.monitoring_signal = False

            if not data and self.auto_open_new_position and not self.monitoring_signal:
                self.open_new_position_after_close(None)

        except Exception as e:
            print(f"Erro ao obter posições: {e}")
            self.monitoring_signal = False  # Deactivate monitoring_signal
            self.update_positions_display([])  # Update interface with empty data

    def fetch_high_low_prices(self):
        high_price, low_price = fetch_high_low_prices(self.selected_symbol)
        if high_price is not None and low_price is not None:
            self.high_label.setText(f"High: ${high_price:,.2f}")
            self.low_label.setText(f"Low: ${low_price:,.2f}")
        else:
            self.high_label.setText("High: N/A")
            self.low_label.setText("Low: N/A")

    def update_positions_display(self, positions):
        """Updates the QTableWidget with the latest position data."""
        self.positions_table.setRowCount(0)
        current_positions_ids = set()
        for position in positions:
            symbol = position['symbol']
            current_positions_ids.add(symbol)

            row_position = self.positions_table.rowCount()
            self.positions_table.insertRow(row_position)

            # Data preparations
            side = position['side']
            amount_usd = position['amount_usd']
            entry_price = position['entry_price']
            current_price = position['current_price']
            margin = position['margin']
            pnl = position['pnl']
            pnl_percentage = position['pnl_percentage']
            leverage = position.get('leverage', self.default_leverage)

            # Get trigger from position trackers
            tracker = self.position_trackers.get(symbol, {})
            trigger = tracker.get('trigger_stop_loss_percent', 'N/A')

            # Contract cell
            contract_item = QTableWidgetItem(f"{symbol} ({side}) {leverage}x")
            contract_item.setTextAlignment(Qt.AlignCenter)
            if side == 'LONG':
                contract_item.setForeground(QBrush(QColor('green')))
            else:
                contract_item.setForeground(QBrush(QColor('red')))

            # Amount cell
            amount_item = QTableWidgetItem(f"${amount_usd:.2f}")
            amount_item.setTextAlignment(Qt.AlignCenter)

            # Entry/Mark Price cell
            if entry_price and current_price:
                entry_mark_price_item = QTableWidgetItem(f"{entry_price:.2f} / {current_price:.2f}")
            else:
                entry_mark_price_item = QTableWidgetItem("N/A")
            entry_mark_price_item.setTextAlignment(Qt.AlignCenter)

            # Margin cell
            margin_item = QTableWidgetItem(f"${margin:.2f}")
            margin_item.setTextAlignment(Qt.AlignCenter)

            # Unrealized PNL cell
            if pnl is not None and pnl_percentage is not None:
                pnl_color = QColor('green') if pnl >= 0 else QColor('red')
                pnl_item = QTableWidgetItem(f"{pnl:.2f} USDT ({pnl_percentage:.2f}%)")
                pnl_item.setTextAlignment(Qt.AlignCenter)
                pnl_item.setForeground(QBrush(pnl_color))
            else:
                pnl_item = QTableWidgetItem("N/A")
                pnl_item.setTextAlignment(Qt.AlignCenter)

            # Trigger cell
            if trigger != 'N/A' and trigger is not None:
                trigger_value = float(trigger)
                trigger_item = QTableWidgetItem(f"{trigger_value:.2f}%")
                if trigger_value > 0:
                    trigger_item.setForeground(QBrush(QColor('green')))
                else:
                    trigger_item.setForeground(QBrush(QColor('red')))
            else:
                trigger_item = QTableWidgetItem("N/A")
                trigger_item.setForeground(QBrush(QColor('gray')))

            trigger_item.setTextAlignment(Qt.AlignCenter)

            # Add items to the table
            self.positions_table.setItem(row_position, 0, contract_item)
            self.positions_table.setItem(row_position, 1, amount_item)
            self.positions_table.setItem(row_position, 2, entry_mark_price_item)
            self.positions_table.setItem(row_position, 3, margin_item)
            self.positions_table.setItem(row_position, 4, pnl_item)
            self.positions_table.setItem(row_position, 5, trigger_item)

            # Action buttons
            market_button = QPushButton("Close Position")
            market_button.clicked.connect(lambda checked, pos=position: self.close_position_market(pos))
            self.positions_table.setCellWidget(row_position, 6, market_button)

            # Tracking positions for auto-closing
            if symbol not in self.position_trackers:
                # Initialize tracker for new position
                self.position_trackers[symbol] = {
                    'position': position,
                    'max_pnl_percent': 0,
                    'trigger_stop_loss_percent': self.default_stop_loss
                }
                self.save_position_trackers()  # Save after adding new position
            else:
                # Update existing tracker
                tracker = self.position_trackers[symbol]
                tracker['position'] = position  # Update position data

        # Remove trackers for closed positions
        for pid in list(self.position_trackers.keys()):
            if pid not in current_positions_ids:
                del self.position_trackers[pid]
                self.save_position_trackers()  # Save after removing position

    def check_auto_close_positions(self):
        """Automatically closes positions based on custom logic."""
        positions_to_delete = []

        for symbol, tracker in self.position_trackers.items():
            position = tracker['position']
            pnl_percentage = float(position.get('pnl_percentage', 0.0))  # Default to 0.0 if None

            # Ensure pnl_percentage is a float
            if pnl_percentage is None:
                pnl_percentage = 0.0

            # Determine the appropriate stop loss based on new rules
            if isinstance(pnl_percentage, float):
                if 0.5 <= pnl_percentage <= 15.9:
                    calculated_stop_loss = self.default_stop_loss + pnl_percentage
                elif 16 <= pnl_percentage <= 30:
                    calculated_stop_loss = pnl_percentage - self.trailing_stop_16_30
                elif 31 <= pnl_percentage <= 50:
                    calculated_stop_loss = pnl_percentage - self.trailing_stop_31_50
                elif pnl_percentage > 50:
                    calculated_stop_loss = pnl_percentage - self.trailing_stop_above_50
                else:
                    calculated_stop_loss = self.default_stop_loss  # Use default stop loss

                # Update stop loss in tracker if greater than current
                if ('trigger_stop_loss_percent' not in tracker or calculated_stop_loss > tracker['trigger_stop_loss_percent']) or (pnl_percentage < 0 and calculated_stop_loss < tracker['trigger_stop_loss_percent']):
                    tracker['trigger_stop_loss_percent'] = calculated_stop_loss

                # Update the maximum profit percentage achieved
                if pnl_percentage > tracker.get('max_pnl_percent', 0):
                    tracker['max_pnl_percent'] = pnl_percentage
                elif pnl_percentage < 0 and pnl_percentage < tracker.get('max_pnl_percent', 0):
                    tracker['max_pnl_percent'] = pnl_percentage

                # Check if profit percentage has fallen below configured stop loss
                if pnl_percentage <= tracker['trigger_stop_loss_percent']:
                    if pnl_percentage >= 0:
                        # Close position with profit
                        self.close_position_market(position)
                        message = (
                            f"{position['symbol']} - "
                            f"LUCRO de {pnl_percentage:.2f}%"
                        )
                        self.show_alert_message(message)
                        self.sound_closed_position_win.play_sound()
                    else:
                        # Close position with loss
                        self.close_position_market(position)
                        message = (
                            f"{position['symbol']} - "
                            f"Prejuízo de {pnl_percentage:.2f}%"
                        )
                        self.show_closed_positions_message(message)
                        self.sound_closed_position_lose.play_sound()

                    # If the option is checked, open a new position
                    if self.auto_open_new_position:
                        self.open_new_position_after_close(position)

                    # Mark for removal
                    positions_to_delete.append(symbol)
                    continue

        # Remove trackers after iteration
        for pid in positions_to_delete:
            if pid in self.position_trackers:
                del self.position_trackers[pid]
                self.save_position_trackers()

    def open_new_position_after_close(self, closed_position):
        """Starts monitoring signals to open a new position."""
        symbol = self.selected_symbol
        leverage = self.default_leverage
        usd_amount = self.default_usd_amount

        # Start monitoring signals
        print("Iniciando monitoramento de sinais para nova posição...")
        self.monitor_trade_signals(symbol, usd_amount, leverage)

    def monitor_trade_signals(self, symbol, usd_amount, leverage):
        """Monitors trade signals and opens a new position when a signal is identified."""
        if self.monitoring_signal:
            return
        self.monitoring_signal = True

        def check_signal():
            side = self.decision_value.upper()
            if side in ['BUY', 'SELL']:
                print(f"Sinal identificado: {side.upper()}. Abrindo nova posição.")
                # Obter detalhes da posição
                position_details = open_new_position_market(symbol, side, usd_amount, leverage)
                if position_details:
                    # Armazenar detalhes da posição
                    self.position_trackers[symbol] = {
                        'position': position_details,
                        'max_pnl_percent': 0,
                        'trigger_stop_loss_percent': self.default_stop_loss
                    }
                    self.save_position_trackers()
                    self.sound_open_position.play_sound()
                else:
                    print("Falha ao abrir nova posição.")
                self.monitoring_signal = False  # Stop monitoring
                self.update_balance_label()  # Update balance after opening new position
            else:
                # Continue monitoring
                print("Sinal não identificado. Continuando monitoramento...")
                QTimer.singleShot(5000, check_signal)  # Check again in 5 seconds

        # Start the first check immediately
        check_signal()

    def check_decision_indicators(self):
        granularity = int(self.granularity)
        decisions = decide_trade_direction(self.selected_symbol, self.rsi_period, self.use_sma, self.use_rsi, self.use_volume, granularity)
        self.decision_value = decisions['decision']
        self.sma_value = f"SMA: {decisions['sma']}"
        self.rsi_value = f"RSI: {decisions['rsi']}"
        self.volume_value = f"Volume: {decisions['volume']}"
        self.use_sma_checkbox.setText(self.sma_value)
        self.use_rsi_checkbox.setText(self.rsi_value)
        self.use_volume_checkbox.setText(self.volume_value)

    def show_alert_message(self, message):
        """Displays an alert message and plays a sound."""
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
        """Displays a message for closed positions."""
        print(message)

    def close_position_market(self, position):
        print(f"Fechando posição: {position['symbol']}")
        close_position_market(position)
        # Remove position from trackers and save
        symbol = position['symbol']
        if symbol in self.position_trackers:
            del self.position_trackers[symbol]
            self.save_position_trackers()
        self.update_balance_label()  # Update balance after closing position

    def update_price_label(self, price):
        previous_price = self.last_price
        self.last_price = price  # Update last price for other methods
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

        # Check for alerts only if the alert prices are greater than 0
        if self.alert_price_above > 0 and price >= self.alert_price_above:
            if not self.alert_above_triggered:
                self.alert_above_triggered = True
                print("ALERTA: Preço acima do valor definido")
                self.sound_price_above.play_sound()
                # Set alert message
                self.show_alert_message(f"Alerta: Preço acima de {self.alert_price_above}")
        else:
            self.alert_above_triggered = False

        if self.alert_price_below > 0 and price <= self.alert_price_below:
            if not self.alert_below_triggered:
                self.alert_below_triggered = True
                print("ALERTA: Preço abaixo do valor definido")
                self.sound_price_below.play_sound()
                # Set alert message
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
        usd_amount = self.default_usd_amount
        position_details = open_new_position_market(symbol, 'BUY', usd_amount, leverage)
        if position_details:
            # Armazenar detalhes da posição
            self.position_trackers[symbol] = {
                'position': position_details,
                'max_pnl_percent': 0,
                'trigger_stop_loss_percent': self.default_stop_loss
            }
            self.save_position_trackers()
            self.sound_open_position.play_sound()
        else:
            print("Falha ao abrir posição BUY.")
        self.monitoring_signal = False

    def sell_market(self):
        symbol = self.selected_symbol
        leverage = self.default_leverage
        usd_amount = self.default_usd_amount
        position_details = open_new_position_market(symbol, 'SELL', usd_amount, leverage)
        if position_details:
            # Armazenar detalhes da posição
            self.position_trackers[symbol] = {
                'position': position_details,
                'max_pnl_percent': 0,
                'trigger_stop_loss_percent': self.default_stop_loss
            }
            self.save_position_trackers()
            self.sound_open_position.play_sound()
        else:
            print("Falha ao abrir posição SELL.")
        self.monitoring_signal = False

    def load_configurations(self):
        """Carrega as configurações de um arquivo JSON."""
        try:
            with open('configurations.json', 'r') as f:
                config = json.load(f)
                self.default_leverage = config.get('default_leverage', self.default_leverage)
                self.default_stop_loss = config.get('default_stop_loss', self.default_stop_loss)
                self.trailing_stop_16_30 = config.get('trailing_stop_16_30', self.trailing_stop_16_30)
                self.trailing_stop_31_50 = config.get('trailing_stop_31_50', self.trailing_stop_31_50)
                self.trailing_stop_above_50 = config.get('trailing_stop_above_50', self.trailing_stop_above_50)
                self.alert_price_above = config.get('alert_price_above', self.alert_price_above)
                self.alert_price_below = config.get('alert_price_below', self.alert_price_below)
                self.default_usd_amount = config.get('default_usd_amount', self.default_usd_amount)
                self.rsi_period = config.get('rsi_period', self.rsi_period)
                self.use_sma = config.get('use_sma', self.use_sma)
                self.use_rsi = config.get('use_rsi', self.use_rsi)
                self.use_volume = config.get('use_volume', self.use_volume)
                self.granularity = config.get('granularity', self.granularity)
                self.selected_symbol = config.get('selected_symbol', self.selected_symbol)
                self.auto_open_new_position = config.get('auto_open_new_position', self.auto_open_new_position)
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
                'trailing_stop_16_30': self.trailing_stop_16_30,
                'trailing_stop_31_50': self.trailing_stop_31_50,
                'trailing_stop_above_50': self.trailing_stop_above_50,
                'alert_price_above': self.alert_price_above,
                'alert_price_below': self.alert_price_below,
                'default_usd_amount': self.default_usd_amount,
                'rsi_period': self.rsi_period,
                'use_sma': self.use_sma,
                'use_rsi': self.use_rsi,
                'use_volume': self.use_volume,
                'granularity': self.granularity,
                'selected_symbol': self.selected_symbol,
                'auto_open_new_position': self.auto_open_new_position
            }
            with open('configurations.json', 'w') as f:
                json.dump(config, f)
            print("Configurations saved successfully.")
        except Exception as e:
            print(f"Error saving configurations: {e}")

    def load_position_trackers(self):
        try:
            with open('position_trackers.json', 'r') as f:
                self.position_trackers = json.load(f)
            print("Position trackers loaded successfully.")
        except FileNotFoundError:
            print("Position trackers file not found. Starting fresh.")
            self.position_trackers = {}
        except Exception as e:
            print(f"Error loading position trackers: {e}")
            self.position_trackers = {}

    def save_position_trackers(self):
        try:
            with open('position_trackers.json', 'w') as f:
                json.dump(self.position_trackers, f)
            print("Position trackers saved successfully.")
        except Exception as e:
            print(f"Error saving position trackers: {e}")

    def update_balance_label(self):
        """Updates the balance label with the current available balance."""
        account_info = get_margin_account_balance(self.selected_symbol)
        if account_info:
            base_asset = account_info['baseAsset']
            quote_asset = account_info['quoteAsset']
            # Por simplicidade, vamos mostrar o saldo livre de USDT (quote asset)
            free_usdt = float(quote_asset['free'])
            borrowed_usdt = float(quote_asset['borrowed'])
            net_usdt = float(quote_asset['netAsset'])
            self.balance_label.setText(f"${free_usdt:.2f}")
            if free_usdt < 0:
                self.balance_label.setStyleSheet("color: #ff3333;")
            else:
                self.balance_label.setStyleSheet("color: #00ff00;")
        else:
            self.balance_label.setText("Saldo: N/A")


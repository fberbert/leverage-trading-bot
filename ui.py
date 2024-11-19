# ui.py

import time
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QCheckBox,
    QComboBox, QSpacerItem, QSizePolicy
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
    list_usdt_contracts
)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Leverage Trading Bot")
        self.setGeometry(0, 0, 1280, 600)
        self.last_price = 0
        self.last_updated_price_time = 0
        self.alert_price_above = 0
        self.alert_price_below = 0
        self.first_run = True
        self.alert_above_triggered = False
        self.alert_below_triggered = False
        self.pair_labels = {
            "XBTUSDTM": "BTC/USDT"
        }
        self.position_trackers = {}  # Dictionary to track positions for auto-closing
        self.auto_open_new_position = True  # Flag to open new positions automatically
        self.default_leverage = 20  # Default leverage value
        self.default_stop_loss = -20  # Default stop loss value
        # New variables for trailing stops
        self.trailing_stop_16_30 = 5  # Trailing stop between 16%-30%
        self.trailing_stop_31_50 = 8  # Trailing stop between 31%-50%
        self.trailing_stop_above_50 = 10  # Trailing stop above 50%
        self.monitoring_signal = False  # Flag to indicate if we are monitoring signals
        self.decision_value = "wait"
        self.sma_value = "SMA: 0.00"
        self.rsi_value = "RSI: 0.00"
        self.volume_value = "Volume: 0.00"
        self.default_contract_qtd = 1  # New variable for default contract quantity
        self.rsi_period = 14  # Default RSI value
        self.use_sma = True  # Default to use SMA
        self.use_rsi = True
        self.use_volume = False
        self.save_config_button = QPushButton("Salvar configurações")

        # Get list of USDT contracts
        self.usdt_contracts = list_usdt_contracts()
        self.contract_options = [(contract['symbol'], contract['baseCurrency']) for contract in self.usdt_contracts]

        # Initialize selected symbol
        self.selected_symbol = 'XBTUSDTM'  # Default symbol

        self.initUI()
        self.sound_player = SoundPlayer("correct-chime.mp3")  # Initialize sound player
        self.sound_closed_position_win = SoundPlayer("closed-position-win.mp3")
        self.sound_closed_position_lose = SoundPlayer("closed-position-lose.mp3")
        self.sound_price_above = SoundPlayer("price-above.mp3")
        self.sound_price_below = SoundPlayer("price-below.mp3")
        self.sound_open_position = SoundPlayer("coin.mp3")

        # Start WebSocket client in a separate thread
        self.price_ws_client = PriceWebsocketClient(self.selected_symbol)
        self.price_ws_client.price_updated.connect(self.update_price_label)
        self.price_ws_client.start()
        self.sound_player.play_sound()

    def initUI(self):
        # Apply dark theme
        self.setStyleSheet("""
            QWidget {
                background-color: black;
                color: white;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #444;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: white;
                gridline-color: #444;
                margin-top: 20px;
            }
            QHeaderView::section {
                background-color: #2e2e2e;
                color: white;
            }
            QTableWidget QTableCornerButton::section {
                background-color: #2e2e2e;
            }
            QLabel#priceLabel {
                font-size: 24px;
            }
            QLabel#highLowLabel {
                font-size: 14px;
            }
            QPushButton {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QCheckBox::indicator {
                border: 1px solid #5a5a5a;
                background: none;
            }
            QCheckBox::indicator:checked {
                background-color: #55ff55;
            }
            QRadioButton::indicator {
                border: 1px solid #5a5a5a;
                border-radius: 6px;
                background: none;
            }
            QRadioButton::indicator:checked {
                background-color: #a1a1a1;
            }
        """)

        # Create layouts
        main_layout = QVBoxLayout()

        # Layout for price and High/Low labels
        price_layout = QHBoxLayout()

        # Price label
        self.price_label = QLabel("")
        self.price_label.setObjectName("priceLabel")
        self.price_label.setFont(QFont("Arial", 20))
        self.price_label.setAlignment(Qt.AlignCenter)
        price_layout.addWidget(self.price_label)

        # Layout for High and Low
        right_layout = QHBoxLayout()
        high_low_layout = QVBoxLayout()
        high_low_layout.setContentsMargins(10, 0, 0, 0)

        self.high_low_period_label = QLabel("Última hora:")
        self.high_low_period_label.setFont(QFont("Arial", 8))
        self.high_low_period_label.setStyleSheet("color: #aaa;")
        self.high_low_period_label.setAlignment(Qt.AlignRight)
        self.high_low_period_label.setFixedWidth(100)
        right_layout.addWidget(self.high_low_period_label, alignment=Qt.AlignRight)

        # High label
        self.high_label = QLabel("High: $0.00")
        self.high_label.setObjectName("highLowLabel")
        self.high_label.setFont(QFont("Arial", 14))
        self.high_label.setAlignment(Qt.AlignRight)
        self.high_label.setStyleSheet("color: green;")
        high_low_layout.addWidget(self.high_label, alignment=Qt.AlignLeft)

        # Low label
        self.low_label = QLabel("Low: $0.00")
        self.low_label.setObjectName("highLowLabel")
        self.low_label.setFont(QFont("Arial", 14))
        self.low_label.setAlignment(Qt.AlignRight)
        self.low_label.setStyleSheet("color: red;")
        high_low_layout.addWidget(self.low_label, alignment=Qt.AlignLeft)

        right_layout.addLayout(high_low_layout)

        # Add right layout to price layout
        price_layout.addLayout(right_layout)

        # Add price layout to main layout
        main_layout.addLayout(price_layout)

        # Alert message label (initially hidden)
        self.alert_message_label = QLabel("")
        self.alert_message_label.setFont(QFont("Arial", 12))
        self.alert_message_label.setAlignment(Qt.AlignCenter)
        self.alert_message_label.setStyleSheet("color: gold;")
        self.alert_message_label.hide()
        main_layout.addWidget(self.alert_message_label)

        # Closed positions label
        self.closed_positions_label = QLabel("")
        self.closed_positions_label.setFont(QFont("Arial", 12))
        self.closed_positions_label.setAlignment(Qt.AlignCenter)
        self.closed_positions_label.setStyleSheet("color: gold;")
        self.closed_positions_label.hide()
        main_layout.addWidget(self.closed_positions_label)

        # Layout for configurable inputs
        config_hbox = QHBoxLayout()
        config_hbox.setContentsMargins(20, 20, 20, 20)
        config_left_layout = QFormLayout()
        config_right_layout = QFormLayout()

        # Pair selection
        pair_label = QLabel("Select Pair:")
        pair_label.setFont(QFont("Arial", 12))
        self.pair_combo = QComboBox()
        self.pair_combo.setFont(QFont("Arial", 12))
        self.pair_combo.setFixedWidth(200)
        for symbol, name in self.contract_options:
            self.pair_combo.addItem(f"{name} ({symbol})", symbol)
        # Set default selected symbol
        index = self.pair_combo.findData(self.selected_symbol)
        if index != -1:
            self.pair_combo.setCurrentIndex(index)
        self.pair_combo.currentIndexChanged.connect(self.on_pair_changed)
        config_left_layout.addRow(pair_label, self.pair_combo)

        # Input for leverage
        leverage_label = QLabel("Leverage:")
        leverage_label.setFont(QFont("Arial", 12))
        self.leverage_input = QLineEdit(str(self.default_leverage))
        self.leverage_input.setFont(QFont("Arial", 12))
        self.leverage_input.setFixedWidth(50)
        config_left_layout.addRow(leverage_label, self.leverage_input)

        # Input for default_stop_loss
        default_stop_loss_label = QLabel("Default Stop Loss (%):")
        default_stop_loss_label.setFont(QFont("Arial", 12))
        self.default_stop_loss_input = QLineEdit(str(self.default_stop_loss))
        self.default_stop_loss_input.setFont(QFont("Arial", 12))
        self.default_stop_loss_input.setFixedWidth(50)
        config_left_layout.addRow(default_stop_loss_label, self.default_stop_loss_input)

        # Inputs for the new trailing stops
        trailing_stop_16_30_label = QLabel("Trailing stop 16%-30%:")
        trailing_stop_16_30_label.setFont(QFont("Arial", 12))
        self.trailing_stop_16_30_input = QLineEdit(str(self.trailing_stop_16_30))
        self.trailing_stop_16_30_input.setFont(QFont("Arial", 12))
        self.trailing_stop_16_30_input.setFixedWidth(50)
        config_left_layout.addRow(trailing_stop_16_30_label, self.trailing_stop_16_30_input)

        trailing_stop_31_50_label = QLabel("Trailing stop 31%-50%:")
        trailing_stop_31_50_label.setFont(QFont("Arial", 12))
        self.trailing_stop_31_50_input = QLineEdit(str(self.trailing_stop_31_50))
        self.trailing_stop_31_50_input.setFont(QFont("Arial", 12))
        self.trailing_stop_31_50_input.setFixedWidth(50)
        config_left_layout.addRow(trailing_stop_31_50_label, self.trailing_stop_31_50_input)

        trailing_stop_above_50_label = QLabel("Trailing stop above 50%:")
        trailing_stop_above_50_label.setFont(QFont("Arial", 12))
        self.trailing_stop_above_50_input = QLineEdit(str(self.trailing_stop_above_50))
        self.trailing_stop_above_50_input.setFont(QFont("Arial", 12))
        self.trailing_stop_above_50_input.setFixedWidth(50)
        config_left_layout.addRow(trailing_stop_above_50_label, self.trailing_stop_above_50_input)

        # Right layout

        # Alert above
        alert_above_label = QLabel("Price Alert Above:")
        alert_above_label.setFont(QFont("Arial", 12))
        self.alert_entry_above = QLineEdit("0")
        self.alert_entry_above.setFont(QFont("Arial", 12))
        self.alert_entry_above.setFixedWidth(100)
        config_right_layout.addRow(alert_above_label, self.alert_entry_above)

        # Alert below
        alert_below_label = QLabel("Price Alert Below:")
        alert_below_label.setFont(QFont("Arial", 12))
        self.alert_entry_below = QLineEdit("0")
        self.alert_entry_below.setFont(QFont("Arial", 12))
        self.alert_entry_below.setFixedWidth(100)
        config_right_layout.addRow(alert_below_label, self.alert_entry_below)

        # Input for default_contract_qtd
        default_contract_qtd_label = QLabel("Default Contract Quantity:")
        default_contract_qtd_label.setFont(QFont("Arial", 12))
        self.default_contract_qtd_input = QLineEdit(str(self.default_contract_qtd))
        self.default_contract_qtd_input.setFont(QFont("Arial", 12))
        self.default_contract_qtd_input.setFixedWidth(100)
        config_right_layout.addRow(default_contract_qtd_label, self.default_contract_qtd_input)

        # Input for RSI period
        rsi_label = QLabel("RSI:")
        rsi_label.setFont(QFont("Arial", 12))
        self.rsi_period_input = QLineEdit(str(self.rsi_period))
        self.rsi_period_input.setFont(QFont("Arial", 12))
        self.rsi_period_input.setFixedWidth(100)
        config_right_layout.addRow(rsi_label, self.rsi_period_input)

        # Add layouts to config_hbox
        config_hbox.addLayout(config_left_layout)
        config_hbox.addLayout(config_right_layout)

        # Add the layout to the main layout
        main_layout.addLayout(config_hbox)

        # save_config_button = QPushButton("Salvar configurações")
        self.save_config_button.setFixedWidth(150)
        self.save_config_button.clicked.connect(self.check_parameters_changes)

        # Create a horizontal layout to add margin to the button
        self.save_config_button_layout = QHBoxLayout()
        self.save_config_button_layout.setContentsMargins(20, 0, 0, 0)
        self.save_config_button_layout.addWidget(self.save_config_button)

        main_layout.addLayout(self.save_config_button_layout)

        # Checkbox to automatically open new positions
        self.auto_open_checkbox = QCheckBox("Abrir nova posição automaticamente")
        self.auto_open_checkbox.setFont(QFont("Arial", 12))
        self.auto_open_checkbox.setChecked(True)
        self.auto_open_checkbox.stateChanged.connect(lambda state: self.toggle_auto_open(state, self.auto_open_checkbox))

        self.auto_open_checkbox.setStyleSheet("QCheckBox { color: white; margin-left: 20px;}")
        main_layout.addWidget(self.auto_open_checkbox)


        # SMA, RSI, and Volume
        indicator_layout = QHBoxLayout()
        indicator_layout.setContentsMargins(150, 20, 150, 0)

        self.use_sma_checkbox = QCheckBox()
        self.use_sma_checkbox.setChecked(self.use_sma)
        self.use_sma_checkbox.setText(self.sma_value)
        self.use_sma_checkbox.setFont(QFont("Arial", 12))
        self.use_sma_checkbox.stateChanged.connect(lambda state: self.toggle_auto_open(state, self.use_sma_checkbox))
        self.use_sma_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")

        indicator_layout.addWidget(self.use_sma_checkbox)

        self.use_rsi_checkbox = QCheckBox()
        self.use_rsi_checkbox.setChecked(self.use_rsi)
        self.use_rsi_checkbox.setText(self.rsi_value)
        self.use_rsi_checkbox.setFont(QFont("Arial", 12))
        self.use_rsi_checkbox.stateChanged.connect(lambda state: self.toggle_auto_open(state, self.use_rsi_checkbox))
        self.use_rsi_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")

        indicator_layout.addWidget(self.use_rsi_checkbox)

        self.use_volume_checkbox = QCheckBox()
        self.use_volume_checkbox.setChecked(self.use_volume)
        self.use_volume_checkbox.setText(self.volume_value)
        self.use_volume_checkbox.setFont(QFont("Arial", 12))
        self.use_volume_checkbox.stateChanged.connect(lambda state: self.toggle_auto_open(state, self.use_volume_checkbox))
        self.use_volume_checkbox.setStyleSheet("QCheckBox { color: white; margin: 20px 0; min-width: 300px;}")

        indicator_layout.addStretch()
        indicator_layout.addWidget(self.use_volume_checkbox)
        indicator_layout.addStretch()

        main_layout.addLayout(indicator_layout)

        # Positions table
        self.positions_table = QTableWidget()
        self.positions_table.setRowCount(0)
        columns = ["Contract", "Amount", "Entry/Mark Price", "Liq Price", "Margin",
                   "Unrealised PnL", "Realised PnL", "Trigger", "Actions"]
        self.positions_table.setColumnCount(len(columns))
        self.positions_table.setHorizontalHeaderLabels(columns)
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Set specific column widths
        self.positions_table.setColumnWidth(0, 230)
        self.positions_table.setColumnWidth(1, 100)
        self.positions_table.setColumnWidth(2, 150)
        self.positions_table.setColumnWidth(3, 80)
        self.positions_table.setColumnWidth(4, 100)
        self.positions_table.setColumnWidth(5, 150)
        self.positions_table.setColumnWidth(6, 150)
        self.positions_table.setColumnWidth(7, 80)
        self.positions_table.setColumnWidth(8, 120)

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

    def toggle_auto_open(self, state, checkbox=None):
        """
        Updates the corresponding flags based on the checkbox state.
        :param state: The state of the checkbox (Checked/Unchecked).
        :param checkbox: The checkbox widget that triggered the state change.
        """
        if checkbox:
            if checkbox == self.use_sma_checkbox:
                self.use_sma = state == Qt.Checked
            elif checkbox == self.use_rsi_checkbox:
                self.use_rsi = state == Qt.Checked
            elif checkbox == self.use_volume_checkbox:
                self.use_volume = state == Qt.Checked
        else:
            self.auto_open_new_position = state == Qt.Checked

    def reset_alerts(self):
        self.alert_above_triggered = False
        self.alert_below_triggered = False

    def check_parameters_changes(self):
        """Updates variables based on inputs."""
        try:
            new_leverage = int(self.leverage_input.text())
            new_default_stop_loss = int(self.default_stop_loss_input.text())
            new_trailing_stop_16_30 = int(self.trailing_stop_16_30_input.text())
            new_trailing_stop_31_50 = int(self.trailing_stop_31_50_input.text())
            new_trailing_stop_above_50 = int(self.trailing_stop_above_50_input.text())
            new_alert_price_above = float(self.alert_entry_above.text())
            new_alert_price_below = float(self.alert_entry_below.text())
            new_default_contract_qtd = int(self.default_contract_qtd_input.text())
            new_rsi_period = int(self.rsi_period_input.text())

            if new_leverage != self.default_leverage:
                self.default_leverage = new_leverage

            if new_default_stop_loss != self.default_stop_loss:
                self.default_stop_loss = new_default_stop_loss

            if new_trailing_stop_16_30 != self.trailing_stop_16_30:
                self.trailing_stop_16_30 = new_trailing_stop_16_30

            if new_trailing_stop_31_50 != self.trailing_stop_31_50:
                self.trailing_stop_31_50 = new_trailing_stop_31_50

            if new_trailing_stop_above_50 != self.trailing_stop_above_50:
                self.trailing_stop_above_50 = new_trailing_stop_above_50

            if new_alert_price_above != self.alert_price_above:
                self.alert_price_above = new_alert_price_above
                self.reset_alerts()

            if new_alert_price_below != self.alert_price_below:
                self.alert_price_below = new_alert_price_below
                self.reset_alerts()

            if new_default_contract_qtd != self.default_contract_qtd:
                self.default_contract_qtd = new_default_contract_qtd

            if new_rsi_period != self.rsi_period:
                self.rsi_period = new_rsi_period

           # Indicador visual no botão
            self.save_config_button.setStyleSheet("background-color: #00ff00; color: black;")
            self.save_config_button.setText("Salvo com sucesso!")
            QTimer.singleShot(500, lambda: self.save_config_button.setStyleSheet("background-color: #333; color: white;"))
            QTimer.singleShot(500, lambda: self.save_config_button.setText("Salvar configurações"))

        except ValueError:
            pass

    def fetch_open_positions(self):
        data = fetch_open_positions()
        self.update_positions_display(data)
        if not data and self.auto_open_new_position and not self.monitoring_signal:
            self.open_new_position_after_close(None)

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
            row_position = self.positions_table.rowCount()
            self.positions_table.insertRow(row_position)

            # Calculations and data preparations
            avg_entry_price = position.get('avgEntryPrice', 0)
            real_leverage = position.get('realLeverage', 0)
            maint_margin = position.get('maintMargin', 0)
            if avg_entry_price != 0:
                qtd = (real_leverage * maint_margin) / avg_entry_price
            else:
                qtd = 0

            entry_mark_price = f"{avg_entry_price} / {position.get('markPrice', 0)}"

            pos_margin = position.get('posMargin', 0)
            unrealised_pnl_value = position.get('unrealisedPnl', 0)
            if pos_margin != 0:
                pnl_percent = ((unrealised_pnl_value / pos_margin) * 100)
            else:
                pnl_percent = 0.0  # Avoid division by zero

            unrealised_pnl = f"{unrealised_pnl_value:.2f} USDT ({pnl_percent:.2f}%)"

            contract_type = self.pair_labels.get(position.get('symbol'), position.get('symbol'))
            current_qty = position.get('currentQty', 0)
            if current_qty < 0:
                position_direction = "SHORT"
                direction_color = 'red'
                qtd = -qtd
            else:
                position_direction = "LONG"
                direction_color = 'green'

            leverage_text = f"- {int(real_leverage)}x"

            # Custom widget for the contract
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

            amount_item = QTableWidgetItem(f"{qtd:.5f} {position.get('symbol', '')}")
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
            if unrealised_pnl_value > 0:
                unrealised_pnl_item.setForeground(QBrush(QColor('green')))
            else:
                unrealised_pnl_item.setForeground(QBrush(QColor('red')))

            realised_pnl_value = position.get('realisedPnl', 0)
            realised_pnl_item = QTableWidgetItem(f"{realised_pnl_value:.2f} USDT")
            realised_pnl_item.setTextAlignment(Qt.AlignCenter)
            if realised_pnl_value > 0:
                realised_pnl_item.setForeground(QBrush(QColor('green')))
            else:
                realised_pnl_item.setForeground(QBrush(QColor('red')))

            # Get stop loss from tracker
            position_id = position.get('id')
            stop_loss_percent = self.position_trackers.get(position_id, {}).get('trigger_stop_loss_percent', self.default_stop_loss)
            stop_loss_item = QTableWidgetItem(f"{stop_loss_percent:.2f}%")
            stop_loss_item.setTextAlignment(Qt.AlignCenter)
            if stop_loss_percent < 0:
                stop_loss_item.setForeground(QBrush(QColor('red')))
            else:
                stop_loss_item.setForeground(QBrush(QColor('green')))

            # Add items to the table
            self.positions_table.setCellWidget(row_position, 0, contract_widget)
            self.positions_table.setItem(row_position, 1, amount_item)
            self.positions_table.setItem(row_position, 2, entry_mark_item)
            self.positions_table.setItem(row_position, 3, liq_price_item)
            self.positions_table.setItem(row_position, 4, margin_item)
            self.positions_table.setItem(row_position, 5, unrealised_pnl_item)
            self.positions_table.setItem(row_position, 6, realised_pnl_item)
            self.positions_table.setItem(row_position, 7, stop_loss_item)

            # Action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(0)
            market_button = QPushButton("Market")
            market_button.clicked.connect(lambda checked, pos=position: self.close_position_market(pos))
            actions_layout.addWidget(market_button)
            actions_widget.setLayout(actions_layout)
            self.positions_table.setCellWidget(row_position, 8, actions_widget)

            # Tracking positions for auto-closing
            position_id = position['id']
            current_positions_ids.add(position_id)
            if position_id not in self.position_trackers:
                # Initialize tracker for new position
                self.position_trackers[position_id] = {
                    'position': position,
                    'max_pnl_percent': pnl_percent if pnl_percent >= 10 else 0,
                    'trigger_stop_loss_percent': self.default_stop_loss
                }
            else:
                # Update existing tracker
                tracker = self.position_trackers[position_id]
                tracker['position'] = position  # Update position data

        # Remove trackers for closed positions
        for pid in list(self.position_trackers.keys()):
            if pid not in current_positions_ids:
                del self.position_trackers[pid]

    def check_auto_close_positions(self):
        """Automatically closes positions based on pnl_percent."""
        positions_to_delete = []

        for tracker in self.position_trackers.values():
            position = tracker['position']
            position_id = position['id']
            pos_margin = position.get('posMargin', 1)
            unrealised_pnl = position.get('unrealisedPnl', 0)

            # Avoid division by zero
            if pos_margin == 0:
                continue

            # Calculate profit/loss percentage
            pnl_percent = (unrealised_pnl / pos_margin) * 100

            # Determine the appropriate stop loss based on new rules
            if 4.5 <= pnl_percent <= 6.9:
                calculated_stop_loss = pnl_percent - 3
            if 7 <= pnl_percent <= 9:
                calculated_stop_loss = pnl_percent - 5
            elif 10 <= pnl_percent <= 30:
                calculated_stop_loss = pnl_percent - self.trailing_stop_16_30
            elif 31 <= pnl_percent <= 50:
                calculated_stop_loss = pnl_percent - self.trailing_stop_31_50
            elif pnl_percent > 50:
                calculated_stop_loss = pnl_percent - self.trailing_stop_above_50
            else:
                calculated_stop_loss = self.default_stop_loss  # Use default stop loss

            # Update stop loss in tracker if greater than current
            if ('trigger_stop_loss_percent' not in tracker or calculated_stop_loss > tracker['trigger_stop_loss_percent']) or (pnl_percent < 0 and calculated_stop_loss < tracker['trigger_stop_loss_percent']):
                tracker['trigger_stop_loss_percent'] = calculated_stop_loss
                print('Updated trigger_stop_loss_percent:', tracker['trigger_stop_loss_percent'])

            # Update the maximum profit percentage achieved
            if pnl_percent > tracker.get('max_pnl_percent', 0):
                tracker['max_pnl_percent'] = pnl_percent
                print('Updated max_pnl_percent:', tracker['max_pnl_percent'])
            elif pnl_percent < 0 and pnl_percent < tracker.get('max_pnl_percent', 0):
                tracker['max_pnl_percent'] = pnl_percent
                print('Updated max_pnl_percent:', tracker['max_pnl_percent'])

            # Check if profit percentage has fallen below configured stop loss
            if pnl_percent <= tracker['trigger_stop_loss_percent']:
                if pnl_percent >= 0:
                    # Close position with profit
                    self.close_position_market(position)
                    print('position:', position)
                    message = (
                        f"{position['symbol']} - "
                        f"Taxas: {position['realLeverage']*2*0.06:.2f}% - "
                        f"LUCRO de {pnl_percent:.2f}% -> {pnl_percent - (position['realLeverage']*2*0.06):.2f}% "
                    )
                    self.show_alert_message(message)
                    self.sound_closed_position_win.play_sound()
                else:
                    # Close position with loss
                    self.close_position_market(position)
                    message = (
                        f"{position['symbol']} - "
                        f"Taxas: {position['realLeverage']*2*0.06:.2f}% - "
                        f"Prejuízo de {pnl_percent:.2f}% -> {pnl_percent - (position['realLeverage']*2*0.06):.2f}% "
                    )
                    self.show_closed_positions_message(message)
                    self.sound_closed_position_lose.play_sound()

                # If the option is checked, open a new position
                if self.auto_open_new_position:
                    self.open_new_position_after_close(position)

                # Mark for removal
                positions_to_delete.append(position_id)
                continue

        # Remove trackers after iteration
        for pid in positions_to_delete:
            if pid in self.position_trackers:
                del self.position_trackers[pid]

    def open_new_position_after_close(self, closed_position):
        """Starts monitoring signals to open a new position."""
        symbol = self.selected_symbol
        leverage = self.default_leverage  # Default leverage
        size = self.default_contract_qtd  # Use default quantity

        # Start monitoring signals
        print("Iniciando monitoramento de sinais para nova posição...")
        self.monitor_trade_signals(symbol, size, leverage)

    def monitor_trade_signals(self, symbol, size, leverage):
        """Monitors trade signals and opens a new position when a signal is identified."""
        if self.monitoring_signal:
            # Already monitoring, avoid duplicate calls
            return
        self.monitoring_signal = True

        def check_signal():
            side = self.decision_value
            if side in ['buy', 'sell']:
                print(f"Sinal identificado: {side.upper()}. Abrindo nova posição.")
                open_new_position_market(symbol, side, size, leverage)
                self.sound_open_position.play_sound()
                self.monitoring_signal = False  # Stop monitoring
            else:
                # Continue monitoring
                QTimer.singleShot(5000, check_signal)  # Check again in 5 seconds

        # Start the first check immediately
        check_signal()

    def check_decision_indicators(self):
        decisions = decide_trade_direction(self.selected_symbol, self.rsi_period, self.use_sma, self.use_rsi, self.use_volume)
        self.decision_value = decisions['decision']
        self.sma_value = f"SMA: {decisions['sma']}"
        self.rsi_value = f"RSI: {decisions['rsi']}"
        self.volume_value = f"Volume: {decisions['volume']}"
        self.use_sma_checkbox.setText(self.sma_value)
        self.use_rsi_checkbox.setText(self.rsi_value)
        self.use_volume_checkbox.setText(self.volume_value)

    def show_alert_message(self, message):
        """Displays an alert message and plays a sound."""
        self.alert_message_label.setText(message)
        self.alert_message_label.show()
        if 'acima' in message:
            self.sound_price_above.play_sound()
        else:
            self.sound_price_below.play_sound()

    def show_closed_positions_message(self, message):
        """Displays a message for closed positions."""
        self.closed_positions_label.setText(message)
        self.closed_positions_label.show()

    def close_position_market(self, position):
        close_position_market(position)

    def update_price_label(self, price):
        formatted_price = f"{self.selected_symbol} ${price:,.2f}"
        self.price_label.setText(formatted_price)

        current_time = time.time()
        time_since_last_update = current_time - self.last_updated_price_time

        if time_since_last_update >= 1:
            if price > self.last_price:
                self.price_label.setStyleSheet("color: #00ff00;")
            elif price < self.last_price:
                self.price_label.setStyleSheet("color: #ff3333;")
            self.last_updated_price_time = current_time

        # Check for alerts only if the alert prices are greater than 0
        if self.alert_price_above > 0 and price >= self.alert_price_above:
            if not self.alert_above_triggered:
                self.alert_above_triggered = True
                print("ALERTA: Preço acima do valor definido")
                self.sound_price_above.play_sound()
                # Set alert message
                self.alert_message_label.setText(f"Alerta: Preço acima de {self.alert_price_above}")
                self.alert_message_label.show()
        else:
            if self.alert_above_triggered:
                self.alert_message_label.hide()
            self.alert_above_triggered = False

        if self.alert_price_below > 0 and price <= self.alert_price_below:
            if not self.alert_below_triggered:
                self.alert_below_triggered = True
                print("ALERTA: Preço abaixo do valor definido")
                self.sound_price_below.play_sound()
                # Set alert message
                self.alert_message_label.setText(f"Alerta: Preço abaixo de {self.alert_price_below}")
                self.alert_message_label.show()
        else:
            if self.alert_below_triggered:
                self.alert_message_label.hide()
            self.alert_below_triggered = False
        self.last_price = price

        if self.first_run:
            self.price_alert_above = price * 1.01
            self.price_alert_below = price * 0.99
            self.alert_entry_above.setText(str(int(self.price_alert_above)))
            self.alert_entry_below.setText(str(int(self.price_alert_below)))
            self.first_run = False


    def on_pair_changed(self):
        self.selected_symbol = self.pair_combo.currentData()
        print(f"Symbol changed to {self.selected_symbol}")
        self.restart_price_websocket()
        self.fetch_high_low_prices()
        self.reset_alerts()

    def restart_price_websocket(self):
        # Stop the current WebSocket client
        self.price_ws_client.stop()
        self.price_ws_client.wait()
        # Start a new WebSocket client with the new symbol
        self.price_ws_client = PriceWebsocketClient(self.selected_symbol)
        self.price_ws_client.price_updated.connect(self.update_price_label)
        self.price_ws_client.start()


#!/usr/bin/env python3
"""
tk-bitcoin-monitor.py
Real-time Bitcoin Price Monitor with Sound Alert.

Requirements:
- Python 3
- tkinter
- pygame

To install requirements, run:

$ pip install tkinter pygame

Source: Binance API

Author: Fábio Berbert de Paula
Repository: https://github.com/fberbert/tk-bitcoin
"""

import urllib.request
import json
import os
import tkinter as tk
import pygame

def get_btc_usd_price():
    """Fetches the latest Bitcoin price in USD from the Binance API."""
    # api_url = 'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT'

    """Fetches the latest Bitcoin price in USD from the Kucoin API."""
    api_url = 'https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT'

    try:
        with urllib.request.urlopen(api_url) as url:
            data = json.loads(url.read().decode())
            price = float(data['data']['price'])
            return price
    except Exception as e:
        price_label.config(text=f"Error: {e}")
        return None

def update_price(event=None):
    """Updates the displayed price and checks if the alert threshold has been reached."""
    global last_price
    global direction

    price = get_btc_usd_price()
    alert_price = float(alert_entry.get())

    if price:
        formatted_price = f"${price:,.2f}"
        price_label.config(text=formatted_price)

        # Check if the price reached the alert level
        try:
            if price >= last_price:
                price_label.config(fg="green")
            elif price == alert_price:
                price_label.config(fg="yellow")
            else:
                price_label.config(fg="red")
        except ValueError:
            pass  # Ignore if alert entry is not a valid value

        # Define alert direction
        if event == "Alert":
            direction = "up" if price >= alert_price else "down"

        # Handle alert flashing and sound playback
        if direction == "up" and price <= alert_price:
            flash_label("green")
            play_sound()
            direction = ""
        elif direction == "down" and price >= alert_price:
            flash_label("red")
            play_sound()
            direction = ""

        last_price = price
    root.after(5000, update_price)  # Refresh every 5 seconds

def flash_label(color):
    """Flashes the price label in the specified color."""
    for i in range(5):
        price_label.after(1000 * i, lambda c="white" if i % 2 else color: price_label.config(fg=c))

def play_sound():
    """Plays an alert sound."""
    pygame.mixer.init()
    pygame.mixer.music.load(sound_alert)
    pygame.mixer.music.play()

def close_window(event=None):
    """Closes the window."""
    root.destroy()

# Window configuration
root = tk.Tk()
# root.overrideredirect(True)  # Removes window borders and title bar
root.geometry("100x60+0+0") # Window size
root.attributes("-topmost", True)  # Keeps the window on top
root.wm_attributes("-type", "splash")  # Hides the window from the taskbar
root.bind('<Escape>', close_window)  # Shortcut to close the window


# Background and font colors
root.configure(bg="black")
# root.wm_attributes("-alpha", 0.95)  # Ajusta a transparência (se desejado)
# root.wm_title("Bitcoin Monitor")  # Define o título temporariamente, mesmo que não seja visível
# root.resizable(False, False)  # Impede redimensionamento da janela

price_label = tk.Label(root, font=("Arial", 12), fg="white", bg="black")
price_label.pack(expand=True)

# Alert price entry
alert_entry = tk.Entry(root, font=("Arial", 10), bg="gray", fg="black")
alert_entry.pack()
alert_entry.insert(0, "0")  # Default value
alert_entry.bind("<Return>", lambda event: update_price(event="Alert"))

# sound alert is in the same folder as the script
sound_alert = os.path.join(os.path.dirname(__file__), "correct-chime.mp3")

# Start price update loop
last_price = 0
direction = ""
update_price()

# Start the GUI loop
root.mainloop()


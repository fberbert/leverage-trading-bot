#!/usr/bin/env python3
"""
tk-bitcoin-monitor.py
Real-time Bitcoin Price Monitor with Sound Alert using WebSockets.

Requirements:
- Python 3
- tkinter
- pygame
- kucoin-python
- python-dotenv

To install requirements, run:

$ pip install pygame kucoin-python python-dotenv

Source: KuCoin API WebSocket
"""

import os
import tkinter as tk
import pygame
import asyncio
import socket
import threading
from dotenv import load_dotenv
from kucoin.client import WsToken
from kucoin.ws_client import KucoinWsClient

# Load API keys from .env file
load_dotenv()
API_KEY = os.getenv("KUCOIN_API_KEY")
API_SECRET = os.getenv("KUCOIN_API_SECRET")
API_PASSWORD = os.getenv("KUCOIN_API_PASSWORD")

# Sound alert path
sound_alert = os.path.join(os.path.dirname(__file__), "correct-chime.mp3")

# Initialize Tkinter GUI
root = tk.Tk()
root.geometry("100x60+0+0")
root.attributes("-topmost", True)
root.wm_attributes("-type", "splash")
root.configure(bg="black")
root.bind('<Escape>', lambda e: root.quit())
root.bind('q', lambda e: root.quit())

price_label = tk.Label(root, font=("Arial", 12), fg="white", bg="black")
price_label.pack(expand=True)

alert_entry = tk.Entry(root, font=("Arial", 10), bg="gray", fg="black")
alert_entry.pack()
alert_entry.insert(0, "0")
alert_price = float(alert_entry.get())

last_price = 0
direction = ""

def play_sound():
    """Plays an alert sound."""
    pygame.mixer.init()
    pygame.mixer.music.load(sound_alert)
    pygame.mixer.music.play()

def flash_label(color):
    """Flashes the price label in the specified color."""
    for i in range(5):
        price_label.after(500 * i, lambda c="white" if i % 2 else color: price_label.config(fg=c))

async def handle_message(msg):
    """Handles incoming WebSocket messages and updates the price in the GUI."""
    global last_price, direction, alert_price

    if msg['topic'] == '/market/ticker:BTC-USDT':
        price = float(msg['data']['price'])
        formatted_price = f"${price:,.2f}"
        price_label.config(text=formatted_price)

        # Update alert price from entry field
        try:
            alert_price = float(alert_entry.get())
        except ValueError:
            pass

        # Change label color based on price movement
        if price > last_price:
            price_label.config(fg="green")
        elif price < last_price:
            price_label.config(fg="red")

        # Check alert conditions
        if price >= alert_price and direction != "up":
            play_sound()
            direction = "up"
        elif price <= alert_price and direction != "down":
            play_sound()
            direction = "down"

        last_price = price

async def update_price_via_websocket():
    print("Initializing WebSocket client and subscribing to BTC-USDT ticker updates.")
    """Initializes WebSocket client and subscribes to BTC-USDT ticker updates."""
    client = WsToken(key=API_KEY, secret=API_SECRET, passphrase=API_PASSWORD)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    address = ('api.kucoin.com',443)
    sock.connect(address)

    # ws_client = await KucoinWsClient.create(None, client, handle_message, private=False)
    ws_client = await KucoinWsClient.create(None, client, handle_message, private=False,sock=sock)

    print("Subscribing to BTC-USDT ticker updates.")
    await ws_client.subscribe('/market/ticker:BTC-USDT')

    while True:
        await asyncio.sleep(1)  # Keep the loop alive

def start_websocket_loop():
    """Starts the WebSocket event loop in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update_price_via_websocket())

def start_gui():
    """Starts the Tkinter main loop."""
    root.mainloop()

if __name__ == "__main__":
    # Run the WebSocket loop in a separate thread
    threading.Thread(target=start_websocket_loop, daemon=True).start()
    # Start the Tkinter GUI loop
    start_gui()


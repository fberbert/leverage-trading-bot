# tk-bitcoin-monitor.py
A real-time Bitcoin price monitor with sound alert using WebSockets.

This script fetches the latest Bitcoin price in USD from the KuCoin WebSocket API and displays it in a minimalist GUI window using Tkinter. The window also includes an input field to set a custom alert price, which, when reached, triggers a sound alert.

## Screenshot

<p align="center">
  <img src="screenshot.jpg" alt="Bitcoin Price Monitor Screenshot">
</p>

## Requirements
- Python 3.x
- `tkinter` for the GUI (comes pre-installed with Python on most platforms)
- `pygame` for sound playback
- `kucoin-python` for WebSocket connection
- `python-dotenv` for loading API credentials from `.env` file

### Install Dependencies
To install the necessary dependencies, run:
```bash
$ pip install pygame kucoin-python python-dotenv
```

## Usage

1. **Prepare API Credentials**:
    - Create a `.env` file in the project directory containing your KuCoin API credentials as follows:
      ```
      KUCOIN_API_KEY=your_api_key
      KUCOIN_API_SECRET=your_api_secret
      KUCOIN_API_PASSWORD=your_api_password
      ```
2. **Run the Script**: Execute `tk-bitcoin-monitor.py` from the terminal:
    ```bash
    $ ./tk-bitcoin-monitor.py
    ```
3. **Set an Alert Price**: Enter a Bitcoin price in the alert field. The current Bitcoin price is updated in real-time and displayed.
4. **Alert Trigger**: If the current Bitcoin price reaches or exceeds your alert price, a sound alert will be triggered.

### Controls
- **Set Alert Price**: Press **Enter** after typing a value in the alert field.
- **Close Window**: Press **Esc**.

## Configuration
- **API Source**: This script uses KuCoin’s WebSocket API to retrieve the real-time Bitcoin price in USD.
- **Sound Alert File**: Ensure that `correct-chime.mp3` is located in the same directory as the script for the sound alert feature to work.

## File Structure
```text
├── tk-bitcoin-monitor.py    # Main script file
├── correct-chime.mp3        # Sound file for the alert notification
└── .env                     # Contains KuCoin API credentials
```

## Notes
Ensure that your internet connection is active for the WebSocket connection. Adjust the alert value as desired.

## Author
Fábio Berbert de Paula  
[GitHub Repository](https://github.com/fberbert/tk-bitcoin)

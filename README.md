# Arkham Volume Pump bot

## Setup and Run Instructions

### Make sure you have installed Python

### 1. Install dependencies
> ```sh
> pip install -r requirements.txt
> ```

### 2. Create accounts.csv file
Fill in the acccounts.csv file using acccounts_sample as a guide.
API_KEY and API_SECRET you can create in Arkham Settings

### 3. Run script
> ```bash
> python main.py
> ```

### 4. Change config
In config.json you can change the settings.
- "hold_time": 5 - how long position will be held in minutes
- "spot_target_volume": 240000 - target spot volume
- "max_check_price": 3 - how much check if price is lower or higher than entry price
- "slippage": 0.003 - limit order price slippage from current price
- "is_perpetual": 1 - is perpetual or spot (1 - for perpetual, 0 for spot)
- "leverage": 8 - leverage of the perpetual (initial margin = full balance)
- "perp_target_volume": 1000000 - target volume of the perpetual

## Contact me
**[Telegram](https://t.me/chikanoff)**
**[My channel](https://t.me/chikanoFFarm)**

## Buy Me a Coffee

If you find this project useful and would like to support its development, you can buy me a coffee.

**TRC-20 Address:** `TEbvib2iYetCV8LjJpKTDvXeEiGpxXAzpo`

**EVM:** `0xeE0B3Ca740aC71B5D39eEbcE864877Db8Ce74706`

**SOL:** `4McQnDHgnzjZYoZygzXwtJW19bAqNgFKwcxVXhX3kBPx`

Thank you for your support!
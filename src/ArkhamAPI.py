import time
import hmac
import hashlib
import base64
import uuid
import requests
import json
from loguru import logger

class ArkhamAPI:
    def __init__(self, api_key, api_secret, proxies=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://arkm.com/api"
        self.proxies = proxies
        logger.add("arkham_api.log", rotation="1 day", level="INFO")  # Логирование в файл

    def generate_signature(self, method, path, body, expires):
        message = f"{self.api_key}{expires}{method}{path}{body}"
        secret = base64.b64decode(self.api_secret)
        signature = hmac.new(secret, message.encode(), hashlib.sha256).digest()
        signature_b64 = base64.b64encode(signature).decode()
        logger.debug(f"Generated signature for {path}: {signature_b64}")
        return signature_b64

    def get_market_price(self, symbol):
        path = f"/public/ticker?symbol={symbol}"
        url = f"{self.base_url}{path}"
        method = "GET"
        expires = str(int(time.time() * 1000000) + 300000000)
        signature = self.generate_signature(method, path, "", expires)

        headers = {
            "Arkham-Api-Key": self.api_key,
            "Arkham-Expires": expires,
            "Arkham-Signature": signature
        }

        logger.info(f"Fetching market price for {symbol}...")
        response = requests.get(url, headers=headers, proxies=self.proxies)
        if response.status_code == 200:
            data = response.json()
            price = float(data['price']) if 'price' in data else None
            logger.info(f"Market price for {symbol}: {price}")
            return price
        else:
            logger.error(f"Error fetching price for {symbol}: {response.status_code} - {response.text}")
            return None

    def get_balance_for_symbol(self, symbol):
        """Получение баланса для конкретного символа."""
        path = "/account/balances"
        url = f"{self.base_url}{path}"
        method = "GET"
        expires = str(int(time.time() * 1000000) + 300000000)
        signature = self.generate_signature(method, path, "", expires)

        headers = {
            "Arkham-Api-Key": self.api_key,
            "Arkham-Expires": expires,
            "Arkham-Signature": signature
        }

        logger.info(f"Fetching balance for {symbol}...")
        response = requests.get(url, headers=headers, proxies=self.proxies)
        
        if response.status_code == 200:
            balance_data = response.json()
            for item in balance_data:
                if item["symbol"] == symbol:
                    free_balance = float(item["free"])
                    logger.info(f"Balance for {symbol}: {free_balance}")
                    return free_balance
            logger.error(f"Symbol {symbol} not found in balance data.")
            return None
        else:
            logger.error(f"Error fetching balance for {symbol}: {response.status_code} - {response.text}")
            return None

    def create_order(self, price, size, side, symbol, subaccount_id=0, post_only=False):
        path = "/orders/new"
        url = f"{self.base_url}{path}"
        method = "POST"
        client_order_id = str(uuid.uuid4())

        body = {
            "clientOrderId": client_order_id,
            "postOnly": post_only,
            "price": str(price),
            "side": side,
            "size": str(size),
            "subaccountId": subaccount_id,
            "symbol": symbol,
            "type": "market"
        }

        body_json = json.dumps(body)
        expires = str(int(time.time() * 1000000) + 300000000)
        signature = self.generate_signature(method, path, body_json, expires)

        headers = {
            "Content-Type": "application/json",
            "Arkham-Api-Key": self.api_key,
            "Arkham-Expires": expires,
            "Arkham-Signature": signature
        }

        logger.info(f"Creating order for {size} {symbol} at {price}...")
        response = requests.post(url, headers=headers, data=body_json, proxies=self.proxies)
        if response.status_code == 200:
            logger.info(f"Order created successfully: {response.json()}")
            return response.json()
        else:
            logger.error(f"Error creating order: {response.status_code} - {response.text}")
            return None
        
    def get_trading_volume(self):
        path = "/affiliate-dashboard/trading-volume-stats"
        url = f"{self.base_url}{path}"
        method = "GET"
        expires = str(int(time.time() * 1000000) + 300000000)
        signature = self.generate_signature(method, path, "", expires)

        headers = {
            "Arkham-Api-Key": self.api_key,
            "Arkham-Expires": expires,
            "Arkham-Signature": signature
        }

        logger.info("Fetching trading volume...")
        response = requests.get(url, headers=headers, proxies=self.proxies)
        if response.status_code == 200:
            volume_data = response.json()
            spot_taker_volume = float(volume_data['spotTakerVolume']) if 'spotTakerVolume' in volume_data and volume_data['spotTakerVolume'] else 0
            spot_maker_volume = float(volume_data['spotMakerVolume']) if 'spotMakerVolume' in volume_data and volume_data['spotMakerVolume'] else 0
            total_volume = spot_taker_volume+spot_maker_volume
            spot_taker_fees = float(volume_data['spotTakerFees']) if 'spotTakerFees' in volume_data and volume_data['spotTakerFees'] else 0
            spot_maker_fees = float(volume_data['spotMakerFees']) if 'spotMakerFees' in volume_data and volume_data['spotMakerFees'] else 0
            
            total_fees = spot_maker_fees + spot_taker_fees
            logger.info(f"Trading volume: {total_volume}")
            logger.info(f"Spot fees: {total_fees}")
            return total_volume
        else:
            logger.error(f"Error fetching trading volume: {response.status_code} - {response.text}")
            return 0


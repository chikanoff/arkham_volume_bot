import time
import hmac
import hashlib
import base64
import uuid
import requests
import json
import random
from loguru import logger

class ArkhamAPI:
    def __init__(self, api_key, api_secret, proxies=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://arkm.com/api"
        self.proxies = proxies
        logger.add("logs/arkham_api.log", rotation="1 day", level="INFO")

    def generate_signature(self, method, path, body, expires):
        message = f"{self.api_key}{expires}{method}{path}{body}"
        secret = base64.b64decode(self.api_secret)
        signature = hmac.new(secret, message.encode(), hashlib.sha256).digest()
        signature_b64 = base64.b64encode(signature).decode()
        logger.debug(f"Generated signature for {path}")
        return signature_b64
    
    def get_open_orders(self, subaccount_id=0):
        path = "/orders"
        url = f"{self.base_url}{path}"
        params = {}
        
        if subaccount_id:
            params['subaccountId'] = subaccount_id
        
        method = "GET"
        expires = str(int(time.time() * 1000000) + 300000000)
        signature = self.generate_signature(method, path, '', expires)
        
        headers = {
            "Content-Type": "application/json",
            "Arkham-Api-Key": self.api_key,
            "Arkham-Expires": expires,
            "Arkham-Signature": signature
        }

        response = requests.get(url, headers=headers, params=params, proxies=self.proxies)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error fetching orders: {response.status_code} - {response.text}")
            return None

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

    def create_order(self, price, size, side, symbol, type, subaccount_id=0, post_only=False):
        path = "/orders/new"
        url = f"{self.base_url}{path}"
        method = "POST"
        client_order_id = str(uuid.uuid4())
        
        if type == "market":
            price = 0

        body = {
            "clientOrderId": client_order_id,
            "postOnly": post_only,
            "price": f"{price:.8f}",
            "side": side,
            "size": str(size),
            "subaccountId": subaccount_id,
            "symbol": symbol,
            "type": type
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

        logger.info(f"Creating order for {side}: {size} {symbol} at {price}. {type}")
        response = requests.post(url, headers=headers, data=body_json, proxies=self.proxies)
        if response.status_code == 200:
            logger.info(f"Order created successfully: {response.json()}")
            return response.json()
        else:
            logger.error(f"Error creating order: {response.status_code} - {response.text}")
            return None
        
    def cancel_orders(self):
        path = "/orders/cancel/all"
        url = f"{self.base_url}{path}"
        method = "POST"
        body = {
            "subaccountId": 0,
            "timeToCancel": 0
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

        logger.info(f"Canceling all open orders..")
        response = requests.post(url, headers=headers, data=body_json, proxies=self.proxies)

        if response.status_code == 200:
            logger.info(f"Orders cancelled successfully: {response.json()}")
            return response.json()
        else:
            logger.error(f"Error cancelling orders: {response.status_code} - {response.text}")
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
            total_spot_volume = spot_taker_volume+spot_maker_volume

            perp_taker_volume = float(volume_data['perpTakerVolume']) if 'perpTakerVolume' in volume_data and volume_data['perpTakerVolume'] else 0
            perp_maker_volume = float(volume_data['perpMakerVolume']) if 'perpMakerVolume' in volume_data and volume_data['perpMakerVolume'] else 0
            total_perp_volume = perp_taker_volume+perp_maker_volume

            spot_taker_fees = float(volume_data['spotTakerFees']) if 'spotTakerFees' in volume_data and volume_data['spotTakerFees'] else 0
            spot_maker_fees = float(volume_data['spotMakerFees']) if 'spotMakerFees' in volume_data and volume_data['spotMakerFees'] else 0
            total_spot_fees = spot_maker_fees + spot_taker_fees

            perp_taker_fees = float(volume_data['perpTakerFees']) if 'perpTakerFees' in volume_data and volume_data['perpTakerFees'] else 0
            perp_maker_fees = float(volume_data['perpMakerFees']) if 'spotMakerFees' in volume_data and volume_data['perpMakerFees'] else 0
            total_perp_fees = perp_taker_fees + perp_maker_fees

            return total_spot_volume, total_perp_volume, total_spot_fees, total_perp_fees
        else:
            logger.error(f"Error fetching trading volume: {response.status_code} - {response.text}")
            return 0

    def get_tickers(self):
        path = "/public/tickers"
        url = f"{self.base_url}{path}"
        method = "GET"
        expires = str(int(time.time() * 1000000) + 300000000)
        signature = self.generate_signature(method, path, "", expires)

        headers = {
            "Arkham-Api-Key": self.api_key,
            "Arkham-Expires": expires,
            "Arkham-Signature": signature
        }

        logger.info("Fetching tickers...")
        response = requests.get(url, headers=headers, proxies=self.proxies)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error fetching tickers: {response.status_code} - {response.text}")
            return 0

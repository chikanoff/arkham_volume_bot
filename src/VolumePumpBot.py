import sqlite3
import random
from datetime import datetime, timedelta
from loguru import logger
import requests
from src.ArkhamAPI import ArkhamAPI
import asyncio

class VolumePumpBot:
    def __init__(self, api: ArkhamAPI, symbols: dict, target_volume: float, max_check_price: int, slippage: float, db_path="orders.db"):
        self.api = api
        self.symbols = symbols
        self.target_volume = target_volume
        self.max_check_price = max_check_price
        self.slippage = slippage
        self.db_path = db_path
        self._setup_db()
        logger.add("bot.log", rotation="1 day", level="INFO")

    def _setup_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                            order_id TEXT PRIMARY KEY,
                            symbol TEXT,
                            side TEXT,
                            size REAL,
                            open_price REAL,
                            status TEXT,
                            created_at TIMESTAMP,
                            closed_at TIMESTAMP,
                            check_count INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()

    def _save_order(self, order_id, symbol, side, size, open_price):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders (order_id, symbol, side, size, open_price, status, created_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                        (order_id, symbol, side, size, open_price, "open", datetime.now()))
        conn.commit()
        conn.close()
        logger.info(f"Сохранен ордер {order_id}: {side} {size} {symbol} по цене {open_price}")


    def _update_order(self, order_id, status, closed_at=None):
        """Обновление статуса ордера."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''UPDATE orders 
                        SET status = ?, closed_at = ? 
                        WHERE order_id = ?''', 
                        (status, closed_at, order_id))
        conn.commit()
        conn.close()
        logger.info(f"Обновлен ордер {order_id}: статус {status}")

    def _get_open_orders(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, symbol, side, size, open_price, status, created_at, closed_at, check_count FROM orders WHERE status = 'open'")
        open_orders = cursor.fetchall()
        conn.close()
        return open_orders

    async def _wait_until_filled(self, symbol):
        is_filled = False
        while not is_filled:
            try:
                open_orders = self.api.get_open_orders()
                if not open_orders:
                    is_filled = True
                    logger.info(f"Ордер заполнился для {symbol}")
                    break
                else:
                    logger.info(f"Ожидание заполнения ордера для {symbol} 10 секунд....")
                    await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Произошла ошибка сети: {e}")
                await asyncio.sleep(12)

    async def open_position(self, symbol):
        """Открытие позиции на весь доступный баланс."""
        balance = self.api.get_balance_for_symbol("USDT")
        if balance is None or balance <= 0:
            logger.error("Недостаточно средств на балансе USDT.")
            return

        current_price = self.api.get_market_price(symbol)
        if current_price is None:
            logger.error(f"Не удалось получить цену для {symbol}.")
            return

        size = balance*0.99 / current_price
        if self.symbols[symbol]["rounding_step"] == 1:
            size = int(size)
        else:
            size = size - (size % self.symbols[symbol]["rounding_step"])

        size = round(size, 10)

        # order_type = random.choice(["limitGtc", "market"])
        order_type = "market"

        response = self.api.create_order(price=current_price, size=size, side="buy", symbol=symbol, type=order_type)

        if response and "orderId" in response:
            order_id = response["orderId"]
            self._save_order(order_id, symbol, "buy", size, current_price)
            await self._wait_until_filled(symbol)
        else:
            logger.error(f"Ошибка при открытии позиции для {symbol}.")

    async def close_position_random(self, order_id, symbol, size):
        """Закрытие позиции (продажа)."""
        current_price = self.api.get_market_price(symbol)
        if current_price is None:
            logger.error(f"Не удалось получить цену для {symbol}.")
            return
        
        order_type = random.choice(["limitGtc", "market"])
        
        response = self.api.create_order(price=current_price, size=size, side="sell", symbol=symbol, type=order_type)
        
        if response:
            self._update_order(order_id, "closed", closed_at=datetime.now())
            await self._wait_until_filled(symbol)
        else:
            logger.error(f"Ошибка при закрытии позиции для {symbol}.")

    async def close_position_by_market(self, order_id, symbol, size):
        """Закрытие позиции (продажа)."""
        current_price = self.api.get_market_price(symbol)
        if current_price is None:
            logger.error(f"Не удалось получить цену для {symbol}.")
            return
        
        response = self.api.create_order(price=current_price, size=size, side="sell", symbol=symbol, type="market")
        
        if response:
            self._update_order(order_id, "closed", closed_at=datetime.now())
            await self._wait_until_filled(symbol)
        else:
            logger.error(f"Ошибка при закрытии позиции для {symbol}.")

    async def manage_positions(self):
        open_orders = self._get_open_orders()

        for order in open_orders:
            order_id, symbol, side, size, open_price, status, created_at, closed_at, check_count = order

            if side != "buy":
                continue

            created_at = datetime.strptime(created_at.split(".")[0], "%Y-%m-%d %H:%M:%S")
            hold_time = datetime.now() - created_at
            current_price = self.api.get_market_price(symbol)
            await asyncio.sleep(2)

            if not current_price:
                logger.error(f"Не удалось получить текущую цену для {symbol}.")
                continue

            if hold_time >= timedelta(minutes=5):
                if current_price >= open_price*(1 + self.slippage):
                    await self.close_position_by_market(order_id, symbol, size)
                    continue

                if current_price >= open_price:
                    await self.close_position_random(order_id, symbol, size)
                    continue

                if check_count >= self.max_check_price:
                    logger.warning(f"Принудительное закрытие {symbol}, цена: {current_price}")
                    await self.close_position_by_market(order_id, symbol, size)
                else:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        '''UPDATE orders SET check_count = check_count + 1 WHERE order_id = ?''',
                        (order_id,)
                    )
                    conn.commit()
                    conn.close()

                    logger.info(f"Цена для {symbol} ниже точки входа. Проверка #{check_count + 1}.")

    async def run(self):
        """Запуск бота с учетом рандомной задержки."""
        while True:
            try:
                if self.api.get_open_orders():
                    self._wait_until_filled()

                current_volume = self.api.get_trading_volume()
                logger.info(f"Текущий объем сделок: {current_volume}")

                if current_volume >= self.target_volume:
                    logger.info(f"Целевой объем {self.target_volume} достигнут!")
                    break

                open_orders = self._get_open_orders()

                if not open_orders:
                    symbol = random.choice(list(self.symbols.keys()))
                    await self.open_position(symbol)
                    await asyncio.sleep(2)
                else:
                    await self.manage_positions()

                await asyncio.sleep(random.randint(30, 60))

            except requests.exceptions.RequestException as e:
                logger.error(f"Произошла ошибка сети: {e}")
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Неизвестная ошибка: {e}")
                await asyncio.sleep(10)


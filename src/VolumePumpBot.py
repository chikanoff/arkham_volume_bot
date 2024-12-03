import sqlite3
import random
from datetime import datetime, timedelta
from loguru import logger
from src.ArkhamAPI import ArkhamAPI
import asyncio

class VolumePumpBot:
    def __init__(self, api: ArkhamAPI, symbols: dict, target_volume: float, percentage_of_balance: float, db_path="orders.db"):
        self.api = api
        self.symbols = symbols
        self.target_volume = target_volume
        self.percentage_of_balance = percentage_of_balance
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

        size = balance*0.9 / current_price
        size = size - (size % self.symbols[symbol]["rounding_step"])
        size = round(size, 10)
        response = self.api.create_order(price=0, size=size, side="buy", symbol=symbol)

        if response and "orderId" in response:
            order_id = response["orderId"]
            self._save_order(order_id, symbol, "buy", size, current_price)
        else:
            logger.error(f"Ошибка при открытии позиции для {symbol}.")


    async def close_position(self, order_id, symbol, size):
        """Закрытие позиции (продажа)."""
        response = self.api.create_order(price=0, size=size, side="sell", symbol=symbol)

        if response:
            self._update_order(order_id, "closed", closed_at=datetime.now())
        else:
            logger.error(f"Ошибка при закрытии позиции для {symbol}.")

    async def manage_positions(self):
        max_checks = 3  # Максимальное количество проверок цены
        slippage = 0.005  # Допустимое отклонение (0.5%)
        open_orders = self._get_open_orders()

        for order in open_orders:
            order_id, symbol, side, size, open_price, status, created_at, closed_at, check_count = order

            if side != "buy":
                continue  # Обрабатываем только покупку

            created_at = datetime.strptime(created_at.split(".")[0], "%Y-%m-%d %H:%M:%S")
            hold_time = datetime.now() - created_at
            current_price = self.api.get_market_price(symbol)

            if not current_price:
                logger.error(f"Не удалось получить текущую цену для {symbol}.")
                continue

            # Проверяем, если цена превышает open_price с учетом slippage
            if current_price >= open_price * (1 + slippage):
                await self.close_position(order_id, symbol, size)
                continue

            # Если позиция слишком долго держится, проверяем количество проверок
            if hold_time >= timedelta(minutes=5):
                if check_count >= max_checks:
                    logger.warning(f"Принудительное закрытие {symbol}, цена: {current_price}")
                    await self.close_position(order_id, symbol, size)
                else:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        '''UPDATE orders SET check_count = check_count + 1 WHERE order_id = ?''',
                        (order_id,)
                    )
                    conn.commit()
                    conn.close()

                    logger.info(f"Цена для {symbol} ещё ниже точки входа. Проверка #{check_count + 1}.")

    async def run(self):
        """Запуск бота с учетом рандомной задержки."""
        while True:
            current_volume = self.api.get_trading_volume()
            logger.info(f"Текущий объем сделок: {current_volume}")

            if current_volume >= self.target_volume:
                logger.info(f"Целевой объем {self.target_volume} достигнут!")
                break

            open_orders = self._get_open_orders()

            if not open_orders:
                symbol = random.choice(list(self.symbols.keys()))
                await self.open_position(symbol)
            else:
                await self.manage_positions()

            # Рандомная задержка
            await asyncio.sleep(random.randint(60, 120))


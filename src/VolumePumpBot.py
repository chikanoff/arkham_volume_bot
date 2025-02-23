import sqlite3
import random
from datetime import datetime, timedelta
from loguru import logger
import requests
from src.ArkhamAPI import ArkhamAPI
import asyncio

class VolumePumpBot:
    def __init__(
            self, 
            api: ArkhamAPI, 
            symbols: dict, 
            spot_target_volume: float, 
            perp_target_volume: float, 
            max_check_price: int, 
            slippage: float, 
            is_perpetual, 
            leverage,
            hold_time: int,
            limit_order_diff: float,
            limit_hold_time: int,
            db_path="orders.db"
    ):
        self.api = api
        self.symbols = symbols
        self.spot_target_volume = spot_target_volume
        self.max_check_price = max_check_price
        self.slippage = slippage
        self.db_path = db_path
        self.is_perpetual = is_perpetual
        self.leverage = leverage
        self.hold_time = hold_time
        self.perp_target_volume = perp_target_volume
        self.limit_order_diff= limit_order_diff
        self.limit_hold_time = limit_hold_time
        self._setup_db()
        logger.add("bot.log", rotation="1 day", level="INFO")

    def _setup_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                            order_id TEXT PRIMARY KEY,
                            account_id TEXT,
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

    def _save_order(self, order_id, account_id, symbol, side, size, open_price):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders (order_id, account_id, symbol, side, size, open_price, status, created_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (order_id, account_id, symbol, side, size, open_price, "open", datetime.now()))
        conn.commit()
        conn.close()
        logger.info(f"Сохранен ордер {order_id} для {account_id}: {side} {size} {symbol} по цене {open_price}")

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

    def _get_open_orders(self, account_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE account_id = ? AND status = 'open'", (account_id,))
        open_orders = cursor.fetchall()
        conn.close()
        return open_orders

    def _calculate_limit_price(self, current_price, side, rounding_step=0.01):
        """Рассчитать цену лимитного ордера с учетом шага цены."""
        adjustment = current_price * self.limit_order_diff
        if side == "buy":
            limit_price = current_price - adjustment
        elif side == "sell":
            limit_price = current_price + adjustment
        else:
            limit_price = current_price

        # Округление до кратного шага цены
        return round(limit_price - (limit_price % rounding_step), 2)


    async def _wait_until_filled(self, order_id=None, symbol=None, size=None,  side=None):
        start_time = datetime.now()
        while True:
            try:
                open_orders = self.api.get_open_orders()
                if not open_orders:
                    logger.info(f"Нет открытых ордеров")
                    break

                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time >= self.limit_hold_time:
                    logger.warning(f"Ордер {order_id} для {symbol} не заполнился за {self.limit_hold_time} секунд. Переустановка ордера.")
                    self.api.cancel_orders()
                    
                    current_price = self.api.get_market_price(symbol)
                    new_price = self._calculate_limit_price(current_price, side, self.symbols[symbol]["rounding_step"])
                    new_order = self.api.create_order(price=new_price, size=size, side=side, symbol=symbol, type="limitGtc")

                    if new_order and "orderId" in new_order:
                        order_id = new_order["orderId"]
                        start_time = datetime.now()
                    else:
                        logger.error(f"Не удалось создать новый ордер для {symbol}.")
                        break
                logger.info("Ожидание заполнения ордера...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Ошибка при ожидании заполнения ордера для {symbol}: {e}")
                await asyncio.sleep(10)


    async def open_position(self, symbol):
        """Открытие позиции на весь доступный баланс с лимитным ордером."""
        balance = self.api.get_balance_for_symbol("USDT")
        if balance is None or balance <= 0:
            logger.error("Недостаточно средств на балансе USDT.")
            return

        current_price = self.api.get_market_price(symbol)
        if current_price is None:
            logger.error(f"Не удалось получить цену для {symbol}.")
            return

        size = (balance * 0.95 * self.leverage / current_price) if self.is_perpetual else (balance * 0.95 / current_price)
        size = round(size - (size % self.symbols[symbol]["rounding_step"]), 10)

        limit_price = self._calculate_limit_price(current_price, side="buy", rounding_step=self.symbols[symbol]["rounding_step"])
        response = self.api.create_order(price=limit_price, size=size, side="buy", symbol=symbol, type="limitGtc")

        if response and "orderId" in response:
            order_id = response["orderId"]
            self._save_order(order_id, self.api.api_key, symbol, "buy", size, limit_price)
            await self._wait_until_filled(order_id, symbol, size, side="buy")
        else:
            logger.error(f"Ошибка при открытии позиции для {symbol}.")


    async def close_position_limit(self, order_id, symbol, size):
        """Закрытие позиции лимитным ордером с небольшим увеличением цены."""
        current_price = self.api.get_market_price(symbol)
        if current_price is None:
            logger.error(f"Не удалось получить цену для {symbol}.")
            return

        limit_price = self._calculate_limit_price(current_price, side="sell", rounding_step=self.symbols[symbol]["rounding_step"])
        response = self.api.create_order(price=limit_price, size=size, side="sell", symbol=symbol, type="limitGtc")

        if response:
            self._update_order(order_id, "closed", closed_at=datetime.now())
            await self._wait_until_filled(order_id, symbol, size, side="sell")
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
            await self._wait_until_filled(order_id, symbol, size, side="sell")
        else:
            logger.error(f"Ошибка при закрытии позиции для {symbol}.")

    async def manage_positions(self):
        open_orders = self._get_open_orders(account_id=self.api.api_key)

        for order in open_orders:
            order_id, account_id, symbol, side, size, open_price, status, created_at, closed_at, check_count = order

            if side != "buy":
                continue

            created_at = datetime.strptime(created_at.split(".")[0], "%Y-%m-%d %H:%M:%S")
            hold_time = datetime.now() - created_at
            current_price = self.api.get_market_price(symbol)
            await asyncio.sleep(2)

            if not current_price:
                logger.error(f"{account_id}: Не удалось получить текущую цену для {symbol}.")
                continue

            if current_price >= open_price*(1 + self.slippage):
                logger.info(f"Текущая цена больше цены открытия на {self.slippage} - закрываем позицию")
                await self.close_position_limit(order_id, symbol, size)
                continue

            if hold_time >= timedelta(minutes=self.hold_time):
                if current_price >= open_price:
                    await self.close_position_limit(order_id, symbol, size)
                    continue

                if check_count >= self.max_check_price:
                    logger.warning(f"{account_id}: Принудительное закрытие {symbol}, цена: {current_price}")
                    await self.close_position_limit(order_id, symbol, size)
                else:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        '''UPDATE orders SET check_count = check_count + 1 WHERE order_id = ?''',
                        (order_id,)
                    )
                    conn.commit()
                    conn.close()

                    logger.info(f"{account_id}: Цена для {symbol} ниже точки входа. Проверка #{check_count + 1}.")

    async def run(self):
        """Запуск бота с учетом рандомной задержки."""
        while True:
            try:
                if self.api.get_open_orders():
                    self._wait_until_filled()

                spot_volume, perp_volume, spot_fees, perp_fees = self.api.get_trading_volume()
                

                if spot_volume >= self.spot_target_volume and not self.is_perpetual:
                    logger.info(f"Целевой объем по споту {self.spot_target_volume} достигнут!")
                    break

                if perp_volume >= self.perp_target_volume and self.is_perpetual:
                    logger.info(f"Целевой объем по фьючам {self.spot_target_volume} достигнут!")
                    break

                open_orders = self._get_open_orders(account_id=self.api.api_key)

                if not open_orders:
                    logger.info(f"Spot volume: {spot_volume}")
                    logger.info(f"Spot fees: {spot_fees}")

                    logger.info(f"PERP volume: {perp_volume}")
                    logger.info(f"PERP fees: {perp_fees}")
                    symbol = random.choice(list(self.symbols.keys()))
                    await self.open_position(symbol)
                    await asyncio.sleep(2)
                else:
                    await self.manage_positions()

                await asyncio.sleep(random.randint(40, 50))

            except requests.exceptions.RequestException as e:
                logger.error(f"Произошла ошибка сети: {e}")
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Неизвестная ошибка: {e}")
                await asyncio.sleep(10)


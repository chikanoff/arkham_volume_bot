import asyncio
import sqlite3
import time
from datetime import datetime
from loguru import logger
from src.ArkhamAPI import ArkhamAPI

class VolumePumpBot:
    def __init__(self, api: ArkhamAPI, symbol, db_path='volume_pump.db'):
        self.api = api  # Экземпляр класса для работы с API
        self.symbol = symbol
        self.db_path = db_path
        self._create_db()  # Инициализация базы данных
        logger.add("bot.log", rotation="1 day", level="INFO")  # Логирование в файл

    def _create_db(self):
        """Создание базы данных для хранения сделок."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                            order_id TEXT PRIMARY KEY,
                            side TEXT,
                            price REAL,
                            size REAL,
                            status TEXT,
                            created_at TIMESTAMP,
                            closed_at TIMESTAMP,
                            pnl REAL)''')
        conn.commit()
        conn.close()
    
    def calculate_max_order_size(self):
        """Вычисление максимального размера ордера, который можно открыть на основе текущего баланса."""
        balance = self.api.get_balance_for_symbol('USDT')  # Получаем доступный баланс

        price = self.api.get_market_price(self.symbol)  # Получаем текущую цену

        if balance and price:
            max_size = balance / price  # Максимальный размер ордера
            return max_size
        else:
            logger.error(f"Недостаточно баланса для открытия ордера по паре {self.symbol}")
            return 0

    def _save_order(self, order_id, side, price, size):
        """Сохранение ордера в базе данных."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders (order_id, side, price, size, status, created_at) 
                          VALUES (?, ?, ?, ?, ?, ?)''', 
                          (order_id, side, price, size, 'open', datetime.now()))
        conn.commit()
        conn.close()
        logger.info(f"Открыт ордер {order_id}: {side} {size} {self.symbol} по цене {price}")

    def _update_order(self, order_id, status, closed_at=None, pnl=None):
        """Обновление статуса ордера в базе данных."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''UPDATE orders 
                          SET status = ?, closed_at = ?, pnl = ? 
                          WHERE order_id = ?''', 
                          (status, closed_at, pnl, order_id))
        conn.commit()
        conn.close()
        logger.info(f"Ордер {order_id} обновлен: статус {status}, PnL {pnl}")

    async def open_order(self, side, size):
        """Открытие ордера."""
        price = self.api.get_market_price(self.symbol)  # Получаем текущую цену
        if not price:
            logger.error("Ошибка при получении цены")
            return None
        
        # Открываем ордер
        order_response = self.api.create_order(price, size, side, self.symbol)
        if order_response is not None and 'orderId' in order_response:
            order_id = order_response['orderId']
            self._save_order(order_id, side, price, size)
            logger.info(f"Открыт ордер: {order_id} на {size} {self.symbol} по цене {price}")
            return order_id
        else:
            logger.error(f"Ошибка при создании ордера или пустой ответ: {order_response}")
            return None

    async def close_order(self, order_id):
        """Закрытие ордера."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT price, size, side FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order:
            price, size, side = order[0], order[1], order[2]
            current_price = self.api.get_market_price(self.symbol)

            # Пример расчета PnL
            pnl = (current_price - price) * size if side == 'buy' else (price - current_price) * size
            self._update_order(order_id, status='closed', closed_at=datetime.now(), pnl=pnl)
            logger.info(f"Ордер {order_id} закрыт с PnL: {pnl}")
        else:
            logger.error(f"Ордер {order_id} не найден")

    async def manage_orders(self):
        """Менеджер сделок."""
        open_orders = True
        while open_orders:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE status = 'open'")
            orders = cursor.fetchall()
            conn.close()

            for order in orders:
                order_id, side, price, size, status, created_at, closed_at, pnl = order
                created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S.%f")
                if (datetime.now() - created_at).total_seconds() >= 300:  # Сделка открыта более 5 минут
                    if pnl and pnl >= 0:  # Закрываем сделку только с профитом или без убытков
                        await self.close_order(order_id)
            await asyncio.sleep(10)

    async def run(self, target_volume):
        """Запуск бота для накрутки объема."""
        while True:
            # Получаем текущий объем сделок
            current_volume = self.api.get_trading_volume()
            logger.info(f"Текущий объем сделок: {current_volume}")

            # Если достигнут целевой объем, выходим из цикла
            if current_volume >= target_volume:
                logger.info(f"Целевой объем {target_volume} достигнут!")
                break

            max_size = self.calculate_max_order_size()
            if max_size:  # Проверка на минимальный размер ордера
                await self.open_order('buy', max_size*0.9)
                # Открытие ордеров
                await self.manage_orders()
            else:
                logger.warning("Недостаточно средств для открытия ордера.")


            await asyncio.sleep(10)  # Задержка перед новым циклом

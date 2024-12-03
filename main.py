from dotenv import load_dotenv
import os
import asyncio
from src.utils import load_account_info
from src.ArkhamAPI import ArkhamAPI
from src.VolumePumpBot import VolumePumpBot

load_dotenv()

async def main():
    # Загружаем информацию об аккаунтах из файла
    accounts = load_account_info('accounts.csv')
    tasks = []

    # Определяем тикеры и параметры бота
    symbols = {
        "ETH_USDT": {"rounding_step": 0.001},
        "BTC_USDT": {"rounding_step": 0.00001},
        "PEPE_USDT": {"rounding_step": 1},
        "SOL_USDT": {"rounding_step": 0.001},
        "WIF_USDT": {"rounding_step": 0.01}
    }
    target_volume = 10000  # Целевой объем
    percentage_of_balance = 0.3  # Процент от баланса для сделок

    for account in accounts:
        proxies = {
            "http": f"http://{account['proxy']}",
            "https": f"http://{account['proxy']}"
        }

        # Создаем экземпляр API и бота
        api = ArkhamAPI(account['api_key'], account['api_secret'], proxies=proxies)
        bot = VolumePumpBot(api=api, symbols=symbols, target_volume=target_volume, percentage_of_balance=percentage_of_balance)

        # Добавляем задачу для запуска бота
        tasks.append(bot.run())

    # Запускаем все боты параллельно
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

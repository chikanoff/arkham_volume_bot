from dotenv import load_dotenv
import os
import asyncio
from src.utils import load_account_info
from src.ArkhamAPI import ArkhamAPI
from src.VolumePumpBot import VolumePumpBot


load_dotenv()

async def main():
    accounts = load_account_info('accounts.csv')
    tasks = []

    for account in accounts:
        proxies = {
            "http": f"http://{account['proxy']}",
            "https": f"http://{account['proxy']}"
        }
        
        api = ArkhamAPI(account['api_key'], account['api_secret'], proxies=proxies)
        bot = VolumePumpBot(api=api, symbol='BTC_USDT')
        
        # Создаем задачу для каждого аккаунта
        tasks.append(bot.run(10000))

    # Запускаем все задачи параллельно
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

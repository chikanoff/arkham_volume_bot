import json
import asyncio
from uuid import uuid4
from src.utils import load_account_info
from src.ArkhamAPI import ArkhamAPI
from src.VolumePumpBot import VolumePumpBot


def load_config(config_path="config.json"):
    with open(config_path, "r") as f:
        return json.load(f)

async def main():
    accounts = load_account_info('accounts.csv')
    config = load_config()

    target_volume = config["target_volume"]
    max_check_price = config["max_check_price"]
    slippage = config["slippage"]
    tasks = []

    # тикеры
    symbols = {
        "ETH_USDT": {"rounding_step": 0.001},
        "BTC_USDT": {"rounding_step": 0.00001},
        "PEPE_USDT": {"rounding_step": 1},
        "SOL_USDT": {"rounding_step": 0.001},
        "WIF_USDT": {"rounding_step": 0.01},
        "AVAX_USDT": {"rounding_step": 0.01}
    }

    for account in accounts:
        proxies = {
            "http": f"http://{account['proxy']}",
            "https": f"http://{account['proxy']}"
        }

        api = ArkhamAPI(account['api_key'], account['api_secret'], proxies=proxies)
        bot = VolumePumpBot(api=api, symbols=symbols, target_volume=target_volume, max_check_price=max_check_price, slippage=slippage)

        tasks.append(bot.run())

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

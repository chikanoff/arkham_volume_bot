import json
import asyncio
from src.utils import load_account_info
from src.ArkhamAPI import ArkhamAPI
from src.VolumePumpBot import VolumePumpBot


def load_config(config_path="config.json"):
    with open(config_path, "r") as f:
        return json.load(f)

async def main():
    accounts = load_account_info('accounts.csv')
    config = load_config()

    spot_target_volume = config["spot_target_volume"]
    max_check_price = config["max_check_price"]
    slippage = config["slippage"]
    is_perpetual = config["is_perpetual"]
    leverage = config["leverage"]
    perp_target_volume = config["perp_target_volume"]
    hold_time = config["hold_time"]
    limit_order_diff = config["limit_order_diff"]
    limit_hold_time = config["limit_hold_time"]
    tasks = []

    # тикеры
    symbols = {
        "ETH_USDT": {"rounding_step": 0.001},
        "BTC_USDT": {"rounding_step": 0.00001},
        # "PEPE_USDT": {"rounding_step": 1},
        "SOL_USDT": {"rounding_step": 0.001},
        # "WIF_USDT": {"rounding_step": 0.01},
        # "AVAX_USDT": {"rounding_step": 0.01}
    }

    symbols_perp = {
        "ETH_USDT_PERP": {"rounding_step": 0.001},
        # "BTC_USDT_PERP": {"rounding_step": 0.00001},
        # "PEPE_USDT_PERP": {"rounding_step": 1},
        # "SOL_USDT_PERP": {"rounding_step": 0.001},
        # "WIF_USDT_PERP": {"rounding_step": 0.01},
        # "AVAX_USDTPERP": {"rounding_step": 0.01}
    }

    for account in accounts:
        proxies = None
        if account["proxy"]:
            proxies = {
                "http": f"http://{account['proxy']}",
                "https": f"http://{account['proxy']}"
            }

        trading_symbols = symbols
        
        if is_perpetual:
            trading_symbols = symbols_perp

        api = ArkhamAPI(account['api_key'], account['api_secret'], proxies=proxies)
        bot = VolumePumpBot(
            api=api, 
            symbols=trading_symbols, 
            spot_target_volume=spot_target_volume, 
            perp_target_volume=perp_target_volume, 
            max_check_price=max_check_price, 
            slippage=slippage, 
            is_perpetual=is_perpetual, 
            leverage=leverage,
            hold_time=hold_time,
            limit_order_diff=limit_order_diff,
            limit_hold_time=limit_hold_time
        )
        tasks.append(bot.run())

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())

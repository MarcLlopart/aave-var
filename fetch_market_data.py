import pandas as pd
import numpy as np
import requests
import time
import json
import os
from io import StringIO
from datetime import datetime, timedelta


OUTPUT_FILE = "data/volatility_and_correlation.json"

ASSET_MAP = {
    "WETH": "weth",
    "USDT": "tether",
    "USDC": "usd-coin",
    "WBTC": "wrapped-bitcoin",
    "wstETH": "wrapped-steth",
    "weETH": "wrapped-eeth",
    "cbBTC": "coinbase-wrapped-btc",
    "sUSDe": "ethena-staked-usde",
    "USDe": "ethena-usde",
    "RLUSD": "ripple-usd"
}


STABLECOINS = ["USDT", "USDC", "RLUSD"]

def fetch_coingecko_price_history(coin_id, currency="usd"):
    url = f"https://www.coingecko.com/price_charts/export/{coin_id}/{currency}.csv"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            csv_data = StringIO(response.text)
            try:
                df = pd.read_csv(csv_data)
            except pd.errors.ParserError:
                print(f"  Error parsing CSV for {coin_id}")
                return None
            
            if df.empty:
                return None
                
            if 'snapped_at' in df.columns:
                 df['timestamp'] = pd.to_datetime(df['snapped_at'])
            elif 'timestamp' in df.columns:
                 df['timestamp'] = pd.to_datetime(df['timestamp'])
            else:
                print(f"  Unknown columns for {coin_id}: {df.columns}")
                return None
            
            df.set_index('timestamp', inplace=True)
            df = df.resample('D').last()
            return df['price']
            
        elif response.status_code == 429:
            print("  Rate limited! Waiting 30s...")
            time.sleep(30)
            return fetch_coingecko_price_history(coin_id, currency)
        else:
            print(f"  Failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    all_prices = pd.DataFrame()
    
    for symbol, coin_id in ASSET_MAP.items():
        series = fetch_coingecko_price_history(coin_id)
        
        if series is not None and not series.empty:
            series.name = symbol
            
            if all_prices.empty:
                all_prices = series.to_frame()
            else:
                all_prices = all_prices.join(series, how='outer')
        
        time.sleep(1.5)
    
    all_prices.ffill(inplace=True)
    all_prices.dropna(inplace=True)
    all_prices.dropna(inplace=True)
    

    if all_prices.empty:
        print("Error: No overlapping price data found.")
        return

    log_returns = np.log(all_prices / all_prices.shift(1)).dropna()
    
    correlation_matrix = log_returns.corr()
    
    covariance_matrix = log_returns.cov() * 365
    
    daily_vol = log_returns.std()
    annual_vol = daily_vol * np.sqrt(365)
    
    latest_prices = all_prices.iloc[-1]
    
    output_data = {
        "assets": list(all_prices.columns),
        "latest_prices": latest_prices.to_dict(),
        "annual_volatility": annual_vol.to_dict(),
        "correlation_matrix": correlation_matrix.values.tolist(),
        "covariance_matrix": covariance_matrix.values.tolist(),
        "data_start": str(all_prices.index[0]),
        "data_end": str(all_prices.index[-1])
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)
        

if __name__ == "__main__":
    main()

import pandas as pd
import numpy as np
import requests
import time
import os
from io import StringIO
from datetime import datetime, timedelta

TOP_ASSETS = [
    {"symbol": "WETH", "name": "Wrapped Ether", "coingecko_id": "weth", "supply": 9.17},
    {"symbol": "USDT", "name": "Tether", "coingecko_id": "tether", "supply":6.62},
    {"symbol": "weETH", "name": "Wrapped eETH", "coingecko_id": "wrapped-eeth", "supply": 6.36},
    {"symbol": "USDC", "name": "USD Coin", "coingecko_id": "usd-coin", "supply": 4.53},
    {"symbol": "wstETH", "name": "Wrapped stETH", "coingecko_id": "wrapped-steth", "supply": 4.19},
    {"symbol": "WBTC", "name": "Wrapped Bitcoin", "coingecko_id": "wrapped-bitcoin", "supply": 3.88},
    {"symbol": "cbBTC", "name": "Coinbase BTC", "coingecko_id": "coinbase-wrapped-btc", "supply": 1.82},
    {"symbol": "sUSDe", "name": "Staked USDe", "coingecko_id": "ethena-staked-usde", "supply": 0.832},
    {"symbol": "USDe", "name": "USDe", "coingecko_id": "ethena-usde", "supply": 0.802},
    {"symbol": "RLUSD", "name": "RLUSD", "coingecko_id": "ripple-usd", "supply": 0.599}
]

OUTPUT_FILE = "data/aave_var_results.csv"

def fetch_coingecko_csv(coin_id, currency="usd"):
    url = f"https://www.coingecko.com/price_charts/export/{coin_id}/{currency}.csv"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            return df
        else:
            print(f"Failed to fetch CSV for {coin_id}. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {coin_id}: {e}")
        return None

def fetch_coingecko_api(coin_id, days=365):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'prices' not in data: 
                return None
            
            prices = data['prices']
            df = pd.DataFrame(prices, columns=["snapped_at", "price"])
            df['snapped_at'] = pd.to_datetime(df['snapped_at'], unit='ms')
            return df
        else:
            print(f"API failed for {coin_id}. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"API Error {coin_id}: {e}")
        return None

def get_historical_data(coin_id):
    df = fetch_coingecko_csv(coin_id)
    
    if df is None or df.empty:
        time.sleep(2)
        df = fetch_coingecko_api(coin_id)
        
    if df is not None:
        df.columns = [c.lower() for c in df.columns]
        if 'snapped_at' in df.columns:
            df['date'] = pd.to_datetime(df['snapped_at'])
        elif 'timestamp' in df.columns:
             df['date'] = pd.to_datetime(df['timestamp'])
             
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        return df['price']
    
    return None

def calculate_metrics(prices_series, window_days):
    if len(prices_series) < window_days:
        return None
        
    start_date = prices_series.index[-1] - timedelta(days=window_days)
    window_data = prices_series[prices_series.index >= start_date]
    
    if len(window_data) < 2:
        return None
        
    returns = window_data.pct_change().dropna()
    
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(365)
    
    Z_99_9 = 3.090
    var_99_9_1d_pct = Z_99_9 * daily_vol
    
    return {
        "annual_vol": annual_vol,
        "var_99_9_1d_pct": var_99_9_1d_pct
    }

if __name__ == "__main__":
    results = []
    
    for asset in TOP_ASSETS:
        symbol = asset['symbol']
        coin_id = asset['coingecko_id']
        supply_b = asset['supply']
        
        prices = get_historical_data(coin_id)
        
        if prices is None:
            print(f"Skipping {symbol} (No data)")
            continue
            
        metrics = {}
        
        if not prices.empty:
            metrics['latest_price'] = prices.iloc[-1]
        else:
            metrics['latest_price'] = np.nan

        for period, label in [(30, "Short"), (90, "Mid"), (365, "Long")]:
            m = calculate_metrics(prices, period)
            if m:
                metrics[f"vol_{label}"] = m['annual_vol']
                metrics[f"var99.9_{label}"] = m['var_99_9_1d_pct']
                
                metrics[f"var_amt_99.9_{label}_B"] = m['var_99_9_1d_pct'] * supply_b
            else:
                metrics[f"vol_{label}"] = np.nan
        
        metrics['symbol'] = symbol
        metrics['supply_B'] = supply_b
        results.append(metrics)
        
        time.sleep(1)
    
    df_res = pd.DataFrame(results)
    
    cols = ['symbol', 'supply_B', 'latest_price',
            'vol_Short', 'var99.9_Short', 'var_amt_99.9_Short_B',
            'vol_Mid', 'var99.9_Mid', 
            'vol_Long', 'var99.9_Long']
    
    actual_cols = [c for c in cols if c in df_res.columns]
    df_final = df_res[actual_cols]
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.float_format', lambda x: '%.4f' % x)

    df_final.to_csv(OUTPUT_FILE, index=False)


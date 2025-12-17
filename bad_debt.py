import requests
import pandas as pd
from dotenv import load_dotenv
import os
from io import StringIO

load_dotenv()

# Aave v3 Ethereum Subgraph ID
API_KEY = os.getenv("GRAPH_API_KEY")
SUBGRAPH_ID = "Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g"
URL = f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_ID}"
OUTPUT_FILE = "data/active_positions.csv"

# Target symbols
TARGET_SYMBOLS = [
    {"symbol": "WETH", "name": "Wrapped Ether", "coingecko_id": "weth", "supply": 9.17},
    {"symbol": "USDT", "name": "Tether", "coingecko_id": "tether", "supply": 6.62},
    {"symbol": "weETH", "name": "Wrapped eETH", "coingecko_id": "wrapped-eeth", "supply": 6.36},
    {"symbol": "USDC", "name": "USD Coin", "coingecko_id": "usd-coin", "supply": 4.53},
    {"symbol": "wstETH", "name": "Wrapped stETH", "coingecko_id": "wrapped-steth", "supply": 4.19},
    {"symbol": "WBTC", "name": "Wrapped Bitcoin", "coingecko_id": "wrapped-bitcoin", "supply": 3.88},
    {"symbol": "cbBTC", "name": "Coinbase BTC", "coingecko_id": "coinbase-wrapped-btc", "supply": 1.82},
    {"symbol": "sUSDe", "name": "Staked USDe", "coingecko_id": "ethena-staked-usde", "supply": 0.832},
    {"symbol": "USDe", "name": "USDe", "coingecko_id": "ethena-usde", "supply": 0.802},
    {"symbol": "RLUSD", "name": "RLUSD", "coingecko_id": "ripple-usd", "supply": 0.599}
]

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

def get_latest_eth_price():
    df = fetch_coingecko_csv("ethereum", "usd")
    
    if df is not None and not df.empty:
        latest_price = df.iloc[-1]['price'] if 'price' in df.columns else df.iloc[-1][1]
        return float(latest_price)
    
    return None

def fetch_all_token_prices():
    prices = {}
    
    for token in TARGET_SYMBOLS:
        coin_id = token["coingecko_id"]
        df = fetch_coingecko_csv(coin_id, "usd")
        
        if df is not None and not df.empty:
            latest_price = df.iloc[-1]['price'] if 'price' in df.columns else df.iloc[-1][1]
            prices[token["symbol"]] = float(latest_price)
            print(f"  {token['symbol']}: ${latest_price:,.2f}")
    
    return prices

def fetch_all_user_data():
    all_users = {}
    last_id = ""

    while True:
        query = """
        query GetUsers($lastId: String!) {
          users(
            first: 1000
            where: { id_gt: $lastId }
            orderBy: id
            orderDirection: asc
          ) {
            id
            reserves {
              id
              reserve {
                symbol
                decimals
                underlyingAsset
              }
              currentATokenBalance
              currentVariableDebt
              currentStableDebt
              currentTotalDebt
              usageAsCollateralEnabledOnUser
            }
          }
        }
        """
        
        response = requests.post(
            URL,
            json={"query": query, "variables": {"lastId": last_id}},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        
        if "errors" in data:
            print(f"GraphQL Error: {data['errors']}")
            break
        
        users = data.get("data", {}).get("users", [])
        
        if not users:
            break
        
        for user in users:
            all_users[user["id"]] = user
        
        last_id = users[-1]["id"]
    return all_users

def calculate_bad_debt(users_data, token_prices, target_symbols):
    
    symbol_list = [s["symbol"] for s in target_symbols]
    target_decimals = {s["symbol"]: 0 for s in target_symbols} 
    
    bad_debt_by_symbol = {symbol: 0.0 for symbol in symbol_list}
    users_with_bad_debt_by_symbol = {symbol: 0 for symbol in symbol_list}
    user_details_by_symbol = {symbol: [] for symbol in symbol_list}
    
    all_active_positions = []
    
    processed = 0
    for user_id, user_data in users_data.items():
        reserves = user_data.get("reserves", [])
        
        if not reserves:
            continue
        
        processed += 1
        if processed % 1000 == 0:
            print(f"  Processed {processed} users...")
        
        total_collateral_usd = 0.0
        total_debt_usd = 0.0
        debt_by_symbol = {}
        
        user_positions = []
        
        for reserve in reserves:
            symbol = reserve["reserve"]["symbol"]
            decimals = int(reserve["reserve"]["decimals"])
            
            price_usd = token_prices.get(symbol, 0.0)
            
            collateral_balance = float(reserve["currentATokenBalance"]) / (10 ** decimals)
            collateral_usd = 0.0
            if reserve["usageAsCollateralEnabledOnUser"]:
                collateral_usd = collateral_balance * price_usd
                total_collateral_usd += collateral_usd
            
            debt_balance = float(reserve["currentTotalDebt"]) / (10 ** decimals)
            debt_usd = debt_balance * price_usd
            total_debt_usd += debt_usd
            
            if symbol in symbol_list and debt_usd > 0:
                if symbol not in debt_by_symbol:
                    debt_by_symbol[symbol] = 0.0
                debt_by_symbol[symbol] += debt_usd
            
            if collateral_balance > 0 or debt_balance > 0:
                user_positions.append({
                    "user_id": user_id,
                    "symbol": symbol,
                    "collateral_amount": collateral_balance,
                    "debt_amount": debt_balance,
                    "is_collateral": reserve["usageAsCollateralEnabledOnUser"],
                    "price": price_usd
                })
        
        if total_debt_usd > 0:
             all_active_positions.extend(user_positions)

        user_bad_debt = total_debt_usd - total_collateral_usd
        
        if user_bad_debt > 0:
            for symbol, debt_amount in debt_by_symbol.items():
                if symbol in symbol_list:
                    proportion = debt_amount / total_debt_usd if total_debt_usd > 0 else 0
                    symbol_bad_debt = user_bad_debt * proportion
                    
                    bad_debt_by_symbol[symbol] += symbol_bad_debt
                    users_with_bad_debt_by_symbol[symbol] += 1
                    
                    user_details_by_symbol[symbol].append({
                        "user_id": user_id,
                        "total_debt": total_debt_usd,
                        "total_collateral": total_collateral_usd,
                        "bad_debt": user_bad_debt,
                        "symbol_debt": debt_amount,
                        "symbol_bad_debt": symbol_bad_debt
                    })
    
    return bad_debt_by_symbol, users_with_bad_debt_by_symbol, user_details_by_symbol, all_active_positions

def main():    
    token_prices = fetch_all_token_prices()
    
    users_data = fetch_all_user_data()
    
    if not users_data:
        print("No user data fetched")
        return
    
    bad_debt_by_symbol, users_with_bad_debt, user_details, all_active_positions = calculate_bad_debt(
        users_data, 
        token_prices, 
        TARGET_SYMBOLS
    )

    active_df = pd.DataFrame(all_active_positions)
    active_df.to_csv(OUTPUT_FILE, index=False)

if __name__ == "__main__":
    main()
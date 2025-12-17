import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import json
from monte_carlo import geometric_brownian_motion, correlated_geometric_brownian_motion, load_simulation_data, INPUT_FILE

# Configuration
NUM_SIMULATIONS = 10000
ACTIVE_POSITIONS_FILE = "data/active_positions.csv"
MARKET_DATA_FILE = "data/volatility_and_correlation.json"
VAR_PERCENTILE = 99.9

def calculate_user_equity(user_positions, price_map):
    """
    Calculate user equity (Collateral - Debt) given a map of symbol -> price.
    Returns: (total_collateral_usd, total_debt_usd, net_value_usd)
    """
    total_collateral = 0.0
    total_debt = 0.0
    
    for pos in user_positions:
        symbol = pos['symbol']
        price = price_map.get(symbol, pos['price'])
        
        if pos['is_collateral']:
            total_collateral += pos['collateral_amount'] * price
        
        total_debt += pos['debt_amount'] * price
        
    return total_collateral, total_debt, total_collateral - total_debt

def simulate_bad_debt(active_positions_df, market_data, num_simulations=NUM_SIMULATIONS):

    assets = market_data['assets']
    latest_prices = market_data['latest_prices']
    annual_vol = market_data['annual_volatility']
    correlation_matrix = np.array(market_data['correlation_matrix'])

    S0_list = [latest_prices.get(a, 0) for a in assets]
    sigma_list = [annual_vol.get(a, 0) for a in assets]
    mu_list = [0.0] * len(assets)

    user_groups = active_positions_df.groupby('user_id')
    users_list = []
    for user_id, group in user_groups:
        positions = group.to_dict('records')
        users_list.append(positions)
        
    paths = correlated_geometric_brownian_motion(
        S0_list, mu_list, sigma_list, correlation_matrix, 
        T=1.0, n_steps=365, n_sims=num_simulations
    )
    
    final_prices_matrix = paths[-1]
    
    simulation_bad_debts = []
    
    for i in range(num_simulations):
        if i % 100 == 0:
            print(f"  Simulating scenario {i}/{num_simulations}...")
        
        price_map_scenario = {
            assets[j]: final_prices_matrix[i, j] 
            for j in range(len(assets))
        }
        
        total_bad_debt_scenario = 0.0
        
        for user_positions in users_list:
            collateral, debt, net_value = calculate_user_equity(user_positions, price_map_scenario)
            
            if net_value < 0:
                total_bad_debt_scenario += abs(net_value)
                
        simulation_bad_debts.append(total_bad_debt_scenario)
    
    return simulation_bad_debts

def main():
    if not os.path.exists(ACTIVE_POSITIONS_FILE):
        print(f"Error: {ACTIVE_POSITIONS_FILE} not found. Run bad_debt.py first.")
        return
        
    if not os.path.exists(MARKET_DATA_FILE):
        print(f"Error: {MARKET_DATA_FILE} not found. Run fetch_market_data.py first.")
        return

    active_df = pd.read_csv(ACTIVE_POSITIONS_FILE)
    
    with open(MARKET_DATA_FILE, 'r') as f:
        market_data = json.load(f)
        
    bad_debt_distribution = simulate_bad_debt(active_df, market_data, NUM_SIMULATIONS)
    
    bad_debt_var = np.percentile(bad_debt_distribution, VAR_PERCENTILE)
    average_bad_debt = np.mean(bad_debt_distribution)
    max_bad_debt = np.max(bad_debt_distribution)
    
    print("\n" + "="*50)
    print("AAVE VaR ANALYSIS RESULTS (CORRELATED)")
    print("="*50)
    print(f"Simulations: {NUM_SIMULATIONS}")
    print(f"Confidence Level: {VAR_PERCENTILE}%")
    print(f"Time Horizon: 1 Year (365 Days)")
    print("-" * 30)
    print(f"VaR (99.9%): ${bad_debt_var:,.2f}")
    print(f"Average Bad Debt: ${average_bad_debt:,.2f}")
    print(f"Max Bad Debt observed: ${max_bad_debt:,.2f}")
    print("="*50)
    
    plt.figure(figsize=(10, 6))
    plt.hist(bad_debt_distribution, bins=50, color='royalblue', alpha=0.7)
    plt.axvline(bad_debt_var, color='red', linestyle='dashed', linewidth=2, label=f'VaR 99.9%: ${bad_debt_var:,.0f}')
    plt.title('Distribution of Protocol Bad Debt (Correlated Monte Carlo)')
    plt.xlabel('Bad Debt ($)')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig('results/var_distribution_correlated.png')
    print("Saved distribution plot to var_distribution_correlated.png")

if __name__ == "__main__":
    main()

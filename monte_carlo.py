import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import math

NUM_SIMULATIONS = 10000
INPUT_FILE = "data/aave_var_results.csv"
OUTPUT_FILE = "results/monte_carlo_matrix.png"

TERMS = {
    'Short': {'days': 30, 'col_vol': 'vol_Short'},
    'Mid': {'days': 90, 'col_vol': 'vol_Mid'},
    'Long': {'days': 365, 'col_vol': 'vol_Long'}
}

def load_simulation_data(input_file=INPUT_FILE):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return None
    return pd.read_csv(input_file)

def geometric_brownian_motion(S0, mu, sigma, T, n_steps, n_sims):
    dt = T / n_steps
    Z = np.random.normal(0, 1, size=(n_steps, n_sims))
    paths = np.zeros((n_steps + 1, n_sims))
    paths[0] = S0
    drift = (mu - 0.5 * sigma**2) * dt
    diffusion = sigma * np.sqrt(dt) * Z
    log_returns = drift + diffusion
    accumulated_returns = np.cumsum(log_returns, axis=0)
    paths[1:] = S0 * np.exp(accumulated_returns)
    return paths

def correlated_geometric_brownian_motion(S0_list, mu_list, sigma_list, corr_matrix, T, n_steps, n_sims):
    """
    Generate correlated GBM paths for multiple assets.
    S0_list: list of initial prices
    mu_list: list of drift rates (usually 0)
    sigma_list: list of volatilities
    corr_matrix: correlation matrix (n_assets x n_assets)
    """
    n_assets = len(S0_list)
    dt = T / n_steps
    

    try:
        L = np.linalg.cholesky(corr_matrix)
    except np.linalg.LinAlgError:
        L = np.linalg.cholesky(corr_matrix + np.eye(n_assets) * 1e-5)

    Z_uncorr = np.random.normal(0, 1, size=(n_steps, n_sims, n_assets))
    
    Z_corr = np.dot(Z_uncorr, L.T)
    paths = np.zeros((n_steps + 1, n_sims, n_assets))
    paths[0] = S0_list
    
    for i in range(n_assets):
        mu = mu_list[i]
        sigma = sigma_list[i]
        S0 = S0_list[i]
        
        drift = (mu - 0.5 * sigma**2) * dt
        diffusion = sigma * np.sqrt(dt) * Z_corr[:, :, i]
        
        log_returns = drift + diffusion
        accumulated_returns = np.cumsum(log_returns, axis=0)
        
        paths[1:, :, i] = S0 * np.exp(accumulated_returns)
        
    return paths

def main():
    df = load_simulation_data()
    if df is None:
        return
    
    assets = df['symbol'].tolist()
    n_assets = len(assets)
    
    terms_list = [('Short', 30, 'vol_Short'), ('Mid', 90, 'vol_Mid'), ('Long', 365, 'vol_Long')]
    n_terms = len(terms_list)
    
    fig, axes = plt.subplots(nrows=n_assets, ncols=n_terms, figsize=(18, 4 * n_assets))
    
    fig.suptitle(f'Monte Carlo Simulations (99.9% VaR) - {NUM_SIMULATIONS} Sims', fontsize=20, y=0.99)

    for i, asset in enumerate(assets):
        row_data = df[df['symbol'] == asset].iloc[0]
        
        for j, (term_name, days, col_vol) in enumerate(terms_list):
            ax = axes[i, j]
            
            if col_vol not in row_data or pd.isna(row_data[col_vol]):
                ax.text(0.5, 0.5, 'No Data', ha='center')
                ax.set_title(f"{asset} - {term_name}", fontsize=10)
                continue

            vol = row_data[col_vol]

            if 'latest_price' in row_data and not pd.isna(row_data['latest_price']):
                S0 = row_data['latest_price']
            else:
                S0 = 1.0
                
            mu = 0.0
            T_years = days / 365.0
            n_steps = days
            
            paths = geometric_brownian_motion(S0, mu, vol, T_years, n_steps, NUM_SIMULATIONS)
            final_prices = paths[-1]
            
            percentile_0_1 = np.percentile(final_prices, 0.1) # 99.9% confidence
            var_price_level = percentile_0_1
            
            n_plot_paths = min(100, NUM_SIMULATIONS)
            ax.plot(paths[:, :n_plot_paths], alpha=0.15, color='royalblue', linewidth=0.5)
            
            ax.axhline(y=var_price_level, color='red', linestyle='--', linewidth=2, label=f'VaR 99.9% Price')
            
            if i == 0:
                ax.set_title(f"{term_name} Term ({days} days)", fontsize=14, fontweight='bold')
            
            if j == 0:
                ax.set_ylabel(f"{asset}\nPrice ($)", fontsize=12, fontweight='bold')
            else:
                pass
                
            ax.set_xlabel('Days')
            ax.grid(True, alpha=0.3)

            stats_text = f"Vol: {vol:.1%}\nMin: {var_price_level:.3f}"
            ax.text(0.02, 0.03, stats_text, transform=ax.transAxes, 
                    bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'), fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.985]) 
    plt.savefig(OUTPUT_FILE, dpi=100)
    plt.close(fig)

if __name__ == "__main__":
    main()

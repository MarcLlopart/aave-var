import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

INPUT_FILE = "data/aave_var_results.csv"
OUTPUT_FILE = "results/volatility_var_comparison.png"

def main():
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = df.dropna(subset=['symbol'])

    terms = ['Short', 'Mid', 'Long']
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharey=True)
    fig.suptitle('Volatility vs VaR (99.9%) Comparison per Timeframe', fontsize=16)

    bar_width = 0.35
    
    for i, term in enumerate(terms):
        ax = axes[i]
        
        symbols = df['symbol']
        x = np.arange(len(symbols))
        
        vol_col = f'vol_{term}'
        var_col = f'var99.9_{term}'
        
        if vol_col not in df.columns or var_col not in df.columns:
            print(f"Warning: Columns for {term} term not found.")
            continue
            
        vol_values = df[vol_col]
        var_values = df[var_col]
        
        rects1 = ax.bar(x - bar_width/2, vol_values, bar_width, label='Volatility', color='royalblue', alpha=0.8)
        
        rects2 = ax.bar(x + bar_width/2, var_values, bar_width, label='VaR (99.9%)', color='red', alpha=0.8)
        
        ax.set_title(f'{term} Term', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(symbols, rotation=45, ha='right')
        
        if i == 0:
            ax.set_ylabel('Value (Normalized)', fontsize=12)
            ax.legend()
            
        ax.grid(axis='y', linestyle='--', alpha=0.3)

        def autolabel(rects):
            for rect in rects:
                height = rect.get_height()
                ax.annotate(f'{height:.2f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=8, rotation=90)

        autolabel(rects1)
        autolabel(rects2)

    plt.tight_layout()
    plt.subplots_adjust(top=0.90) 
    
    plt.savefig(OUTPUT_FILE, dpi=300)
    print(f"Saved comparison plot to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

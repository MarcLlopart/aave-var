import requests
import pandas as pd
from dotenv import load_dotenv
import os
load_dotenv()

API_KEY = os.getenv("GRAPH_API_KEY")
SUBGRAPH_ID = "Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g"
URL = f"https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/{SUBGRAPH_ID}"

OUTPUT_FILE = "data/top_borrowers.csv"

def fetch_borrows():
    query = """
    query GetBorrows($skip: Int!) {
      borrows(first: 1000, skip: $skip, orderBy: timestamp, orderDirection: desc) {
        user { id }
        reserve { symbol underlyingAsset decimals }
        amount
        assetPriceUSD
      }
    }
    """
    
    all_borrows = []
    skip = 0

    while skip < 5000:
        response = requests.post(
            URL,
            json={"query": query, "variables": {"skip": skip}},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        
        if "errors" in data:
            print(f"GraphQL Error: {data['errors']}")
            break
        
        borrows = data.get("data", {}).get("borrows", [])
        if not borrows:
            break
            
        all_borrows.extend(borrows)
        skip += 1000

    return all_borrows

def main():
    borrows = fetch_borrows()
    
    if not borrows:
        print("No data fetched.")
        return
    
    df = pd.DataFrame([
        {
            "borrower": b["user"]["id"],
            "symbol": b["reserve"]["symbol"],
            "token_address": b["reserve"]["underlyingAsset"],
            "amount_usd": (float(b["amount"]) * float(b["assetPriceUSD"]) / (10 ** b["reserve"]["decimals"])) 
        }
        for b in borrows
    ])
    
    result = (df.groupby(["borrower", "symbol", "token_address"])
              .agg({"amount_usd": "sum"})
              .reset_index()
              .rename(columns={"amount_usd": "total_borrowed_amt"}))
    
    result = (result[result["total_borrowed_amt"] > 0]
              .sort_values("total_borrowed_amt", ascending=False)
              .head(1000))
    
    result.to_csv(OUTPUT_FILE, index=False)

if __name__ == "__main__":
    main()
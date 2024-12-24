import sys
import os
import requests
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logging.basicConfig(level=logging.INFO)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError("Missing Supabase credentials for buy_placeholder script.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_jupiter_price(mint: str) -> float:
    """
    Fetches the current price for the given mint from Jupiter's Price API V2.
    Returns 0.0 if any error occurs.
    """
    try:
        url = f"https://api.jup.ag/price/v2?ids={mint}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return float(data["data"][mint]["price"])
        else:
            logging.warning(f"Jupiter returned status {resp.status_code} for mint={mint}")
    except Exception as e:
        logging.error(f"Error fetching Jupiter price for mint={mint}: {e}", exc_info=True)
    return 0.0

def insert_portfolio_entry(mint: str, buy_price: float, quantity: float):
    """
    Inserts a row into the 'portfolio' table indicating we hold this token.
    """
    try:
        # Optionally, we can attempt to find a coin_uuid from 'coins' table, if it exists
        coin_uuid = None
        try:
            # Suppose the 'coins' table has a 'mint' column. Adjust if needed.
            coin_resp = supabase.table('coins').select('id').eq('mint', mint).limit(1).execute()
            if coin_resp.data and len(coin_resp.data) > 0:
                coin_uuid = coin_resp.data[0]['id']
        except Exception as e:
            logging.error(f"Unable to find coin_uuid for mint={mint}, continuing without it. Error: {e}")

        insert_data = {
            "mint": mint,
            "price": buy_price,
            "quantity": quantity,
            "inpossession": True,
        }
        if coin_uuid:
            insert_data["coin_uuid"] = coin_uuid

        supabase.table('portfolio').insert(insert_data).execute()
        logging.info(f"Inserted into portfolio => mint={mint}, price={buy_price}, qty={quantity}, coin_uuid={coin_uuid}")
    except Exception as e:
        logging.error(f"Error inserting into portfolio table: {e}", exc_info=True)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        mint = sys.argv[1]
        print(f"[BUY PLACEHOLDER] Buying token with mint: {mint}")

        # 1) Fetch Jupiter price
        cur_price = fetch_jupiter_price(mint)

        # 2) Insert into portfolio with quantity=500000
        default_qty = 500000.0
        insert_portfolio_entry(mint, cur_price, default_qty)
    else:
        print("[BUY PLACEHOLDER] No mint provided, but simulating buy.")
    print("token bought")

# File: /pompv1/balance_bar.py

import time
import os
import requests
import logging
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WATERMILL_FLASK_URL = os.getenv("WATERMILL_FLASK_URL", "http://localhost:5000")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("Missing Supabase credentials.")
    sys.exit(1)

# Create Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_current_jupiter_price(mint: str) -> float:
    """
    Fetches the current token price in USDC from Jupiter's Price API V2.
    Returns the price as a float, or 0.0 on error.
    """
    try:
        # Example call: https://api.jup.ag/price/v2?ids=<mint>
        url = f"https://api.jup.ag/price/v2?ids={mint}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # data["data"][mint]["price"] -> string
            return float(data["data"][mint]["price"])
        else:
            logging.warning(f"Jupiter price API returned status {resp.status_code} for mint={mint}")
    except Exception as e:
        logging.error(f"Error fetching Jupiter price for mint={mint}: {e}", exc_info=True)
    return 0.0

def update_balance_bar_loop():
    """
    Main loop that:
      1. Fetches all 'inpossession' coins from 'portfolio'
      2. For each, calls Jupiter price API
      3. Calculates the net difference vs. the stored 'price'
      4. Sums across the portfolio
      5. Sends the sum to the front-end to update the bar
    """
    while True:
        try:
            # Get all coins in portfolio with inpossession = true
            resp = supabase.table('portfolio') \
                .select("*") \
                .eq('inpossession', True) \
                .execute()
            rows = resp.data
            total_net = 0.0

            if rows:
                for row in rows:
                    mint = row.get("mint")
                    buy_price = float(row.get("price", 0.0))
                    qty = float(row.get("quantity", 0.0))
                    if mint and qty > 0 and buy_price > 0:
                        current_price = fetch_current_jupiter_price(mint)
                        # net for this token = quantity * (current_price - buy_price)
                        net_diff = qty * (current_price - buy_price)
                        total_net += net_diff

            # Emit or POST to image_processor to let it emit a socket event
            post_url = f"{WATERMILL_FLASK_URL}/update_balance_bar"
            payload = {"netbalance": total_net}
            try:
                requests.post(post_url, json=payload, timeout=5)
            except Exception as e:
                logging.error(f"Error posting to /update_balance_bar: {e}", exc_info=True)

        except Exception as e:
            logging.error(f"Error in update_balance_bar_loop: {e}", exc_info=True)

        time.sleep(10)

if __name__ == "__main__":
    logging.info("Starting balance_bar loop...")
    update_balance_bar_loop()

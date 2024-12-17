# app.py

import os
from flask import Flask, render_template, abort
from dotenv import load_dotenv
import requests
import logging

# ===========================
# Load Environment Variables
# ===========================

load_dotenv()  # Load variables from .env into environment

# ===========================
# Flask App Configuration
# ===========================

app = Flask(__name__)

# ===========================
# Supabase Configuration
# ===========================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")  # If needed

if not SUPABASE_URL or not SUPABASE_API_KEY:
    logging.error("Supabase URL or API Key not found in environment variables.")
    exit(1)

# ===========================
# Logging Configuration
# ===========================

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detailed logs
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# ===========================
# Helper Functions
# ===========================

def get_headers():
    """
    Returns the headers required for Supabase REST API requests.
    """
    return {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def get_all_bundles():
    """
    Retrieve all bundles and count the number of coins in each.
    """
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/bundles",
            headers=get_headers(),
            params={
                "select": "*",
                "order": "created_at.desc"
            }
        )
        response.raise_for_status()
        bundles = response.json()
        
        # For each bundle, count the number of coins
        for bundle in bundles:
            coins_response = requests.get(
                f"{SUPABASE_URL}/rest/v1/coins",
                headers=get_headers(),
                params={
                    "select": "id",
                    "bundle_id": f"eq.{bundle['id']}"
                }
            )
            coins_response.raise_for_status()
            coins = coins_response.json()
            bundle['coin_count'] = len(coins)
        
        return bundles
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching bundles: {e}")
        return []

def get_bundle_by_id(bundle_id):
    """
    Retrieve a specific bundle and its coins.
    """
    try:
        bundle_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/bundles",
            headers=get_headers(),
            params={
                "id": f"eq.{bundle_id}"
            }
        )
        bundle_response.raise_for_status()
        bundles = bundle_response.json()
        if not bundles:
            return None, []
        
        bundle = bundles[0]
        
        # Retrieve coins in the bundle
        coins_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/coins",
            headers=get_headers(),
            params={
                "bundle_id": f"eq.{bundle_id}",
                "order": "coin_id.asc"
            }
        )
        coins_response.raise_for_status()
        coins = coins_response.json()
        
        return bundle, coins
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching bundle {bundle_id}: {e}")
        return None, []

def get_coin_by_id(coin_id):
    """
    Retrieve a specific coin by its ID.
    """
    try:
        coin_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/coins",
            headers=get_headers(),
            params={
                "id": f"eq.{coin_id}"
            }
        )
        coin_response.raise_for_status()
        coins = coin_response.json()
        if not coins:
            return None
        return coins[0]
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching coin {coin_id}: {e}")
        return None

# ===========================
# Routes
# ===========================

@app.route('/')
def index():
    """
    Homepage: Displays a list of all bundles.
    """
    bundles = get_all_bundles()
    return render_template('index.html', bundles=bundles)

@app.route('/bundle/<bundle_id>')
def bundle_detail(bundle_id):
    """
    Bundle Page: Displays all coins in the specified bundle.
    """
    bundle, coins = get_bundle_by_id(bundle_id)
    if not bundle:
        abort(404, description="Bundle Not Found")
    return render_template('bundle.html', bundle=bundle, coins=coins)

@app.route('/coin/<coin_id>')
def coin_detail(coin_id):
    """
    Coin Page: Displays detailed information about a specific coin.
    """
    coin = get_coin_by_id(coin_id)
    if not coin:
        abort(404, description="Coin Not Found")
    return render_template('coin.html', coin=coin)

# ===========================
# Error Handlers
# ===========================

@app.errorhandler(404)
def not_found(error):
    return render_template('base.html', content=f"<h1>404 - Not Found</h1><p>{error.description}</p>"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html', content=f"<h1>500 - Internal Server Error</h1><p>{error.description}</p>"), 500

# ===========================
# Run the App
# ===========================

if __name__ == '__main__':
    app.run(debug=True)

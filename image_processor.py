import os
import time
import json
import redis
import requests
import logging
from io import BytesIO
from PIL import Image
from flask import Flask
from flask_socketio import SocketIO
from dotenv import load_dotenv
from openai_decider import get_decision
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(level=logging.INFO)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
REDIS_URL = os.getenv("REDIS_URL","redis://localhost:6380/0")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("SUPABASE_URL or SUPABASE_KEY not set.")
    exit(1)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logging.error(f"Failed to create Supabase client: {e}", exc_info=True)
    exit(1)

try:
    r = redis.from_url(REDIS_URL)
except Exception as e:
    logging.error(f"Failed to connect to Redis: {e}", exc_info=True)
    exit(1)

app = Flask(__name__, static_url_path='/static', static_folder='frontend')
socketio = SocketIO(app, cors_allowed_origins="*")

IMG_WIDTH = 512
IMG_HEIGHT = 512
GRID_COLS = 2
GRID_ROWS = 4
BOX_WIDTH = IMG_WIDTH // GRID_COLS
BOX_HEIGHT = IMG_HEIGHT // GRID_ROWS

current_bundle_id = None

def process_next_bundle():
    global current_bundle_id
    item = r.lpop("bundle_queue")
    if not item:
        logging.info("No item found in bundle_queue.")
        return

    logging.info(f"Pulled item from queue: {item}")

    try:
        data = json.loads(item)
    except json.JSONDecodeError:
        logging.error("Invalid JSON in queue item.")
        return

    bundle_id = data.get("bundle_id")
    image_url = data.get("image_url")
    logging.info(f"Starting process for bundle {bundle_id} with image_url {image_url}")

    if not bundle_id or not image_url:
        logging.error("Bundle data missing bundle_id or image_url.")
        return

    current_bundle_id = bundle_id

    # Download image
    logging.info("Downloading image...")
    try:
        resp = requests.get(image_url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        logging.info("Image downloaded and opened successfully.")
    except requests.RequestException as e:
        logging.error(f"Failed to download image for bundle {bundle_id}: {e}", exc_info=True)
        return
    except Exception as e:
        logging.error(f"Error processing image for bundle {bundle_id}: {e}", exc_info=True)
        return

    # Prepare directory for this bundle
    bundle_dir = os.path.join(app.static_folder, "coins", bundle_id)
    os.makedirs(bundle_dir, exist_ok=True)

    coins_data = []
    for i in range(8):
        row = i // GRID_COLS
        col = i % GRID_COLS
        x = col * BOX_WIDTH
        y = row * BOX_HEIGHT
        try:
            coin_img = img.crop((x,y,x+BOX_WIDTH,y+BOX_HEIGHT))
            coin_file_name = f"{i+1:02d}.png"
            coin_path = os.path.join(bundle_dir, coin_file_name)
            coin_img.save(coin_path, format='PNG')
            logging.info(f"Cropped and saved coin {i+1} to {coin_path}")
            # Note the /static prefix in the URL
            coins_data.append({
                "id": f"{i+1:02d}",
                "url": f"/static/coins/{bundle_id}/{coin_file_name}"
            })
        except Exception as e:
            logging.error(f"Error cropping coin {i+1} from bundle {bundle_id}: {e}", exc_info=True)
            return

    try:
        socketio.emit("clear_canvas", {"bundle_id": bundle_id})
        logging.info("Emitted clear_canvas to frontend.")
        time.sleep(1)
        for c in coins_data:
            socketio.emit("add_coin", {"bundle_id": bundle_id, "id": c["id"], "url": c["url"]})
            logging.info(f"Sent coin {c['id']} (URL: {c['url']}) to frontend.")
            time.sleep(0.5)
    except Exception as e:
        logging.error(f"Error sending coins to frontend: {e}", exc_info=True)
        return

    # Fetch metadata from Supabase
    try:
        res = supabase.table('coins').select("*").eq('bundle_id', bundle_id).execute()
        coin_rows = res.data
        coin_rows.sort(key=lambda x: x['coin_id'])
        coin_info_list = []
        for c in coin_rows:
            coin_info_list.append({
                "id": c['coin_id'],
                "name": c.get('metadata_name', ''),
                "symbol": c.get('metadata_symbol', ''),
                "description": c.get('metadata_description', '')
            })
        logging.info("Fetched coin metadata from Supabase.")
    except Exception as e:
        logging.error(f"Error fetching coin metadata for bundle {bundle_id}: {e}", exc_info=True)
        return

    # Get decisions via OpenAI
    logging.info("Requesting decisions from OpenAI...")
    decisions = get_decision(bundle_id, image_url, coin_info_list)
    logging.info(f"OpenAI decisions: {decisions}")
    if decisions is None:
        logging.error(f"No valid OpenAI decisions for bundle {bundle_id}.")
        return

    # Emit overlay marks and fade out
    try:
        socketio.emit("overlay_marks", decisions)
        logging.info("Sent overlay_marks to frontend.")
        time.sleep(5)
        socketio.emit("fade_out", {})
        logging.info("Sent fade_out to frontend.")
    except Exception as e:
        logging.error(f"Error overlaying marks/fading out for bundle {bundle_id}: {e}", exc_info=True)

    current_bundle_id = None
    logging.info(f"Completed processing for bundle {bundle_id}")

@app.route('/')
def index():
    return app.send_static_file('index.html')

def run_processor():
    while True:
        process_next_bundle()
        time.sleep(5)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_processor, daemon=True)
    t.start()
    socketio.run(app, host="0.0.0.0", port=5000)

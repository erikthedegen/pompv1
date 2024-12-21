import websocket
import json
import time
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Resampling
import logging
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from cloudflare_uploader import upload_to_cloudflare

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("Supabase URL or Key not found.")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

API_URL = os.getenv("API_URL", "wss://pumpportal.fun/api/data")

TOTAL_COINS = 8
GRID_COLS = 2
GRID_ROWS = 4
IMG_WIDTH = 512
IMG_HEIGHT = 512
BOX_WIDTH = IMG_WIDTH // GRID_COLS
BOX_HEIGHT = IMG_HEIGHT // GRID_ROWS

FONT_PATH = os.getenv("FONT_PATH", "notosans.ttf")
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 6
NAME_START_FONT_SIZE = 16
NAME_MIN_FONT_SIZE = 6
DESC_START_FONT_SIZE = 14
DESC_MIN_FONT_SIZE = 6
LABEL_BOX_SIZE = 22
LINE_SPACING = 2
LABEL_FONT_SIZE = 14

coins_buffer = []

def load_font(font_path, size):
    if os.path.isfile(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            logging.error(f"Failed to load font '{font_path}' with size {size}: {e}")
    else:
        logging.warning(f"Font file '{font_path}' not found. Using default font.")
    return ImageFont.load_default()

NAME_FONT_DEFAULT = load_font(FONT_PATH, NAME_START_FONT_SIZE)
DESC_FONT_DEFAULT = load_font(FONT_PATH, DESC_START_FONT_SIZE)
LABEL_FONT = load_font(FONT_PATH, LABEL_FONT_SIZE)

def text_size(draw, text, font):
    if not text:
        return 0, 0
    bbox = draw.textbbox((0,0), text, font=font)
    width = bbox[2]-bbox[0]
    height = bbox[3]-bbox[1]
    return width, height

def fit_single_line(draw, text, max_width, max_height, start_font_size=16, min_font_size=6):
    ellipsis = "…"
    for fs in range(start_font_size, min_font_size - 1, -1):
        font = load_font(FONT_PATH, fs)
        tw, th = text_size(draw, text, font)
        if th <= max_height:
            if tw <= max_width:
                return text, font
            else:
                # Truncate
                line = text
                while line and text_size(draw, line + ellipsis, font)[0] > max_width:
                    line = line[:-1]
                if line:
                    return line + ellipsis, font
    font = load_font(FONT_PATH, min_font_size)
    return ellipsis, font

def force_wrap_text(draw, text, font, max_width):
    if not text:
        return []
    lines = []
    words = text.split()
    current_line = ""

    def line_width(txt):
        return text_size(draw, txt, font)[0]

    def break_long_word(word):
        chunks = []
        current = ""
        for ch in word:
            test = current + ch
            if line_width(test) > max_width and current:
                chunks.append(current)
                current = ch
            else:
                current = test
        if current:
            chunks.append(current)
        return chunks

    for w in words:
        if line_width(w) > max_width:
            parts = break_long_word(w)
            for part in parts:
                test_line = (current_line + " " + part).strip() if current_line else part
                if line_width(test_line) > max_width and current_line:
                    lines.append(current_line)
                    current_line = part
                else:
                    current_line = test_line
        else:
            test_line = (current_line + " " + w).strip() if current_line else w
            if line_width(test_line) > max_width and current_line:
                lines.append(current_line)
                current_line = w
            else:
                current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines

def fit_description(draw, text, max_width, max_height, start_font_size=14, min_font_size=6):
    for fs in range(start_font_size, min_font_size - 1, -1):
        font = load_font(FONT_PATH, fs)
        wrapped_lines = force_wrap_text(draw, text, font, max_width)
        total_h = sum(text_size(draw, line, font)[1] for line in wrapped_lines) + LINE_SPACING*(len(wrapped_lines)-1)
        if total_h <= max_height:
            return wrapped_lines, font
    return None, None

def save_bundle_to_db(coins):
    try:
        bundle_response = supabase.table('bundles').insert({}).execute()
        if not bundle_response.data:
            logging.error(f"Failed to insert bundle: {bundle_response}")
            return None
        bundle_id = bundle_response.data[0]['id']
        logging.info(f"Inserted bundle with ID: {bundle_id}")

        for idx, coin in enumerate(coins):
            coin_id = f"{idx+1:02d}"
            coin_data = {
                "bundle_id": bundle_id,
                "coin_id": coin_id,
                "mint": coin.get("mint", ""),
                "pumpfun_url": coin.get("pumpfun_url", ""),
                "metadata_image_official": coin.get("metadata_image_official", ""),
                "metadata_name": coin.get("metadata_name", ""),
                "metadata_symbol": coin.get("metadata_symbol", ""),
                "metadata_description": coin.get("metadata_description", ""),
                "twitter": coin.get("twitter", None),       # New field
                "website": coin.get("website", None)        # New field
            }
            coin_response = supabase.table('coins').insert(coin_data).execute()
            if not coin_response.data:
                logging.error(f"Failed to insert coin {coin_id}: {coin_response}")
            else:
                logging.info(f"Inserted coin {coin_id} into bundle {bundle_id}")
        return bundle_id
    except Exception as e:
        logging.error(f"Error saving bundle to database: {e}", exc_info=True)
        return None

def scale_image_keep_aspect(img, max_size):
    w, h = img.size
    scale = min(max_size/w, max_size/h)
    return img.resize((int(w*scale), int(h*scale)), Resampling.LANCZOS)

def draw_coin_box(draw, main_image, x, y, coin_data, index):
    draw.rectangle([x, y, x+BOX_WIDTH-1, y+BOX_HEIGHT-1], fill="white", outline="white", width=1)
    draw.rectangle([x+2, y+2, x+BOX_WIDTH-3, y+BOX_HEIGHT-3], outline="red", width=1)

    margin = 5
    safe_x = x + margin
    safe_y = y + margin
    safe_w = BOX_WIDTH - 2*margin
    safe_h = BOX_HEIGHT - 2*margin

    image_size = 100
    coin_img = None
    coin_img_url = coin_data.get("metadata_image_official", "")
    if coin_img_url:
        try:
            resp = requests.get(coin_img_url, timeout=5)
            if resp.status_code == 200:
                cimg = Image.open(BytesIO(resp.content)).convert("RGBA")
                max_img_size = min(image_size, safe_h)
                coin_img = scale_image_keep_aspect(cimg, max_img_size)
            else:
                logging.warning(f"Failed to fetch image for coin {index+1}: Status {resp.status_code}")
        except Exception as e:
            logging.error(f"Error fetching coin image for coin {index+1}: {e}", exc_info=True)
    else:
        logging.warning(f"No image available for coin {index+1}")

    img_w, img_h = 0, 0
    if coin_img:
        img_w, img_h = coin_img.size
        img_y = safe_y + (safe_h - img_h) // 2
        main_image.paste(coin_img, (safe_x, img_y), coin_img)

    draw_obj = draw
    vertical_offset = 10
    text_start_x = safe_x + img_w + 8
    right_margin = 5

    label_id_text = f"{index+1:02d}"
    label_x = text_start_x
    label_y = safe_y + vertical_offset

    draw_obj.rectangle([label_x, label_y, label_x+LABEL_BOX_SIZE-1, label_y+LABEL_BOX_SIZE-1],
                       fill="white", outline="red", width=1)
    lw, lh = text_size(draw_obj, label_id_text, LABEL_FONT)
    ltx = label_x + (LABEL_BOX_SIZE - lw) // 2
    lty = label_y + (LABEL_BOX_SIZE - lh) // 2 - 4
    draw_obj.text((ltx, lty), label_id_text, fill="red", font=LABEL_FONT)

    name_area_x = label_x + LABEL_BOX_SIZE + 5
    name_area_w = (safe_x + safe_w - right_margin) - name_area_x
    name_area_h = LABEL_BOX_SIZE

    raw_name = (coin_data.get("metadata_name") or "").strip() or "(No Name)"
    symbol = (coin_data.get("metadata_symbol") or "").strip()
    name_line_text = raw_name
    ticker_line_text = f"({symbol})" if symbol else ""

    name_line, name_font = fit_single_line(draw_obj, name_line_text, name_area_w, name_area_h,
                                           start_font_size=NAME_START_FONT_SIZE,
                                           min_font_size=NAME_MIN_FONT_SIZE)
    nw, nh = text_size(draw_obj, name_line, name_font)
    name_line_y = label_y + (LABEL_BOX_SIZE - nh) // 2 - 13
    draw_obj.text((name_area_x, name_line_y), name_line, fill="black", font=name_font)

    if ticker_line_text:
        ticker_line, ticker_font = fit_single_line(draw_obj, ticker_line_text, name_area_w, name_area_h,
                                                   start_font_size=NAME_START_FONT_SIZE,
                                                   min_font_size=NAME_MIN_FONT_SIZE)
        tw, th = text_size(draw_obj, ticker_line, ticker_font)
        ticker_line_y = name_line_y + nh + 3
        draw_obj.text((name_area_x, ticker_line_y), ticker_line, fill="black", font=ticker_font)
    else:
        ticker_line_y = name_line_y
        th = 0

    desc_y = ticker_line_y + (th if ticker_line_text else 0) + 5
    desc_x = text_start_x
    desc_w = (safe_x + safe_w - right_margin) - desc_x
    desc_h = (safe_y + safe_h) - desc_y

    desc = (coin_data.get("metadata_description") or "").strip()
    if len(desc) > 60:
        desc = desc[:60] + "..."

    if desc:
        desc_lines, desc_font = fit_description(draw_obj, desc, desc_w, desc_h,
                                                start_font_size=DESC_START_FONT_SIZE,
                                                min_font_size=DESC_MIN_FONT_SIZE)
        if desc_lines is None:
            small_font = load_font(FONT_PATH, MIN_FONT_SIZE)
            draw_obj.text((desc_x, desc_y), "[Desc too long]", fill="black", font=small_font)
        else:
            for dl in desc_lines:
                tw, th = text_size(draw_obj, dl, desc_font)
                draw_obj.text((desc_x, desc_y), dl, fill="black", font=desc_font)
                desc_y += th + LINE_SPACING

def create_image_for_coins(coins, bundle_id):
    os.makedirs("bundleimagesmain", exist_ok=True)
    from PIL import ImageDraw
    main_image = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255, 255))
    draw = ImageDraw.Draw(main_image)
    for i, coin in enumerate(coins):
        row = i // GRID_COLS
        col = i % GRID_COLS
        x = col * BOX_WIDTH
        y = row * BOX_HEIGHT
        draw_coin_box(draw, main_image, x, y, coin, i)
    filename = os.path.join("bundleimagesmain", f"{bundle_id}.png")
    main_image.save(filename, "PNG")
    logging.info(f"Saved image: {filename}")
    return filename

def on_message(ws, message):
    global coins_buffer
    try:
        data = json.loads(message)
        if "mint" in data:
            mint_address = data["mint"]
            pumpfun_url = f"https://pump.fun/coin/{mint_address}"
            data["pumpfun_url"] = pumpfun_url

        if "uri" in data and data["uri"]:
            metadata_url = data["uri"]
            try:
                response = requests.get(metadata_url, timeout=5)
                if response.status_code == 200:
                    metadata = response.json()
                    data["metadata_name"] = metadata.get("name", "")
                    data["metadata_symbol"] = metadata.get("symbol", "")
                    data["metadata_description"] = metadata.get("description", "")
                    data["metadata_image"] = metadata.get("image", "")
                    data["twitter"] = metadata.get("twitter", None)     # Extract twitter
                    data["website"] = metadata.get("website", None)     # Extract website
                    if data["metadata_image"]:
                        parts = data["metadata_image"].split("/ipfs/")
                        if len(parts) == 2:
                            image_hash = parts[1]
                            official_image_url = f"https://pump.mypinata.cloud/ipfs/{image_hash}?img-width=256&img-dpr=2&img-onerror=redirect"
                            data["metadata_image_official"] = official_image_url
                        else:
                            data["metadata_image_official"] = data["metadata_image"]
                    else:
                        data["metadata_image_official"] = ""
                else:
                    logging.warning(f"Failed to fetch metadata from {metadata_url}: Status {response.status_code}")
                    data["metadata_name"] = ""
                    data["metadata_symbol"] = ""
                    data["metadata_description"] = ""
                    data["metadata_image_official"] = ""
                    data["twitter"] = None
                    data["website"] = None
            except Exception as e:
                logging.error(f"Error fetching metadata from {metadata_url}: {e}", exc_info=True)
                data["metadata_name"] = ""
                data["metadata_symbol"] = ""
                data["metadata_description"] = ""
                data["metadata_image_official"] = ""
                data["twitter"] = None
                data["website"] = None

        logging.info("New Token Event Received:")
        logging.info(json.dumps(data, indent=4))

        coins_buffer.append(data)

        if len(coins_buffer) == TOTAL_COINS:
            bundle_id = save_bundle_to_db(coins_buffer)
            if bundle_id:
                filename = create_image_for_coins(coins_buffer, bundle_id)
                uploaded_url = upload_to_cloudflare(filename, f"{bundle_id}.png")
                if uploaded_url:
                    # Use public URL from CLOUDFLARE_PUBLIC_URL for the final image_url
                    public_url = f"{os.getenv('CLOUDFLARE_PUBLIC_URL')}/{bundle_id}.png"
                    try:
                        supabase.table('bundles').update({"image_url": public_url}).eq("id", bundle_id).execute()
                        logging.info(f"Updated bundle with public image_url: {public_url}")
                    except Exception as e:
                        logging.error(f"Failed updating bundle image_url: {e}", exc_info=True)
                else:
                    logging.error("Failed to upload image to Cloudflare.")
            else:
                logging.error("No bundle_id retrieved; image not saved.")
            coins_buffer.clear()

    except json.JSONDecodeError:
        logging.error(f"Invalid JSON received: {message}")
    except Exception as e:
        logging.error(f"Error processing message: {e}", exc_info=True)

def on_error(ws, error):
    logging.error(f"WebSocket Error: {error}", exc_info=True)

def on_close(ws, close_status_code, close_msg):
    logging.warning(f"WebSocket Closed. Code: {close_status_code}, Msg: {close_msg}. Reconnecting in 5 seconds...")
    time.sleep(5)
    connect_websocket()

def on_open(ws):
    logging.info("WebSocket Opened. Subscribing to 'subscribeNewToken' events...")
    try:
        payload = {"method": "subscribeNewToken"}
        ws.send(json.dumps(payload))
        logging.info("Subscribed to 'subscribeNewToken' events.")
    except Exception as e:
        logging.error(f"Error during subscription: {e}", exc_info=True)

def connect_websocket():
    logging.info("Connecting to WebSocket...")
    ws = websocket.WebSocketApp(
        API_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

if __name__ == "__main__":
    if not os.path.isfile(FONT_PATH):
        logging.warning(f"Font file '{FONT_PATH}' not found. Using default font.")
    connect_websocket()

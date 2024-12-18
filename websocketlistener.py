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
API_URL = os.getenv("API_URL", "wss://pumpportal.fun/api/data")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("Missing Supabase URL or Key.")
    exit(1)

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logging.error(f"Failed to create Supabase client: {e}", exc_info=True)
    exit(1)

TOTAL_COINS = 8
GRID_COLS = 2
GRID_ROWS = 4
IMG_WIDTH = 512
IMG_HEIGHT = 512
BOX_WIDTH = IMG_WIDTH // GRID_COLS
BOX_HEIGHT = IMG_HEIGHT // GRID_ROWS

FONT_PATH = os.getenv("FONT_PATH", "notosans.ttf")
NAME_START_FONT_SIZE = 16
NAME_MIN_FONT_SIZE = 6
DESC_START_FONT_SIZE = 14
DESC_MIN_FONT_SIZE = 6
LABEL_FONT_SIZE = 14
LABEL_BOX_SIZE = 22
LINE_SPACING = 2

def load_font(path, size):
    """Attempt to load a TTF font, fallback to default if fails."""
    if os.path.isfile(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception as font_err:
            logging.error(f"Failed to load font '{path}' size {size}: {font_err}")
    logging.warning(f"Font '{path}' not found. Using default font.")
    return ImageFont.load_default()

NAME_FONT_DEFAULT = load_font(FONT_PATH, NAME_START_FONT_SIZE)
DESC_FONT_DEFAULT = load_font(FONT_PATH, DESC_START_FONT_SIZE)
LABEL_FONT = load_font(FONT_PATH, LABEL_FONT_SIZE)

coins_buffer = []

def text_dimensions(draw, text, font):
    if not text:
        return 0, 0
    bbox = draw.textbbox((0,0), text, font=font)
    width = bbox[2]-bbox[0]
    height = bbox[3]-bbox[1]
    return width, height

def fit_single_line(draw, text, max_w, max_h, start_size=16, min_size=6):
    """Fit a single line of text into a given box, shrinking if needed."""
    ellipsis = "…"
    for fs in range(start_size, min_size - 1, -1):
        font = load_font(FONT_PATH, fs)
        tw, th = text_dimensions(draw, text, font)
        if th <= max_h:
            if tw <= max_w:
                return text, font
            else:
                # Truncate
                truncated = text
                while truncated and text_dimensions(draw, truncated + ellipsis, font)[0] > max_w:
                    truncated = truncated[:-1]
                if truncated:
                    return truncated + ellipsis, font
    # If not fitting, just return ellipsis at min size
    font = load_font(FONT_PATH, min_size)
    return ellipsis, font

def force_wrap_text(draw, text, font, max_w):
    """Wrap text into multiple lines by force-fitting words and partial words."""
    if not text:
        return []
    lines = []
    words = text.split()
    current_line = ""

    def line_w(t):
        return text_dimensions(draw, t, font)[0]

    def break_long_word(word):
        # Break a long word into chunks
        parts = []
        current_chunk = ""
        for ch in word:
            attempt = current_chunk + ch
            if line_w(attempt) > max_w and current_chunk:
                parts.append(current_chunk)
                current_chunk = ch
            else:
                current_chunk = attempt
        if current_chunk:
            parts.append(current_chunk)
        return parts

    for w in words:
        if line_w(w) > max_w:
            pieces = break_long_word(w)
            for piece in pieces:
                test_line = (current_line + " " + piece).strip() if current_line else piece
                if line_w(test_line) > max_w and current_line:
                    lines.append(current_line)
                    current_line = piece
                else:
                    current_line = test_line
        else:
            test_line = (current_line + " " + w).strip() if current_line else w
            if line_w(test_line) > max_w and current_line:
                lines.append(current_line)
                current_line = w
            else:
                current_line = test_line

    if current_line:
        lines.append(current_line)
    return lines

def fit_description(draw, text, max_w, max_h, start_size=14, min_size=6):
    """Fit a multi-line description inside a specified area."""
    for fs in range(start_size, min_size - 1, -1):
        font = load_font(FONT_PATH, fs)
        wrapped = force_wrap_text(draw, text, font, max_w)
        total_h = sum(text_dimensions(draw, ln, font)[1] for ln in wrapped) + LINE_SPACING*(len(wrapped)-1)
        if total_h <= max_h:
            return wrapped, font
    return None, None

def save_bundle_to_db(coins):
    """Create a new bundle in Supabase and insert coin records."""
    try:
        bundle_res = supabase.table('bundles').insert({}).execute()
        if not bundle_res.data:
            logging.error(f"Failed to insert new bundle: {bundle_res}")
            return None
        bundle_id = bundle_res.data[0]['id']
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
                "metadata_description": coin.get("metadata_description", "")
            }
            coin_res = supabase.table('coins').insert(coin_data).execute()
            if not coin_res.data:
                logging.error(f"Failed to insert coin {coin_id} into bundle {bundle_id}: {coin_res}")
            else:
                logging.info(f"Inserted coin {coin_id} into bundle {bundle_id}")
        return bundle_id
    except Exception as db_err:
        logging.error(f"Error saving bundle to database: {db_err}", exc_info=True)
        return None

def scale_image(img, max_size):
    """Scale image down while preserving aspect ratio."""
    w,h = img.size
    scale = min(max_size/w, max_size/h)
    return img.resize((int(w*scale), int(h*scale)), Resampling.LANCZOS)

def draw_coin_box(draw, main_image, x, y, coin_data, index):
    """Draw a single coin box with metadata onto the main image."""
    draw.rectangle([x,y,x+BOX_WIDTH-1,y+BOX_HEIGHT-1], fill="white", outline="white", width=1)
    draw.rectangle([x+2,y+2,x+BOX_WIDTH-3,y+BOX_HEIGHT-3], outline="red", width=1)

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
                coin_img = scale_image(cimg, max_img_size)
            else:
                logging.warning(f"Failed to fetch image for coin {index+1}: HTTP {resp.status_code}")
        except Exception as img_err:
            logging.error(f"Error fetching coin image for coin {index+1}: {img_err}", exc_info=True)
    else:
        logging.warning(f"No image available for coin {index+1}")

    img_w, img_h = 0,0
    if coin_img:
        img_w,img_h = coin_img.size
        img_y = safe_y+(safe_h - img_h)//2
        main_image.paste(coin_img,(safe_x,img_y),coin_img)

    vertical_offset = 10
    text_start_x = safe_x + img_w + 8
    right_margin = 5

    label_id_text = f"{index+1:02d}"
    label_x = text_start_x
    label_y = safe_y + vertical_offset
    draw.rectangle([label_x,label_y,label_x+LABEL_BOX_SIZE-1,label_y+LABEL_BOX_SIZE-1],
                   fill="white", outline="red", width=1)
    lw,lh = text_dimensions(draw, label_id_text, LABEL_FONT)
    ltx = label_x+(LABEL_BOX_SIZE - lw)//2
    lty = label_y+(LABEL_BOX_SIZE - lh)//2 -4
    draw.text((ltx,lty), label_id_text, fill="red", font=LABEL_FONT)

    name_area_x = label_x + LABEL_BOX_SIZE + 5
    name_area_w = (safe_x+safe_w - right_margin)-name_area_x
    name_area_h = LABEL_BOX_SIZE

    raw_name = (coin_data.get("metadata_name") or "").strip() or "(No Name)"
    symbol = (coin_data.get("metadata_symbol") or "").strip()
    name_line_text = raw_name
    ticker_line_text = f"({symbol})" if symbol else ""

    name_line, name_font = fit_single_line(draw,name_line_text,name_area_w,name_area_h,
                                           start_size=NAME_START_FONT_SIZE,
                                           min_size=NAME_MIN_FONT_SIZE)
    nw, nh = text_dimensions(draw, name_line, name_font)
    name_line_y = label_y+(LABEL_BOX_SIZE - nh)//2 -13
    draw.text((name_area_x,name_line_y), name_line, fill="black", font=name_font)

    if ticker_line_text:
        ticker_line, ticker_font = fit_single_line(draw,ticker_line_text,name_area_w,name_area_h,
                                                   start_size=NAME_START_FONT_SIZE,
                                                   min_size=NAME_MIN_FONT_SIZE)
        tw,th = text_dimensions(draw, ticker_line, ticker_font)
        ticker_line_y = name_line_y + nh + 3
        draw.text((name_area_x,ticker_line_y), ticker_line, fill="black", font=ticker_font)
    else:
        th = 0
        ticker_line_y = name_line_y

    desc_y = ticker_line_y+(th if ticker_line_text else 0)+5
    desc_x = text_start_x
    desc_w = (safe_x+safe_w - right_margin)-desc_x
    desc_h = (safe_y+safe_h)-desc_y

    desc = (coin_data.get("metadata_description") or "").strip()
    if len(desc)>60:
        desc = desc[:60]+"..."

    if desc:
        desc_lines, desc_font = fit_description(draw, desc, desc_w, desc_h,
                                                start_size=DESC_START_FONT_SIZE,
                                                min_size=DESC_MIN_FONT_SIZE)
        if desc_lines is None:
            small_font = load_font(FONT_PATH, MIN_FONT_SIZE)
            draw.text((desc_x,desc_y), "[Desc too long]", fill="black", font=small_font)
        else:
            for dl in desc_lines:
                tw,th = text_dimensions(draw, dl, desc_font)
                draw.text((desc_x,desc_y), dl, fill="black", font=desc_font)
                desc_y += th + LINE_SPACING

def create_image_for_coins(coins, bundle_id):
    """Assemble the main bundle image with coin boxes and their metadata."""
    os.makedirs("bundleimagesmain", exist_ok=True)
    main_image = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (255,255,255,255))
    draw = ImageDraw.Draw(main_image)
    for i, coin in enumerate(coins):
        row = i//GRID_COLS
        col = i%GRID_COLS
        x = col*BOX_WIDTH
        y = row*BOX_HEIGHT
        draw_coin_box(draw, main_image, x, y, coin, i)
    filename = os.path.join("bundleimagesmain", f"{bundle_id}.png")
    main_image.save(filename,"PNG")
    logging.info(f"Saved main image for bundle {bundle_id}: {filename}")
    return filename

def on_message(ws, message):
    """Process incoming WebSocket messages representing new token events."""
    global coins_buffer
    try:
        data = json.loads(message)
        if "mint" in data:
            mint_addr = data["mint"]
            data["pumpfun_url"] = f"https://pump.fun/coin/{mint_addr}"

        # Fetch metadata if uri present
        if "uri" in data and data["uri"]:
            meta_url = data["uri"]
            try:
                resp = requests.get(meta_url, timeout=5)
                if resp.status_code == 200:
                    metadata = resp.json()
                    data["metadata_name"] = metadata.get("name","")
                    data["metadata_symbol"] = metadata.get("symbol","")
                    data["metadata_description"] = metadata.get("description","")
                    data["metadata_image"] = metadata.get("image","")
                    if data["metadata_image"]:
                        parts = data["metadata_image"].split("/ipfs/")
                        if len(parts)==2:
                            image_hash = parts[1]
                            official_url = f"https://pump.mypinata.cloud/ipfs/{image_hash}?img-width=256&img-dpr=2&img-onerror=redirect"
                            data["metadata_image_official"] = official_url
                        else:
                            data["metadata_image_official"] = data["metadata_image"]
                    else:
                        data["metadata_image_official"] = ""
                else:
                    logging.warning(f"Failed to fetch metadata from {meta_url}: HTTP {resp.status_code}")
                    data["metadata_name"] = ""
                    data["metadata_symbol"] = ""
                    data["metadata_description"] = ""
                    data["metadata_image_official"] = ""
            except Exception as meta_err:
                logging.error(f"Error fetching metadata from {meta_url}: {meta_err}", exc_info=True)
                data["metadata_name"] = ""
                data["metadata_symbol"] = ""
                data["metadata_description"] = ""
                data["metadata_image_official"] = ""

        logging.info("New Token Event:")
        logging.info(json.dumps(data, indent=4))
        coins_buffer.append(data)

        if len(coins_buffer)==TOTAL_COINS:
            # Save bundle and its coins
            bundle_id = save_bundle_to_db(coins_buffer)
            if bundle_id:
                filename = create_image_for_coins(coins_buffer, bundle_id)
                uploaded_url = upload_to_cloudflare(filename, f"{bundle_id}.png")
                if uploaded_url:
                    public_url = f"{os.getenv('CLOUDFLARE_PUBLIC_URL')}/{bundle_id}.png"
                    try:
                        supabase.table('bundles').update({"image_url": public_url}).eq("id", bundle_id).execute()
                        logging.info(f"Updated bundle {bundle_id} with image_url: {public_url}")
                    except Exception as update_err:
                        logging.error(f"Failed updating bundle image_url: {update_err}", exc_info=True)
                else:
                    logging.error("Failed to upload image to Cloudflare.")
            else:
                logging.error("No bundle_id retrieved; bundle not saved properly.")
            coins_buffer.clear()

    except json.JSONDecodeError:
        logging.error(f"Invalid JSON received: {message}")
    except Exception as e:
        logging.error(f"Error processing message: {e}", exc_info=True)

def on_error(ws, error):
    logging.error(f"WebSocket error: {error}", exc_info=True)

def on_close(ws, close_status_code, close_msg):
    logging.warning(f"WebSocket closed. Code: {close_status_code}, Msg: {close_msg}. Reconnecting in 5s...")
    time.sleep(5)
    connect_websocket()

def on_open(ws):
    logging.info("WebSocket opened. Subscribing to 'subscribeNewToken' events...")
    try:
        payload = {"method":"subscribeNewToken"}
        ws.send(json.dumps(payload))
        logging.info("Subscribed to 'subscribeNewToken'.")
    except Exception as e:
        logging.error(f"Error subscribing to event: {e}", exc_info=True)

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

if __name__=="__main__":
    if not os.path.isfile(FONT_PATH):
        logging.warning(f"Font file '{FONT_PATH}' not found. Using default font.")
    connect_websocket()

from flask import Flask, request, send_file
from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Resampling
import requests
import io
import os
import logging

app = Flask(__name__)

# Configuration and Constants
TOTAL_COINS = 8
GRID_COLS = 2
GRID_ROWS = 4
IMG_WIDTH = 512
IMG_HEIGHT = 512
BOX_WIDTH = IMG_WIDTH // GRID_COLS
BOX_HEIGHT = IMG_HEIGHT // GRID_ROWS

FONT_PATH = "notosans.ttf"  # Ensure the font file is present
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 6
NAME_START_FONT_SIZE = 16
NAME_MIN_FONT_SIZE = 6
DESC_START_FONT_SIZE = 14
DESC_MIN_FONT_SIZE = 6
LABEL_BOX_SIZE = 22
LINE_SPACING = 2
LABEL_FONT_SIZE = 14

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

def load_font(font_path, size):
    if font_path and os.path.isfile(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except:
            pass
    return ImageFont.load_default()

NAME_FONT_DEFAULT = load_font(FONT_PATH, NAME_START_FONT_SIZE)
DESC_FONT_DEFAULT = load_font(FONT_PATH, DESC_START_FONT_SIZE)
LABEL_FONT = load_font(FONT_PATH, LABEL_FONT_SIZE)

def text_size(draw, text, font):
    if not text:
        return 0,0
    bbox = draw.textbbox((0,0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
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

def scale_image_keep_aspect(img, max_size):
    w,h = img.size
    scale = min(max_size/w, max_size/h)
    return img.resize((int(w*scale), int(h*scale)), Resampling.LANCZOS)

def draw_coin_box(draw, main_image, x, y, coin_data, index):
    draw.rectangle([x, y, x+BOX_WIDTH-1, y+BOX_HEIGHT-1], fill="white", outline="white", width=1)
    draw.rectangle([x+2, y+2, x+BOX_WIDTH-3, y+BOX_HEIGHT-3], outline="red", width=1)

    margin = 5
    safe_x = x + margin
    safe_y = y + margin
    safe_w = BOX_WIDTH - 2 * margin
    safe_h = BOX_HEIGHT - 2 * margin

    image_size = 100
    coin_img = None
    coin_img_url = coin_data.get("metadata_image_official","")
    if coin_img_url:
        try:
            resp = requests.get(coin_img_url, timeout=5)
            if resp.status_code == 200:
                cimg = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                max_img_size = min(image_size, safe_h)
                coin_img = scale_image_keep_aspect(cimg, max_img_size)
        except:
            pass

    img_w = img_h = 0
    if coin_img:
        img_w, img_h = coin_img.size
        img_y = safe_y + (safe_h - img_h)//2
        main_image.paste(coin_img, (safe_x, img_y), coin_img)

    vertical_offset = 10
    text_start_x = safe_x + img_w + 8
    right_margin = 5

    label_id_text = f"{index+1:02d}"
    label_x = text_start_x
    label_y = safe_y + vertical_offset

    draw.rectangle([label_x, label_y, label_x + LABEL_BOX_SIZE -1, label_y + LABEL_BOX_SIZE -1],
                   fill="white", outline="red", width=1)
    lw, lh = text_size(draw, label_id_text, LABEL_FONT)
    ltx = label_x + (LABEL_BOX_SIZE - lw)//2
    lty = label_y + (LABEL_BOX_SIZE - lh)//2 -4
    draw.text((ltx, lty), label_id_text, fill="red", font=LABEL_FONT)

    name_area_x = label_x + LABEL_BOX_SIZE + 5
    name_area_w = (safe_x + safe_w - right_margin) - name_area_x
    name_area_h = LABEL_BOX_SIZE

    raw_name = (coin_data.get("metadata_name") or "").strip() or "(No Name)"
    symbol = (coin_data.get("metadata_symbol") or "").strip()

    name_line_text = raw_name
    ticker_line_text = f"({symbol})" if symbol else ""

    name_line, name_font = fit_single_line(draw, name_line_text, name_area_w, name_area_h,
                                           start_font_size=NAME_START_FONT_SIZE, min_font_size=NAME_MIN_FONT_SIZE)
    nw, nh = text_size(draw, name_line, name_font)
    name_line_y = label_y + (LABEL_BOX_SIZE - nh)//2 -13
    draw.text((name_area_x, name_line_y), name_line, fill="black", font=name_font)

    if ticker_line_text:
        ticker_line, ticker_font = fit_single_line(draw, ticker_line_text, name_area_w, name_area_h,
                                                   start_font_size=NAME_START_FONT_SIZE, min_font_size=NAME_MIN_FONT_SIZE)
        tw, th = text_size(draw, ticker_line, ticker_font)
        ticker_line_y = name_line_y + nh + 3
        draw.text((name_area_x, ticker_line_y), ticker_line, fill="black", font=ticker_font)
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
        desc_lines, desc_font = fit_description(draw, desc, desc_w, desc_h,
                                                start_font_size=DESC_START_FONT_SIZE,
                                                min_font_size=DESC_MIN_FONT_SIZE)
        if desc_lines is None:
            small_font = load_font(FONT_PATH, MIN_FONT_SIZE)
            draw.text((desc_x, desc_y), "[Desc too long]", fill="black", font=small_font)
        else:
            for dl in desc_lines:
                tw, th = text_size(draw, dl, desc_font)
                draw.text((desc_x, desc_y), dl, fill="black", font=desc_font)
                desc_y += th + 2

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/generate", methods=["POST"])
def generate_image():
    data = request.json
    coins = data.get("coins", [])
    while len(coins) < TOTAL_COINS:
        coins.append({
            "metadata_name": "",
            "metadata_symbol": "",
            "metadata_description": "",
            "metadata_image_official": ""
        })

    main_image = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (255, 255, 255, 255))
    draw = ImageDraw.Draw(main_image)
    for i, coin in enumerate(coins):
        row = i // GRID_COLS
        col = i % GRID_COLS
        x = col * BOX_WIDTH
        y = row * BOX_HEIGHT
        draw_coin_box(draw, main_image, x, y, coin, i)

    img_bytes = io.BytesIO()
    main_image.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return send_file(img_bytes, mimetype='image/png', as_attachment=True, download_name='coins_bundle.png')

if __name__ == "__main__":
    app.run(debug=True)

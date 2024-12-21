# File: newcoincheck.py

import time
import logging
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

logging.basicConfig(level=logging.INFO)

load_dotenv()  # to load SUPABASE_URL, SUPABASE_KEY, etc.

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NODE_SERVER_URL = os.getenv("NODE_SERVER_URL", "http://localhost:3000")
WATERMILL_FLASK_URL = os.getenv("WATERMILL_FLASK_URL", "http://localhost:5000")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.error("Missing Supabase credentials.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

currently_processing_coin = False


def main_loop():
    global currently_processing_coin

    while True:
        if not currently_processing_coin:
            try:
                coin_to_process = find_unprocessed_coin()
                if coin_to_process:
                    currently_processing_coin = True
                    process_goodcoin(coin_to_process)
                    currently_processing_coin = False
                else:
                    # nothing to do
                    pass
            except Exception as e:
                logging.error(f"Error in main loop: {e}", exc_info=True)
                currently_processing_coin = False

        time.sleep(5)


def find_unprocessed_coin():
    """
    Finds the oldest row in 'goodcoins' where processed=false
    """
    try:
        resp = supabase.table('goodcoins') \
            .select("*") \
            .eq('processed', False) \
            .order('created_at', desc=False) \
            .limit(1) \
            .execute()
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
    except Exception as e:
        logging.error(f"Error finding unprocessed coin: {e}", exc_info=True)
    return None


def process_goodcoin(goodcoin_row):
    goodcoin_uuid = goodcoin_row['id']
    coin_uuid = goodcoin_row['coin_uuid']
    logging.info(f"Processing goodcoin row_id={goodcoin_uuid}, coin_uuid={coin_uuid}")

    # 1) fetch the matching row from 'coins'
    coin_data = get_coin_data_by_uuid(coin_uuid)
    if not coin_data:
        logging.warning(f"No coin data found for coin_uuid={coin_uuid}. Marking as error.")
        mark_goodcoin_processed(goodcoin_uuid, "error")
        return

    # We'll show the coin image in the watermill
    image_url = goodcoin_row.get('cloudflareimage')
    if image_url:
        start_investigation(image_url)

    text_coin_id = coin_data.get('coin_id', '???')

    # 2) Google Lens screenshot
    meta_image_url = coin_data.get('metadata_image_official')
    if not meta_image_url:
        logging.warning(f"No metadata_image_official for coin_uuid={coin_uuid}. Disqualifying.")
        mark_goodcoin_processed(goodcoin_uuid, "bad")
        emit_disqualified_event(text_coin_id)
        stop_investigation()
        return

    lens_screenshot_url = do_google_lens_screenshot(meta_image_url)
    if not lens_screenshot_url:
        logging.warning("Google Lens screenshot failed. Disqualifying coin.")
        mark_goodcoin_processed(goodcoin_uuid, "bad")
        emit_disqualified_event(text_coin_id)
        stop_investigation()
        return

    # 3) run GPT check for "copy"|"unique"
    lens_judgment = call_sysprompt_lens_openai(lens_screenshot_url)
    if not lens_judgment:
        lens_judgment = "copy"  # default if something broke

    if lens_judgment == "copy":
        logging.info(f"Coin {text_coin_id} => 'copy' => disqualified.")
        mark_goodcoin_processed(goodcoin_uuid, "bad")
        emit_disqualified_event(text_coin_id)
        stop_investigation()
        return
    elif lens_judgment == "unique":
        logging.info(f"Coin {text_coin_id} => 'unique' => proceed with Twitter flow.")
        twitter_url = coin_data.get('twitter')
        if not twitter_url:
            logging.warning(f"No twitter URL for coin_uuid={coin_uuid}, disqualifying.")
            mark_goodcoin_processed(goodcoin_uuid, "bad")
            emit_disqualified_event(text_coin_id)
            stop_investigation()
            return

        tw_screenshot_url = do_twitter_screenshot(twitter_url)
        if not tw_screenshot_url:
            logging.warning("Twitter screenshot failed. Disqualifying coin.")
            mark_goodcoin_processed(goodcoin_uuid, "bad")
            emit_disqualified_event(text_coin_id)
            stop_investigation()
            return

        final_judgment = call_sysprompt_finaldecision_openai(tw_screenshot_url)
        if not final_judgment:
            final_judgment = "pass"

        if final_judgment == "pass":
            logging.info(f"Coin {text_coin_id} => final pass => disqualified.")
            mark_goodcoin_processed(goodcoin_uuid, "bad")
            emit_disqualified_event(text_coin_id)
            stop_investigation()
            return
        elif final_judgment == "buy":
            logging.info(f"Coin {text_coin_id} => final buy => calling buy script.")
            do_buy_coin(coin_data)
            mark_goodcoin_processed(goodcoin_uuid, "buy")
            stop_investigation()
            return
        else:
            logging.warning(f"Unknown final_judgment={final_judgment}, default pass.")
            mark_goodcoin_processed(goodcoin_uuid, "bad")
            emit_disqualified_event(text_coin_id)
            stop_investigation()
            return
    else:
        logging.warning(f"Unknown lens_judgment={lens_judgment}, default copy => disqualified.")
        mark_goodcoin_processed(goodcoin_uuid, "bad")
        emit_disqualified_event(text_coin_id)
        stop_investigation()


def get_coin_data_by_uuid(coin_uuid):
    try:
        resp = supabase.table('coins').select("*").eq('id', coin_uuid).execute()
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
    except Exception as e:
        logging.error(f"Error fetching coin data for coin_uuid={coin_uuid}: {e}", exc_info=True)
    return None


def do_google_lens_screenshot(image_url):
    try:
        payload = {"imageUrl": image_url}
        res = requests.post(f"{NODE_SERVER_URL}/api/lens-screenshot", json=payload, timeout=120)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                return data.get("cloudflareUrl")
    except Exception as e:
        logging.error(f"Error in do_google_lens_screenshot: {e}", exc_info=True)
    return None


def do_twitter_screenshot(twitter_url):
    try:
        payload = {"twitterUrl": twitter_url}
        res = requests.post(f"{NODE_SERVER_URL}/api/twitter-screenshot", json=payload, timeout=120)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                return data.get("cloudflareUrl")
    except Exception as e:
        logging.error(f"Error in do_twitter_screenshot: {e}", exc_info=True)
    return None


def call_sysprompt_lens_openai(screenshot_url):
    try:
        from sysprompt_lens_openai import run_lens_check
        return run_lens_check(screenshot_url)
    except Exception as e:
        logging.error(f"Error calling sysprompt_lens_openai: {e}", exc_info=True)
    return None


def call_sysprompt_finaldecision_openai(screenshot_url):
    try:
        from sysprompt_finaldecision_openai import run_finaldecision_check
        return run_finaldecision_check(screenshot_url)
    except Exception as e:
        logging.error(f"Error calling sysprompt_finaldecision_openai: {e}", exc_info=True)
    return None


def do_buy_coin(coin_data):
    import subprocess
    mint = coin_data.get("mint", "")
    try:
        subprocess.run(["python", "buy_placeholder.py", mint], check=True)
    except Exception as e:
        logging.error(f"Error calling buy_placeholder script: {e}", exc_info=True)


def mark_goodcoin_processed(goodcoin_id, quality_value):
    try:
        supabase.table('goodcoins').update({
            "processed": True,
            "quality": quality_value
        }).eq("id", goodcoin_id).execute()
    except Exception as e:
        logging.error(f"Error updating goodcoin {goodcoin_id}: {e}", exc_info=True)


def emit_disqualified_event(coin_text_id):
    if not coin_text_id:
        coin_text_id = "???"
    try:
        requests.post(f"{WATERMILL_FLASK_URL}/disqualify_coin",
                      json={"coin_id": coin_text_id},
                      timeout=10)
    except Exception as e:
        logging.error(f"Failed to emit disqualified event for coin_id={coin_text_id}: {e}")


def start_investigation(image_url):
    try:
        requests.post(f"{WATERMILL_FLASK_URL}/start_investigation",
                      json={"image_url": image_url},
                      timeout=10)
    except Exception as e:
        logging.error(f"Failed to start_investigation with {image_url}: {e}")


def stop_investigation():
    try:
        requests.post(f"{WATERMILL_FLASK_URL}/stop_investigation",
                      json={},
                      timeout=10)
    except Exception as e:
        logging.error(f"Failed to stop_investigation: {e}")


if __name__ == "__main__":
    main_loop()

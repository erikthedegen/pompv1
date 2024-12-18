import os
import json
import logging
import time
import redis
from supabase import create_client, Client
from dotenv import load_dotenv

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

def enqueue_new_bundles():
    """Continuously polls supabase for new unprocessed bundles and puts them into Redis queue."""
    logging.info("Starting to continuously enqueue new bundles...")
    while True:
        try:
            response = supabase.table('bundles').select('*').eq('processed', False).execute()
            bundles = response.data
            if not bundles:
                # No new unprocessed bundles
                time.sleep(10)
                continue
            for b in bundles:
                image_url = b.get('image_url')
                if image_url:
                    item = {
                        "bundle_id": b['id'],
                        "image_url": image_url
                    }
                    r.rpush("bundle_queue", json.dumps(item))
                    supabase.table('bundles').update({"processed": True}).eq("id", b['id']).execute()
                    logging.info(f"Enqueued bundle {b['id']} into queue.")
                else:
                    logging.warning(f"Bundle {b['id']} has no image_url, skipping.")
            time.sleep(5)
        except Exception as e:
            logging.error(f"Error enqueuing bundles: {e}", exc_info=True)
            time.sleep(10)

if __name__ == "__main__":
    enqueue_new_bundles()

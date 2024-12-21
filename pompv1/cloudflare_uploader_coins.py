# File: pompv1/cloudflare_uploader_coins.py

import os
import logging
import boto3

def upload_yes_coin_png(file_path, file_name):
    """
    Uploads a single "yes" coin PNG file to Cloudflare R2 
    using a publicly accessible domain (e.g. CLOUDFLARE_PUBLIC_COINS).
    
    Returns the final "friendly" public URL or None on error.
    """
    CLOUDFLARE_BUCKET = os.getenv("CLOUDFLARE_BUCKET")
    CLOUDFLARE_ENDPOINT = os.getenv("CLOUDFLARE_ENDPOINT")
    CLOUDFLARE_ACCESS_KEY = os.getenv("CLOUDFLARE_ACCESS_KEY")
    CLOUDFLARE_SECRET_KEY = os.getenv("CLOUDFLARE_SECRET_KEY")

    # Provide a separate environment variable for the coins domain 
    # if you’d like, or reuse CLOUDFLARE_PUBLIC_URL. 
    CLOUDFLARE_PUBLIC_COINS = os.getenv("CLOUDFLARE_PUBLIC_COINS")

    if not all([CLOUDFLARE_BUCKET, CLOUDFLARE_ENDPOINT, 
                CLOUDFLARE_ACCESS_KEY, CLOUDFLARE_SECRET_KEY, 
                CLOUDFLARE_PUBLIC_COINS]):
        logging.warning("Coin uploader: missing some Cloudflare env variables. Skipping upload.")
        return None

    if not os.path.isfile(file_path):
        logging.error(f"Coin uploader: File not found => {file_path}")
        return None

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=CLOUDFLARE_ENDPOINT,
            aws_access_key_id=CLOUDFLARE_ACCESS_KEY,
            aws_secret_access_key=CLOUDFLARE_SECRET_KEY
        )

        # Mark file as publicly readable
        s3.upload_file(
            file_path, 
            CLOUDFLARE_BUCKET, 
            file_name,
            ExtraArgs={"ACL": "public-read"}
        )

        # Return a friendlier public domain link
        final_url = f"{CLOUDFLARE_PUBLIC_COINS}/{file_name}"
        logging.info(f"Coin uploader: {file_name} => {final_url}")
        return final_url

    except Exception as e:
        logging.error(f"Coin uploader: Error uploading {file_name} => {e}", exc_info=True)
        return None

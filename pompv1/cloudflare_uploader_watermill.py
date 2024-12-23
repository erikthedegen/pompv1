# File: pompv1/cloudflare_uploader_watermill.py

import os
import logging
import boto3

def upload_watermill_coin(file_path, file_name):
    """
    Uploads a single coin PNG file for the watermill feed to Cloudflare R2.
    Returns the public URL (friendly domain) or None on error.
    Must store that URL in the 'coins.watermillcoins' column eventually.
    """
    CLOUDFLARE_BUCKET = os.getenv("CLOUDFLARE_BUCKET")
    CLOUDFLARE_ENDPOINT = os.getenv("CLOUDFLARE_ENDPOINT")
    CLOUDFLARE_ACCESS_KEY = os.getenv("CLOUDFLARE_ACCESS_KEY")
    CLOUDFLARE_SECRET_KEY = os.getenv("CLOUDFLARE_SECRET_KEY")
    # Potentially the same public domain as coins or lens,
    # but you can separate if you want:
    CLOUDFLARE_PUBLIC_URL = os.getenv("CLOUDFLARE_PUBLIC_URL")

    if not all([CLOUDFLARE_BUCKET, CLOUDFLARE_ENDPOINT,
                CLOUDFLARE_ACCESS_KEY, CLOUDFLARE_SECRET_KEY,
                CLOUDFLARE_PUBLIC_URL]):
        logging.warning("Missing some Cloudflare env variables for watermill upload. Skipping.")
        return None

    if not os.path.isfile(file_path):
        logging.error(f"Watermill coin file not found => {file_path}")
        return None

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=CLOUDFLARE_ENDPOINT,
            aws_access_key_id=CLOUDFLARE_ACCESS_KEY,
            aws_secret_access_key=CLOUDFLARE_SECRET_KEY
        )

        # Make the file public
        s3.upload_file(
            file_path,
            CLOUDFLARE_BUCKET,
            file_name,
            ExtraArgs={"ACL": "public-read"}
        )

        final_url = f"{CLOUDFLARE_PUBLIC_URL}/{file_name}"
        logging.info(f"Uploaded watermill coin: {file_name} => {final_url}")
        return final_url

    except Exception as e:
        logging.error(f"Error uploading watermill coin {file_name} => {e}", exc_info=True)
        return None

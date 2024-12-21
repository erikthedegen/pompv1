# File: pompv1/cloudflare_uploader_lens.py

import os
import logging
import boto3

def upload_lens_screenshot(file_path, file_name):
    """
    Uploads a screenshot to Cloudflare R2 but returns a *different* public URL 
    than the existing cloudflare_uploader.py, so that lens screenshots 
    can be fetched by OpenAI.
    """
    CLOUDFLARE_BUCKET = os.getenv("CLOUDFLARE_BUCKET")
    CLOUDFLARE_ENDPOINT = os.getenv("CLOUDFLARE_ENDPOINT")  # e.g. https://<accountid>.r2.cloudflarestorage.com
    CLOUDFLARE_ACCESS_KEY = os.getenv("CLOUDFLARE_ACCESS_KEY")
    CLOUDFLARE_SECRET_KEY = os.getenv("CLOUDFLARE_SECRET_KEY")

    # This is the *public domain* for lens screenshots
    # e.g. "https://pub-b5cefcef71fd44ebbff09a494fc31b31.r2.dev"
    CLOUDFLARE_PUBLIC_LENS = os.getenv("CLOUDFLARE_PUBLIC_LENS")  

    if not all([CLOUDFLARE_BUCKET, CLOUDFLARE_ENDPOINT, CLOUDFLARE_ACCESS_KEY, 
                CLOUDFLARE_SECRET_KEY, CLOUDFLARE_PUBLIC_LENS]):
        logging.warning("Cloudflare credentials or lens public domain missing. Skipping lens upload.")
        return None

    if not os.path.isfile(file_path):
        logging.error(f"Lens screenshot not found: {file_path}")
        return None

    try:
        s3 = boto3.client(
            's3',
            endpoint_url=CLOUDFLARE_ENDPOINT,
            aws_access_key_id=CLOUDFLARE_ACCESS_KEY,
            aws_secret_access_key=CLOUDFLARE_SECRET_KEY
        )
        # Make object publicly readable
        s3.upload_file(file_path, CLOUDFLARE_BUCKET, file_name, ExtraArgs={'ACL': 'public-read'})

        # Return a public domain link
        final_url = f"{CLOUDFLARE_PUBLIC_LENS}/{file_name}"
        logging.info(f"Uploaded lens screenshot => {final_url}")
        return final_url

    except Exception as e:
        logging.error(f"Error uploading lens screenshot to Cloudflare: {e}", exc_info=True)
        return None

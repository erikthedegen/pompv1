# File: pompv1/cloudflare_uploader.py
import os
import logging

def upload_to_cloudflare(file_path, file_name):
    CLOUDFLARE_BUCKET = os.getenv("CLOUDFLARE_BUCKET")
    CLOUDFLARE_ENDPOINT = os.getenv("CLOUDFLARE_ENDPOINT")
    CLOUDFLARE_ACCESS_KEY = os.getenv("CLOUDFLARE_ACCESS_KEY")
    CLOUDFLARE_SECRET_KEY = os.getenv("CLOUDFLARE_SECRET_KEY")

    if not all([CLOUDFLARE_BUCKET, CLOUDFLARE_ENDPOINT, CLOUDFLARE_ACCESS_KEY, CLOUDFLARE_SECRET_KEY]):
        logging.warning("Cloudflare credentials or bucket/endpoint missing. Skipping upload.")
        return None

    try:
        import boto3
    except ImportError:
        logging.error("boto3 not installed. Please `pip install boto3`.")
        return None

    if not os.path.isfile(file_path):
        logging.error(f"File not found: {file_path}")
        return None

    try:
        s3 = boto3.client('s3',
                          endpoint_url=CLOUDFLARE_ENDPOINT,
                          aws_access_key_id=CLOUDFLARE_ACCESS_KEY,
                          aws_secret_access_key=CLOUDFLARE_SECRET_KEY)
        s3.upload_file(file_path, CLOUDFLARE_BUCKET, file_name)
        url = f"{CLOUDFLARE_ENDPOINT}/{CLOUDFLARE_BUCKET}/{file_name}"
        logging.info(f"Uploaded {file_name} to Cloudflare R2: {url}")
        return url
    except Exception as e:
        logging.error(f"Error uploading to Cloudflare: {e}", exc_info=True)
        return None

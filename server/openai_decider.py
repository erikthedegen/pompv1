import os
import json
import logging
from openai import OpenAI
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    logging.error("OPENAI_API_KEY not set.")

client = OpenAI()

def get_decision(bundle_id, image_url, coin_info_list):
    system_prompt = """
You are a memecoin expert. You see an image with 8 memecoins arranged in a 2x4 grid (IDs 01 to 08).
For each coin, I have provided its name, symbol, and description.

The image is provided as well. Analyze the image and the provided metadata and determine which coins have strong potential ("yes") and which are low potential ("no").

Return strictly a JSON object with a key "decisions" that is an array of 8 objects. Each object:
{
  "id": "01",
  "decision": "yes" or "no"
}

No extra text, just the JSON object.
    """.strip()

    # Build the user message:
    # We'll provide the coin data and also attach the image.
    user_message_content = []
    # Add a text prompt explaining what we want
    user_message_content.append({
        "type": "text",
        "text": "Given the following coins and the image, determine their potential:"
    })

    # Add the image to the user message
    user_message_content.append({
        "type": "image_url",
        "image_url": {
            "url": image_url,
            "detail": "auto"  # you can choose "low", "high", or "auto"
        }
    })

    # Add coins data as text
    coin_data_str = "Coin Metadata:\n"
    for c in coin_info_list:
        coin_data_str += f"ID: {c['id']}\nName: {c.get('name','')}\nSymbol: {c.get('symbol','')}\nDescription: {c.get('description','')}\n\n"

    user_message_content.append({
        "type": "text",
        "text": coin_data_str.strip()
    })

    # Define schema
    decision_schema = {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "decision": {"type": "string", "enum": ["yes", "no"]}
                    },
                    "required": ["id", "decision"],
                    "additionalProperties": False
                },
                "additionalProperties": False
            }
        },
        "required": ["decisions"],
        "additionalProperties": False
    }

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message_content}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "decision_schema",
                    "schema": decision_schema,
                    "strict": True
                }
            },
            max_tokens=200
        )

        msg = response.choices[0].message
        if msg.refusal:
            logging.error(f"OpenAI refused the request for bundle {bundle_id}: {msg.refusal}")
            return None

        parsed = msg.parsed
        if not parsed:
            logging.error(f"OpenAI response for bundle {bundle_id} did not return parsed content.")
            return None

        decisions = parsed.get("decisions")
        # Check that decisions is a list of length 8
        if isinstance(decisions, list) and len(decisions) == 8:
            return decisions
        else:
            logging.error(f"OpenAI response does not have expected 8 decisions for bundle {bundle_id}. Got: {decisions}")
            return None
    except Exception as e:
        logging.error(f"OpenAI error for bundle {bundle_id}: {e}", exc_info=True)
        return None

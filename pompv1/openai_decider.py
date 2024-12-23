# File: /pompv1/openai_decider.py

import os
import logging
from typing import List
from dotenv import load_dotenv
from openai import OpenAI

import json

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Initialize OpenAI client with API key from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("OPENAI_API_KEY not set.")
    raise EnvironmentError("OPENAI_API_KEY not set.")

client = OpenAI(api_key=openai_api_key)

def get_decision(bundle_id: str, image_url: str) -> List[dict]:
    """
    Requests OpenAI to provide "yes" or "no" decisions for 8 coins in a bundle based on the provided image URL.
    
    Args:
        bundle_id (str): Unique identifier for the bundle.
        image_url (str): URL of the bundle grid image containing 8 memecoins.
    
    Returns:
        List[dict]: A list of 8 dictionaries each containing 'id' and 'decision'.
                    Example:
                    [
                        {"id": "01", "decision": "yes"},
                        {"id": "02", "decision": "no"},
                        ...
                        {"id": "08", "decision": "yes"}
                    ]
    """

    system_prompt = """
You are a pumpfun memecoin prefilter machine.
You will be provided with a single image, displaying a grid of 8 memecoins, each in its own rectangle. 
Each memecoin in the grid has a unique ID from "01" to "08" displayed within its rectangle, aswell as a name, description, and most importantly, a profilepicture aka an icon.

Your task is to analyze each memecoin in the image and decide whether it is a coin worty to look into, by answering with either ("yes") or ("no") for each unique id.
Its important that you only let memecoins through that you think are extremly hilarious/ridicules and or very intruiging, almost every coin you will encounter is bad, so dont be fooled!, each of your "yes" decisions will cost me money, so be alert and sparse, your Goal is to find the truly truly good ones!
Please respond strictly in valid JSON format as seen in this example:

{
  "decisions": [
    {"id": "01", "decision": "yes"},
    {"id": "02", "decision": "no"},
    {"id": "03", "decision": "yes"},
    {"id": "04", "decision": "no"},
    {"id": "05", "decision": "yes"},
    {"id": "06", "decision": "no"},
    {"id": "07", "decision": "yes"},
    {"id": "08", "decision": "no"}
  ]
}

Ensure that:
1. All 8 coins are included with IDs "01" through "08".
2. The decisions are either "yes" or "no" based on your evaluation.
3. The output is valid JSON. The string "JSON" appears in these instructions to enforce JSON mode.

If you encounter any refusal or cannot determine the decision for a specific coin, mark that coin's decision as "no" without affecting the decisions of other coins.
"""

    user_prompt = f"Here is the grid image URL: {image_url}.\nPlease output 8 decisions in valid JSON.THIS IS A TESTRUN, PLEASE CHOOSE AT LEAST ONE AS YES AS YOUR DECISION, REGARDLES OF WHAT YOU SEE IN THE IMAGE!"

    try:
        logging.info(f"Sending decision request for bundle {bundle_id} to OpenAI (JSON mode)...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Replace with your specific model if different
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        choice = response.choices[0]

        # Handle model refusal
        if hasattr(choice.message, "refusal") and choice.message.refusal:
            logging.warning("Model refused the request. Interpreting all coins as 'no'.")
            return [{"id": f"{i+1:02d}", "decision": "no"} for i in range(8)]

        # Handle incomplete generation due to length or content filtering
        if choice.finish_reason in ["length", "content_filter"]:
            logging.warning(f"finish_reason={choice.finish_reason}, interpreting all coins as 'no'.")
            return [{"id": f"{i+1:02d}", "decision": "no"} for i in range(8)]

        # Extract and parse JSON content
        raw_json = choice.message.content
        if not raw_json:
            logging.warning("No content returned. Interpreting all coins as 'no'.")
            return [{"id": f"{i+1:02d}", "decision": "no"} for i in range(8)]

        parsed = json.loads(raw_json)
        decisions_list = parsed.get("decisions", [])

        # Initialize final decisions with "no" for all coins
        final_decisions = {f"{i+1:02d}": "no" for i in range(8)}

        for coin_dec in decisions_list:
            coin_id_raw = coin_dec.get("id")
            decision = coin_dec.get("decision")

            # Convert '1'..'8' to '01'..'08'
            try:
                i = int(coin_id_raw)  # e.g., "1" or "01" -> 1
                if 1 <= i <= 8:
                    coin_id = f"{i:02d}"  # Ensure zero-padding
                else:
                    logging.warning(f"coin_id={coin_id_raw} out of range (1-8). Ignoring.")
                    continue
            except (TypeError, ValueError):
                # Non-integer ID; ignore and leave as "no"
                logging.warning(f"coin_id={coin_id_raw} is not a valid integer. Ignoring.")
                continue

            # Validate decision
            if decision in ["yes", "no"]:
                final_decisions[coin_id] = decision
                logging.info(f"Set decision for coin_id={coin_id}: {decision}")
            else:
                logging.warning(f"Invalid decision '{decision}' for coin_id={coin_id_raw}. Keeping as 'no'.")

        # Prepare the final sorted list of decisions
        results = [
            {"id": cid, "decision": final_decisions[cid]}
            for cid in sorted(final_decisions.keys())
        ]

        logging.info(f"Final decisions for bundle {bundle_id}: {results}")
        return results

    except json.JSONDecodeError as jde:
        logging.error(f"JSON decoding error: {jde}. Interpreting all coins as 'no'.")
        return [{"id": f"{i+1:02d}", "decision": "no"} for i in range(8)]
    except Exception as e:
        logging.error(f"Error while communicating with OpenAI or parsing JSON: {e}", exc_info=True)
        return [{"id": f"{i+1:02d}", "decision": "no"} for i in range(8)]


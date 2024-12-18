import os
import openai
import json
import logging

openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    logging.error("OPENAI_API_KEY not set.")

def get_decision(bundle_id, image_url, coin_info_list):
    """
    Sends a prompt to the OpenAI API to get 'yes'/'no' decisions for each coin.
    Uses structured outputs to ensure a strict JSON format: array of 8 objects {id, decision}.
    """
    system_prompt = """
You are a memecoin expert. You see an image with 8 memecoins arranged in a 2x4 grid (IDs 01 to 08).
For each coin, I have provided its name, symbol, and description.
Analyze them and determine which have strong potential ("yes") and which have low potential ("no").
Return strictly a JSON array of 8 objects. Each object:
{
  "id": "01",
  "decision": "yes" or "no"
}
No extra text.
    """.strip()

    user_message = "Coins data:\n"
    for c in coin_info_list:
        user_message += f"ID: {c['id']}\nName: {c.get('name','')}\nSymbol: {c.get('symbol','')}\nDescription: {c.get('description','')}\n\n"

    # Define the schema for structured output
    schema = {
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
        "minItems": 8,
        "maxItems": 8,
        "additionalProperties": False
    }

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message.strip()}
            ],
            temperature=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "coin_decisions",
                    "schema": schema,
                    "strict": True
                }
            },
            max_tokens=300
        )

        choice = response.choices[0]
        # If model refuses
        if "refusal" in choice.message:
            logging.warning(f"OpenAI refused request for bundle {bundle_id}: {choice.message['refusal']}")
            return None

        if "parsed" in choice.message:
            decisions = choice.message["parsed"]
            return decisions
        else:
            logging.error(f"No parsed decision data for bundle {bundle_id}.")
            return None
    except json.JSONDecodeError:
        logging.error("OpenAI response is not valid JSON.")
        return None
    except Exception as e:
        logging.error(f"OpenAI error for bundle {bundle_id}: {e}", exc_info=True)
        return None

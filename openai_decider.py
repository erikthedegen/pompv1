import os
import openai
import json
import logging

openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    logging.error("OPENAI_API_KEY not set.")

def get_decision(bundle_id, image_url, coin_info_list):
    system_prompt = """
You are a memecoin expert. You see an image with 8 memecoins arranged in a 2x4 grid (IDs 01 to 08).
For each coin, I have provided its name, symbol, and description.
Analyze them and determine which have strong potential ("yes") and which are low potential ("no").

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

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message.strip()}
            ],
            temperature=0.0
        )
        result_content = response.choices[0].message.content.strip()
        decisions = json.loads(result_content)
        if isinstance(decisions, list) and len(decisions) == 8:
            return decisions
        else:
            logging.error("OpenAI response not in expected format.")
            return None
    except json.JSONDecodeError:
        logging.error("OpenAI response is not valid JSON.")
        return None
    except Exception as e:
        logging.error(f"OpenAI error: {e}", exc_info=True)
        return None

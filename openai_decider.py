import os
import logging
import json
from typing import List
from pydantic import BaseModel, Field
from typing_extensions import Literal
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("OPENAI_API_KEY not set.")

client = OpenAI(api_key=openai_api_key)

class CoinDecision(BaseModel):
    id: str = Field(..., description="Coin ID, like '01', '02', etc.")
    decision: Literal["yes","no"] = Field(..., description="Decision for this coin")

class DecisionList(BaseModel):
    decisions: List[CoinDecision]

def get_decision(bundle_id, image_url, coin_info_list):
    system_prompt = """
You are a memecoin expert. You see an image with 8 memecoins arranged in a 2x4 grid (IDs 01 to 08).
For each coin, I have provided its name, symbol, and description.
Analyze them and determine which have strong potential ("yes") and which are low potential ("no").

Return strictly a JSON object of the form:
{
   "decisions": [
       { "id": "01", "decision": "yes" or "no" },
       ...
       { "id": "08", "decision": "yes" or "no" }
   ]
}
No extra text.
    """.strip()

    user_message = "Coins data:\n"
    for c in coin_info_list:
        user_message += f"ID: {c['id']}\nName: {c.get('name','')}\nSymbol: {c.get('symbol','')}\nDescription: {c.get('description','')}\n\n"

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message.strip()},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            temperature=0.0,
            response_format=DecisionList
        )
        msg = completion.choices[0].message
        if msg.refusal:
            logging.error("Model refused to answer.")
            return None
        decisions = msg.parsed.decisions

        if len(decisions) != 8:
            logging.error("OpenAI response not in expected length (8 items).")
            return None

        valid_ids = {f"{i+1:02d}" for i in range(8)}
        for d in decisions:
            if d.id not in valid_ids:
                logging.error("Invalid coin id in OpenAI response.")
                return None
        return [ {"id": d.id, "decision": d.decision} for d in decisions ]

    except Exception as e:
        logging.error(f"OpenAI error: {e}", exc_info=True)
        return None

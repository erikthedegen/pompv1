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
    id: str = Field(..., description="Coin ID")
    decision: Literal["yes","no"] = Field(..., description="Decision")

class DecisionList(BaseModel):
    decisions: List[CoinDecision]

def get_decision(bundle_id, image_url, coin_info_list):
    system_prompt = """
You are a memecoin expert...
    """.strip()

    user_message = "Coins data:\n"
    for c in coin_info_list:
        user_message += f"ID: {c['id']}\nName: {c.get('name','')}\nSymbol: {c.get('symbol','')}\nDescription: {c.get('description','')}\n\n"

    try:
        logging.info("Sending request to OpenAI...")
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
        logging.info(f"OpenAI raw completion response: {completion}")

        msg = completion.choices[0].message
        if msg.refusal:
            logging.error("Model refused to answer.")
            return None
        decisions = msg.parsed.decisions
        logging.info(f"OpenAI parsed decisions: {decisions}")

        if len(decisions) != 8:
            logging.error("OpenAI response not 8 items.")
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

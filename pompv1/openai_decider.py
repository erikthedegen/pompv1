import os
import logging
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
    raise EnvironmentError("OPENAI_API_KEY not set.")

client = OpenAI(api_key=openai_api_key)

class CoinDecision(BaseModel):
    id: str = Field(..., description="Coin ID")
    decision: Literal["yes", "no"] = Field(..., description="Decision")

class DecisionList(BaseModel):
    decisions: List[CoinDecision]

def get_decision(bundle_id: str, image_url: str, coin_info_list: List[dict]) -> List[dict]:
    system_prompt = """
    You are an expert in memecoins with extensive knowledge of the current market trends and project fundamentals.
    You are provided with an image containing a grid of 8 memecoins, each identified by a unique ID visible in the grid.
    Along with the image, you receive metadata for each coin, including its name, symbol, and description.

    Your task is to analyze each memecoin in the image and decide whether it is a good investment ("yes") or not ("no").
    Base your decision on the provided metadata and any insights you can infer from the image.

    Output a structured list of decisions where each entry contains the coin's ID and your decision ("yes" or "no").

    Ensure that the output strictly adheres to the following JSON schema:
    {
        "decisions": [
            {
                "id": "string",
                "decision": "yes" | "no"
            },
            ...
        ]
    }

    Do not include any additional text or commentary in your response.
    """

    user_message = "Coins data:\n"
    for coin in coin_info_list:
        user_message += (
            f"ID: {coin['id']}\n"
            f"Name: {coin.get('name', 'N/A')}\n"
            f"Symbol: {coin.get('symbol', 'N/A')}\n"
            f"Description: {coin.get('description', 'N/A')}\n\n"
        )

    try:
        logging.info(f"Sending decision request for bundle {bundle_id} to OpenAI...")
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
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
            logging.error(f"OpenAI model refused to answer: {msg.refusal}")
            return None

        decisions = msg.parsed.decisions
        logging.info(f"Received decisions from OpenAI: {decisions}")

        if len(decisions) != 8:
            logging.error(f"Expected 8 decisions, but received {len(decisions)}.")
            return None

        valid_ids = {f"{i+1:02d}" for i in range(8)}
        for decision in decisions:
            if decision.id not in valid_ids:
                logging.error(f"Invalid coin ID in response: {decision.id}")
                return None

        formatted_decisions = [{"id": d.id, "decision": d.decision} for d in decisions]
        logging.info(f"Formatted decisions: {formatted_decisions}")

        return formatted_decisions

    except Exception as e:
        logging.error(f"Error while communicating with OpenAI: {e}", exc_info=True)
        return None

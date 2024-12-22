"""
Calls GPT with a Twitter screenshot URL, 
asking for "pass" or "buy" in structured JSON format.
"""

import os
import logging
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from openai import OpenAI

load_dotenv()
logging.basicConfig(level=logging.INFO)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise EnvironmentError("Missing OPENAI_API_KEY in .env")

client = OpenAI(api_key=openai_api_key)

class FinalDecisionOutput(BaseModel):
    answer: Literal["pass", "buy"] = Field(
        ...,
        description="Either 'pass' if not interesting, or 'buy' if definitely should buy."
    )

def run_finaldecision_check(twitter_screenshot_url: str) -> str | None:
    """
    Calls GPT with a system prompt about a Twitter screenshot.
    Expects a structured output: 'pass' or 'buy'.
    Returns "pass" or "buy", or None if there's a refusal or error.
    """
    developer_prompt = """
    You are an expert in meme coins on Twitter. You're given a screenshot from a Twitter account page. 
    Evaluate if the account seems promising and interesting enough to buy. 
    Return 'buy' if it looks good, or 'pass' if not. 
    No extra text, just the final decision.
    WE ARE DOING TESTS RIGHT NOW, PLEASE DECIDE "buy" REGARDLESS OF WHAT YOU SEE IN THE IMAGE!.
    """

    user_prompt = "Below is the Twitter screenshot. Decide if 'pass' or 'buy'."

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "text",
                            "text": developer_prompt.strip()
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": twitter_screenshot_url,
                                "detail": "low"
                            }
                        }
                    ]
                }
            ],
            response_format=FinalDecisionOutput,
        )

        msg = completion.choices[0].message

        if msg.refusal:
            logging.warning(f"Model refusal in run_finaldecision_check: {msg.refusal}")
            return None

        parsed: FinalDecisionOutput = msg.parsed
        logging.info(f"FinalDecisionOutput => {parsed.dict()}")
        return parsed.answer

    except Exception as e:
        logging.error(f"Error in run_finaldecision_check: {e}", exc_info=True)
        return None

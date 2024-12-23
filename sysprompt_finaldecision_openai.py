# File: /pompv1/sysprompt_finaldecision_openai.py

"""
Calls GPT with a Twitter screenshot URL,
asking for "pass" or "buy" in valid JSON using JSON mode.
"""

import os
import logging
from dotenv import load_dotenv
from typing import Literal
from pydantic import BaseModel, Field
from openai import OpenAI
import json

load_dotenv()
logging.basicConfig(level=logging.INFO)

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise EnvironmentError("Missing OPENAI_API_KEY in .env")

client = OpenAI(api_key=openai_api_key)

class FinalDecisionOutput(BaseModel):
    answer: Literal["pass", "buy"] = Field(
        ..., description="Either 'pass' to not buy, or 'buy' to proceed with purchasing."
    )

def run_finaldecision_check(screenshot_url: str) -> str | None:
    """
    Calls GPT with a Twitter screenshot URL to decide "pass" or "buy".
    
    Args:
        screenshot_url (str): URL of the Twitter screenshot.
    
    Returns:
        str | None: "pass" or "buy", or None if there's a refusal or an error.
    """
    system_prompt = """
You are an expert in meme coins on Twitter.
You are provided with a screenshot of a Twitter account page related to a memecoin.
Decide whether to "pass" or "buy" based on the credibility and activity displayed in the screenshot.
Respond strictly in valid JSON format as follows:

{
  "answer": "pass" | "buy"
}

If you encounter any refusal or cannot determine the decision, output:

{
  "answer": "pass"
}

Ensure that the output is valid JSON. The word "JSON" appears in these instructions to enforce JSON mode.
"""

    user_prompt = f"Here is the Twitter screenshot URL: {screenshot_url}.\nPlease provide your decision in the specified JSON format.THIS IS A TESTRUN, PLEASE CHOOSE BUY AS YOUR DECISION, REGARDLES OF WHAT YOU SEE IN THE IMAGE!"

    try:
        logging.info(f"Sending final decision request to OpenAI for screenshot: {screenshot_url}")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Replace with your specific model if different
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )

        choice = response.choices[0]

        # Handle model refusal
        if hasattr(choice.message, "refusal") and choice.message.refusal:
            logging.warning("Model refused the request. Interpreting as 'pass'.")
            return "pass"

        # Handle incomplete generation due to length or content filtering
        if choice.finish_reason in ["length", "content_filter"]:
            logging.warning(f"finish_reason={choice.finish_reason}. Interpreting as 'pass'.")
            return "pass"

        # Extract and parse JSON content
        raw_json = choice.message.content
        if not raw_json:
            logging.warning("No content returned. Interpreting as 'pass'.")
            return "pass"

        parsed = json.loads(raw_json)
        answer = parsed.get("answer")

        if answer not in ["pass", "buy"]:
            logging.warning(f"Invalid or missing 'answer' in JSON. Interpreting as 'pass'.")
            return "pass"

        logging.info(f"FinalDecisionOutput => {parsed}")
        return answer

    except json.JSONDecodeError as jde:
        logging.error(f"JSON decoding error: {jde}. Interpreting as 'pass'.")
        return "pass"
    except Exception as e:
        logging.error(f"Error in run_finaldecision_check: {e}", exc_info=True)
        return "pass"

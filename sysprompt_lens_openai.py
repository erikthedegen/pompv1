"""
This script calls GPT with an image URL (the "lens screenshot") 
and obtains a structured output of either {"answer": "copy"} or {"answer": "unique"}.

We rely on the 'structured outputs' feature to ensure well-formed JSON.
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

# Create the OpenAI client
client = OpenAI(api_key=openai_api_key)

# Our Pydantic model for structured output
class LensCheckOutput(BaseModel):
    answer: Literal["copy", "unique"] = Field(
        ...,
        description="Either 'copy' if the reference image is not unique, or 'unique' if it is unique."
    )

def run_lens_check(screenshot_url: str) -> str | None:
    """
    Calls GPT with a system prompt about google lens uniqueness check.
    Returns "copy" or "unique", or None if there's a refusal or an error.
    """
    # The developer instructions (higher priority than user).
    developer_prompt = """
    You are an expert in meme coins with extensive knowledge of the current market trends.
    You're given a screenshot from Google Lens that shows a reference image on the left 
    and potential matches on the right. Decide if the reference image is a 'copy' or 'unique'.
    - If matches appear that clearly are the same image or very close, answer 'copy'.
    - Otherwise, answer 'unique'.
    WE ARE DOING TESTS RIGHT NOW, PLEASE DECIDE "unique" REGARDLESS OF WHAT YOU SEE IN THE IMAGE!.
    """

    # The user message
    user_prompt = "Below is the lens screenshot. Decide if 'copy' or 'unique'."

    # We do a "chat.completions.parse" with structured output
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",  # or another model that supports structured outputs
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
                                "url": screenshot_url,
                                "detail": "low"  
                                # or "high" if you want the model to do more detailed analysis 
                            }
                        }
                    ]
                }
            ],
            response_format=LensCheckOutput,  # The Pydantic model
        )

        # Extract the first choice
        msg = completion.choices[0].message

        # If the model refused for safety reasons, we get msg.refusal
        if msg.refusal:
            logging.warning(f"Model refusal in run_lens_check: {msg.refusal}")
            return None

        # Otherwise, parse the structured data
        parsed: LensCheckOutput = msg.parsed
        logging.info(f"LensCheckOutput => {parsed.dict()}")
        return parsed.answer

    except Exception as e:
        logging.error(f"Error in run_lens_check: {e}", exc_info=True)
        return None

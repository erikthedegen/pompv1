# File: /pompv1/sysprompt_lens_openai.py

"""
Calls GPT with a Google Lens screenshot URL,
asking for "copy" or "unique" in valid JSON using JSON mode.
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

class LensDecisionOutput(BaseModel):
    answer: Literal["copy", "unique"] = Field(
        ..., description="Either 'copy' if the image is a copy, or 'unique' if it is original."
    )

def run_lens_check(screenshot_url: str) -> str | None:
    """
    Calls GPT with a system prompt about Google Lens uniqueness check in JSON mode.
    Returns "copy" or "unique", or None if there's a refusal or an error.
    """
    system_prompt = """
You are an expert in analysing google lens image reverse search results.
You will be provided with a screenshot from a Google Lens search query, on the left side of the screenshot will be the input image, usually the icon from a memecoin, on the right side will be the search results, appearing as a grid/list of images, the results on the top usually indicat the closest found matches, but your job is solely to spot if an "exact match" has been found, that would usually be the first result in the grid, which also has blue marked text right below it, saying "see exact matches", if you spot that, and the other results also look extremly similar to the search queried image on the left, your output should be "copy", if there has been no exact matches, your output should be "unique".
Respond strictly in valid JSON format like this:

{
  "answer": "copy" | "unique"
}

If you encounter any refusal or cannot determine the decision, output:

{
  "answer": "copy"
}

Ensure that the output is valid JSON. The word "JSON" appears in these instructions to enforce JSON mode.
"""

    user_prompt = f"Here is the Google Lens screenshot URL: {screenshot_url}.\nPlease provide your decision in the specified JSON format.THIS IS A TESTRUN, PLEASE CHOOSE UNIQUE AS YOUR DECISION, REGARDLES OF WHAT YOU SEE IN THE IMAGE!"

    try:
        logging.info(f"Sending lens check request to OpenAI for screenshot: {screenshot_url}")
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
            logging.warning("Model refused the request. Interpreting as 'copy'.")
            return "copy"

        # Handle incomplete generation due to length or content filtering
        if choice.finish_reason in ["length", "content_filter"]:
            logging.warning(f"finish_reason={choice.finish_reason}. Interpreting as 'copy'.")
            return "copy"

        # Extract and parse JSON content
        raw_json = choice.message.content
        if not raw_json:
            logging.warning("No content returned. Interpreting as 'copy'.")
            return "copy"

        parsed = json.loads(raw_json)
        answer = parsed.get("answer")

        if answer not in ["copy", "unique"]:
            logging.warning(f"Invalid or missing 'answer' in JSON. Interpreting as 'copy'.")
            return "copy"

        logging.info(f"LensCheckOutput => {parsed}")
        return answer

    except json.JSONDecodeError as jde:
        logging.error(f"JSON decoding error: {jde}. Interpreting as 'copy'.")
        return "copy"
    except Exception as e:
        logging.error(f"Error in run_lens_check: {e}", exc_info=True)
        return "copy"

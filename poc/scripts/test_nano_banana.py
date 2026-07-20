"""Standalone test for Nano Banana Pro (Gemini image generation via Vertex AI).
Not wired into the app yet - just confirms credentials + model work before
we integrate it into the country-page hero image feature.

Usage:
  GOOGLE_CLOUD_PROJECT=your-project GOOGLE_CLOUD_LOCATION=global \
  GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json \
  uv run python scripts/test_nano_banana.py "A scenic hero image of Italy"
"""

import os
import sys

from google import genai
from google.genai import types

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
MODEL_ID = os.environ.get("NANO_BANANA_MODEL_ID", "gemini-3-pro-image-preview")
PROMPT = sys.argv[1] if len(sys.argv) > 1 else "A scenic, photorealistic hero banner image of Italy"
OUTPUT_PATH = "/tmp/nano_banana_test.png"


def main() -> None:
    if not PROJECT_ID:
        print("ERROR: set GOOGLE_CLOUD_PROJECT in the environment first.")
        sys.exit(1)
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set - relying on ADC if configured.")

    print(f"Project: {PROJECT_ID} | Location: {LOCATION} | Model: {MODEL_ID}")
    print(f"Prompt: {PROMPT}")

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=PROMPT,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                image_config=types.ImageConfig(aspect_ratio="16:9", image_size="2K"),
            ),
        )
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        sys.exit(1)

    image_found = False
    for part in response.candidates[0].content.parts:
        if part.text:
            print("Model text output:", part.text)
        if part.inline_data:
            image_found = True
            with open(OUTPUT_PATH, "wb") as f:
                f.write(part.inline_data.data)
            print(f"SUCCESS: image written to {OUTPUT_PATH} ({len(part.inline_data.data)} bytes)")

    if not image_found:
        print("No image bytes in response - check the model ID and prompt.")
        sys.exit(1)


if __name__ == "__main__":
    main()

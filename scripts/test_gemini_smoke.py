"""
Smoke test for Gemini client wrapper.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel
from PIL import Image

from core.gemini_client import get_client, generate_json
from core.config import GEMINI_MODEL


class HelloSchema(BaseModel):
    message: str
    status: str


def main():
    print(f"Testing Gemini client with model: {GEMINI_MODEL}")
    client = get_client()
    if client is None:
        print("Gemini client is None (no valid API key or offline).")
        return

    print("Client initialized. Making hello-world structured call...")
    res = generate_json(
        prompt="Respond with a JSON object containing message='Hello UrbanLens' and status='ok'.",
        schema=HelloSchema,
        feature="smoke_test",
    )
    print("Result:", res)

    # Test with sample image
    sample_img = Image.new("RGB", (200, 200), color=(120, 120, 120))
    print("Making image structured call...")
    res_img = generate_json(
        prompt="Describe the image color in the message field.",
        schema=HelloSchema,
        image=sample_img,
        feature="smoke_test_image",
    )
    print("Image Result:", res_img)


if __name__ == "__main__":
    main()

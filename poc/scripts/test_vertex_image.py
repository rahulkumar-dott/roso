from google import genai
from google.genai import types

client = genai.Client(
    vertexai=True,
    project="gen-lang-client-0133745072",
    location="global",
)

response = client.models.generate_content(
    model="gemini-3-pro-image",
    contents="A wide, photorealistic hero banner image of Rome, Italy at golden hour - the "
    "Colosseum in the background, warm light, travel-brochure quality, no text overlays.",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    ),
)

candidate = response.candidates[0]
saved = 0
for part in candidate.content.parts:
    if part.text:
        print("TEXT PART:", part.text[:300])
    if part.inline_data:
        out_path = f"scripts/_test_image_output_{saved}.{part.inline_data.mime_type.split('/')[-1]}"
        with open(out_path, "wb") as fh:
            fh.write(part.inline_data.data)
        print(f"IMAGE PART: saved {len(part.inline_data.data)} bytes ({part.inline_data.mime_type}) -> {out_path}")
        saved += 1

if saved == 0:
    print("No image data returned. Full response for debugging:")
    print(response)

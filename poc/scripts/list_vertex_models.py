from google import genai

client = genai.Client(
    vertexai=True,
    project="gen-lang-client-0133745072",
    location="us-central1",
)

for model in client.models.list():
    name = getattr(model, "name", "") or ""
    if "image" in name.lower() or "gemini" in name.lower() or "banana" in name.lower():
        print(name, "|", getattr(model, "display_name", ""))

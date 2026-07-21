from google import genai

client = genai.Client(
    vertexai=True,
    project="gen-lang-client-0133745072",
    location="global",
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain vector databases in simple words.",
)

print(response.text)

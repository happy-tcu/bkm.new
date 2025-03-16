import os
import openai

# Fetch API key from environment variable
openai.api_key = os.getenv("sk-8126e50abadf423a8c95d6aaf58795a5")

# Check if the API key is set
if not openai.api_key:
    raise ValueError("API key is missing! Set it as an environment variable.")

# Test GPT response
response = openai.Completion.create(
    engine="gpt-3.5-turbo",  # Updated to use a newer model
    prompt="Say hello world",
    max_tokens=50
)

# Print the response
print("Response from OpenAI:", response.choices[0].text.strip())

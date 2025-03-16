from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import requests

app = Flask(__name__)  # Initialize Flask app before defining routes

# Get the DeepSeek API key from environment variables (SECURE)
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
if not deepseek_api_key:
    raise ValueError("DeepSeek API Key is missing! Set it as an environment variable.")

def call_deepseek_ai(prompt: str) -> str:
    """Call the DeepSeek AI API and return the response."""
    url = "https://api.deepseek.com/v1/chat/completions"  # Use the correct DeepSeek AI API URL
    payload = {
        "model": "deepseek-chat",  # Ensure you are using the correct DeepSeek model
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {deepseek_api_key}"
    }
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "No response")
    else:
        return f"DeepSeek AI Error: {response.text}"

@app.route("/")
def home():
    """Home endpoint to check the service status."""
    return "Bakame AI is running with DeepSeek integration!"

@app.route("/ivr", methods=["POST"])
def ivr():
    """IVR menu for interacting via voice."""
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/menu", method="POST")
    gather.say(
        "Hello! Welcome to Bakame AI. "
        "Press 1 for a word of the day from DeepSeek AI. "
        "Press 2 to record your speech for analysis. "
        "Press 3 for a short AI quiz. "
        "Press 4 for an AI-created story."
    )
    response.append(gather)
    response.say("We didn't receive input. Please try again.")
    return str(response)

@app.route("/menu", methods=["POST"])
def menu():
    """Handle selections from the IVR menu."""
    response = VoiceResponse()
    choice = request.form.get("Digits")

    if choice == "1":
        prompt = "Give me a random advanced English word, its definition, and an example sentence."
        ai_response = call_deepseek_ai(prompt)
        response.say("Here is your DeepSeek AI-based word of the day:")
        response.say(ai_response)

    elif choice == "2":
        response.say("Tell me about your favorite adventure after the beep.")
        response.record(max_length=10, action="/analyze_speech")

    elif choice == "3":
        prompt = "Ask the user a simple multiple-choice English grammar question."
        ai_response = call_deepseek_ai(prompt)
        response.say("Here is your AI-generated quiz question:")
        response.say(ai_response)

    elif choice == "4":
        prompt = "Create a very short motivational story in English."
        ai_response = call_deepseek_ai(prompt)
        response.say("Here is your AI-generated story:")
        response.say(ai_response)

    else:
        response.say("Invalid choice. Please try again.")
        response.redirect("/ivr")

    return str(response)

@app.route("/analyze_speech", methods=["POST"])
def analyze_speech():
    """Analyze recorded speech and return AI feedback."""
    recording_url = request.form.get("RecordingUrl")
    if not recording_url:
        return "Error: No recording URL received."

    # Send the recording URL to DeepSeek AI for analysis (future step)
    response_text = f"Your recording has been received and will be analyzed: {recording_url}"
    
    response = VoiceResponse()
    response.say(response_text)
    return str(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)

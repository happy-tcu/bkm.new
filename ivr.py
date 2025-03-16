from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import requests

app = Flask(__name__)  # Initialize Flask app before defining routes

# Get the API key from the environment
deekseek_api_key = os.getenv("DEEKSEEK_API_KEY")
print("DeekSeek API Key is:", deekseek_api_key)

def call_deekseek_ai(prompt: str, api_key: str) -> str:
    url = "https://deekseek.ai/api"
    payload = {
        "prompt": prompt,
        "api_key": api_key
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()  # Assuming the API returns JSON

@app.route("/")
def home():
    return "Bakame AI is running with DeekSeek integration!"

@app.route("/ivr", methods=["POST"])
def ivr():
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/menu", method="POST")
    gather.say(
        "Hello! Welcome to Bakame AI. "
        "Press 1 for a word of the day from DeekSeek AI. "
        "Press 2 to record your speech for analysis. "
        "Press 3 for a short AI quiz. "
        "Press 4 for an AI-created story."
    )
    response.append(gather)
    response.say("We didn't receive input. Please try again.")
    return str(response)

@app.route("/menu", methods=["POST"])
def menu():
    response = VoiceResponse()
    choice = request.form.get("Digits")

    if choice == "1":
        prompt = "Give me a random advanced English word, its definition, and an example sentence."
        ai_response = call_deekseek_ai(prompt, deekseek_api_key)
        response.say("Here is your DeekSeek AI-based word of the day.")
        response.say(ai_response)

    # Other cases as in your original code...

    return str(response)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)
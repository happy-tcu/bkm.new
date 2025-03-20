from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import requests

app = Flask(__name__)

# Get API Keys from environment variables
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

if not deepseek_api_key:
    raise ValueError("DeepSeek API Key is missing! Set it as an environment variable.")
if not deepgram_api_key:
    raise ValueError("Deepgram API Key is missing! Set it as an environment variable.")

def call_deepseek_ai(prompt):
    """Send the prompt to DeepSeek AI and return the response."""
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"]

def transcribe_audio(recording_url):
    """Transcribe the student's speech using Deepgram."""
    url = "https://api.deepgram.com/v1/listen"
    headers = {"Authorization": f"Token {deepgram_api_key}"}
    response = requests.post(url, headers=headers, json={"url": recording_url})
    return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]

@app.route("/ivr", methods=["GET", "POST"])
def menu():
    """Main IVR menu."""
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/handle-key", method="POST")
    gather.say("Press 1 for a motivational story. Press 2 to record your answer. Press 3 for a multiple-choice question. Press 4 for an open-ended question.")
    response.append(gather)
    return str(response)

@app.route("/handle-key", methods=["POST"])
def handle_key():
    """Handle the user's menu selection."""
    response = VoiceResponse()
    choice = request.form.get("Digits")

    if choice == "1":
        prompt = "Create a very short motivational story in English."
        ai_response = call_deepseek_ai(prompt)
        response.say("Here is your AI-generated story:")
        response.say(ai_response)

    elif choice == "2":
        response.say("Please speak after the tone.")
        response.record(timeout=5, transcribe=False, action="/analyze-speech")

    elif choice == "3":
        prompt = "Ask the user a simple multiple-choice English grammar question."
        ai_response = call_deepseek_ai(prompt)
        response.say(ai_response)

    elif choice == "4":
        prompt = "Ask an open-ended question that encourages critical thinking."
        ai_response = call_deepseek_ai(prompt)
        response.say(ai_response)

    else:
        response.say("Invalid choice. Please try again.")
        response.redirect("/ivr")

    return str(response)

@app.route("/analyze-speech", methods=["POST"])
def analyze_speech():
    """Analyze the student's speech and return AI feedback."""
    recording_url = request.form.get("RecordingUrl")
    if not recording_url:
        return "Error: No recording URL received."

    transcript = transcribe_audio(recording_url)
    response = VoiceResponse()
    response.say(f"I heard you say: {transcript}")
    
    ai_feedback = call_deepseek_ai(f"Give feedback on this student's spoken response: {transcript}")
    response.say(ai_feedback)

    return str(response)

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests
import os

app = Flask(__name__)

# Get API Keys from environment variables
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

if not deepseek_api_key:
    raise ValueError("DeepSeek API Key is missing! Set it as an environment variable.")
if not deepgram_api_key:
    raise ValueError("Deepgram API Key is missing! Set it as an environment variable.")

def call_deepseek_ai(prompt: str) -> str:
    """Send the transcribed speech to DeepSeek AI and get feedback."""
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    headers = {"Authorization": f"Bearer {deepseek_api_key}", "Content-Type": "application/json"}

    response = requests.post(url, json=payload, headers=headers)
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "AI response unavailable.")

@app.route("/ivr", methods=["POST"])
def menu():
    response = VoiceResponse()
    
    gather = Gather(num_digits=1, action="/handle_choice", method="POST")
    gather.say("Press 1 to hear a fun fact. Press 2 to record your response. Press 3 for a quiz.")
    response.append(gather)

    return str(response)

@app.route("/handle_choice", methods=["POST"])
def handle_choice():
    """Handles the IVR menu selection."""
    response = VoiceResponse()
    digits = request.form.get("Digits")

    if digits == "1":
        response.say("Did you know honey never spoils? Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3000 years old and still perfectly edible!")
        return str(response)
    
    elif digits == "2":
        response.say("Tell me about your favorite adventure after the beep.")
        response.play("https://www.soundjay.com/button/beep-07.wav")  # Plays beep before recording
        response.record(timeout=10, playBeep=True, maxLength=30, action="/analyze_speech")
        return str(response)
    
    elif digits == "3":
        prompt = "Ask the user a simple multiple-choice English grammar question."
        ai_response = call_deepseek_ai(prompt)
        response.say(ai_response)
        return str(response)

    else:
        response.say("Invalid choice. Please try again.")
        response.redirect("/ivr")
        return str(response)

@app.route("/analyze_speech", methods=["POST"])
def analyze_speech():
    """Transcribes the recorded speech and sends it to DeepSeek AI for feedback."""
    recording_url = request.form.get("RecordingUrl")
    
    if not recording_url:
        return "Error: No recording URL received."

    transcript = transcribe_audio(recording_url)
    ai_feedback = call_deepseek_ai(f"Provide feedback on this spoken response: {transcript}")

    response = VoiceResponse()
    response.say(f"Here is your feedback: {ai_feedback}")
    
    return str(response)

def transcribe_audio(audio_url: str) -> str:
    """Transcribes audio using Deepgram."""
    url = "https://api.deepgram.com/v1/listen"
    headers = {"Authorization": f"Token {deepgram_api_key}"}
    response = requests.post(url, headers=headers, json={"url": audio_url})
    
    return response.json().get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "Transcription unavailable.")

if __name__ == "__main__":
    app.run(debug=True)

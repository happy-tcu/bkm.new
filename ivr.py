from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests
import os

app = Flask(__name__)

# Get API Keys
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

if not deepseek_api_key:
    raise ValueError("DeepSeek API Key is missing! Set it as an environment variable.")
if not deepgram_api_key:
    raise ValueError("Deepgram API Key is missing! Set it as an environment variable.")

# Function to call DeepSeek AI
def call_deepseek_ai(prompt):
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
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "I'm sorry, I couldn't process that.")

@app.route("/ivr", methods=["POST"])
def menu():
    """Handles the IVR menu"""
    response = VoiceResponse()
    
    # Use Gather to collect speech input
    gather = Gather(input="speech", action="/process_speech", method="POST", timeout=5)
    gather.say("Tell me about your favorite adventure after the beep.")
    
    response.append(gather)
    
    # If nothing is received, repeat the prompt
    response.say("I didn't catch that. Please try again.")
    response.redirect("/ivr")  

    return str(response)

@app.route("/process_speech", methods=["POST"])
def process_speech():
    """Handles the speech input, processes it, and responds"""
    response = VoiceResponse()
    recording_url = request.form.get("RecordingUrl")

    if not recording_url:
        response.say("I didn't receive any speech. Please try again.")
        response.redirect("/ivr")
        return str(response)

    # Send the recording to Deepgram for transcription
    transcript = transcribe_audio(recording_url)
    
    # Process with AI
    ai_response = call_deepseek_ai(transcript)
    
    response.say(ai_response)
    response.pause(length=1)  # Small pause to make it feel natural
    response.redirect("/ivr")  # Loop back to continue interaction
    
    return str(response)

def transcribe_audio(audio_url):
    """Sends audio to Deepgram for transcription"""
    url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Authorization": f"Token {deepgram_api_key}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json={"url": audio_url}, headers=headers)
    return response.json().get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")

if __name__ == "__main__":
    app.run(debug=True)

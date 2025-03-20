from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests
import time

app = Flask(__name__)

# Deepgram API Key (Set this in your environment variables)
DEEPGRAM_API_KEY = "your_deepgram_api_key"

@app.route("/ivr", methods=["POST"])
def ivr():
    response = VoiceResponse()
    
    # Welcome message
    response.say("Welcome to the interactive session. Please say something after the beep.")

    # Beep sound
    response.play("https://www.soundjay.com/button/beep-07.wav")

    # Gather speech input (max duration 10 sec)
    gather = Gather(input="speech", timeout=5, speechTimeout="auto", action="/process_speech")
    response.append(gather)

    return str(response)

@app.route("/process_speech", methods=["POST"])
def process_speech():
    """Process user speech and send it to AI for response."""
    response = VoiceResponse()
    
    # Get recorded speech text
    speech_text = request.form.get("SpeechResult")
    
    if not speech_text:
        response.say("I didn’t hear anything. Please try again.")
        response.redirect("/ivr")
        return str(response)
    
    response.say("Processing your response. Please wait.")
    
    # Send to Deepgram AI
    ai_response = get_ai_response(speech_text)
    
    # Say AI Response
    response.say(ai_response)

    # Ask if they want to continue
    gather = Gather(input="speech", timeout=5, speechTimeout="auto", action="/process_speech")
    response.say("Would you like to ask another question?")
    response.append(gather)

    return str(response)

def get_ai_response(user_input):
    """Send user speech to Deepgram AI for processing."""
    url = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {"Authorization": f"Bearer {DEEPGRAM_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": user_input}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        return response_data["choices"][0]["message"]["content"]
    except Exception as e:
        return "I'm sorry, I couldn't process that."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)

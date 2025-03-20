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

# Function to call DeepSeek AI
def call_deepseek_ai(prompt: str) -> str:
    """Calls the DeepSeek AI API and returns the response."""
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    headers = {"Authorization": f"Bearer {deepseek_api_key}", "Content-Type": "application/json"}
    
    response = requests.post(url, json=payload, headers=headers)
    
    response_data = response.json()
    if "choices" in response_data and response_data["choices"]:
        return response_data["choices"][0].get("message", {}).get("content", "No response")
    return "DeepSeek AI returned no valid response."

# Function to transcribe audio with Deepgram
def transcribe_audio(recording_url: str) -> str:
    """Sends Twilio recording URL to Deepgram for transcription."""
    url = "https://api.deepgram.com/v1/listen"
    headers = {"Authorization": f"Token {deepgram_api_key}"}
    params = {"punctuate": "true", "language": "en-US"}

    response = requests.post(url, headers=headers, params=params, data=requests.get(recording_url).content)

    if response.status_code == 200:
        return response.json().get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
    return "Deepgram failed to transcribe the audio."

# Main IVR Menu
@app.route("/ivr", methods=["POST"])
def menu():
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/handle_choice", method="POST", actionOnEmptyResult=True)
    
    gather.say("Press 1 for AI feedback. Press 2 to tell a story. Press 3 for a grammar question.")
    response.append(gather)
    
    response.say("No input received. Please try again.")
    response.redirect("/ivr")

    return str(response)

# Handling IVR Menu Choices
@app.route("/handle_choice", methods=["POST"])
def handle_choice():
    response = VoiceResponse()
    choice = request.form.get("Digits", "")

    if choice == "1":
        response.say("Please record your speech after the beep.")
        response.record(max_length=30, action="/analyze_speech")
    
    elif choice == "2":
        response.say("Tell me about your favorite adventure after the beep.")
        response.record(max_length=30, action="/analyze_speech")

    elif choice == "3":
        prompt = "Ask the user a simple multiple-choice English grammar question."
        ai_response = call_deepseek_ai(prompt)
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

# Analyzing Speech
@app.route("/analyze_speech", methods=["POST"])
def analyze_speech():
    """Analyze recorded speech with Deepgram and return AI feedback."""
    recording_url = request.form.get("RecordingUrl")

    if not recording_url:
        print("ERROR: No recording URL received from Twilio")
        return "Error: No recording URL received."

    print(f"Received Recording URL: {recording_url}")

    transcript = transcribe_audio(recording_url)
    print(f"Deepgram Transcription: {transcript}")

    # Send transcript to DeepSeek AI for feedback
    feedback_prompt = f"Provide feedback on this speech: {transcript}"
    ai_feedback = call_deepseek_ai(feedback_prompt)

    response = VoiceResponse()
    response.say(f"AI Feedback: {ai_feedback}")

    return str(response)

# Running Flask App
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)

from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import requests

app = Flask(__name__)

# Temporary storage (Replace with a database later)
student_data = {}

# Get API Keys from environment variables
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")

if not deepseek_api_key:
    raise ValueError("DeepSeek API Key is missing! Set it as an environment variable.")
if not deepgram_api_key:
    raise ValueError("Deepgram API Key is missing! Set it as an environment variable.")

def call_deepseek_ai(prompt):
    """Call DeepSeek AI and return a response."""
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1  # Faster, more accurate responses
    }
    headers = {"Authorization": f"Bearer {deepseek_api_key}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"]

@app.route("/ivr", methods=["POST"])
def welcome_student():
    """Welcomes the student and collects their name."""
    response = VoiceResponse()
    gather = Gather(input="speech", action="/store-name", timeout=5)
    gather.say("Welcome! Please say your full name.", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/store-name", methods=["POST"])
def store_name():
    """Stores the student's name and asks for their student ID."""
    response = VoiceResponse()
    student_name = request.form.get("SpeechResult")

    if not student_name:
        response.say("I didn't catch that. Please say your name again.", voice="Polly.Matthew", rate="85%")
        response.redirect("/ivr")
        return str(response)

    student_data["name"] = student_name

    gather = Gather(input="speech", action="/store-id", timeout=5)
    gather.say(f"Thank you, {student_name}. Now, please say your student ID number.", voice="Polly.Matthew", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/store-id", methods=["POST"])
def store_id():
    """Stores the student's ID and moves to the main menu."""
    response = VoiceResponse()
    student_id = request.form.get("SpeechResult")

    if not student_id:
        response.say("I didn't hear your student ID. Please try again.", voice="Polly.Matthew", rate="85%")
        response.redirect("/store-name")
        return str(response)

    student_data["id"] = student_id
    student_name = student_data.get("name", "Student")

    response.say(f"Thank you, {student_name}. Now let's begin.", voice="Polly.Matthew", rate="85%")
    response.redirect("/menu")

    return str(response)

@app.route("/menu", methods=["POST"])
def menu():
    """Main interactive IVR menu."""
    student_name = student_data.get("name", "Student")
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/handle-key", method="POST")
    gather.say(f"{student_name}, press 1 for interactive facts, press 2 for speech coaching, press 3 for an English quiz, press 4 for an open conversation.", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/handle-key", methods=["POST"])
def handle_key():
    """Handle menu selection."""
    response = VoiceResponse()
    choice = request.form.get("Digits")

    if choice == "1":
        response.redirect("/fact-session")

    elif choice == "2":
        response.redirect("/speech-coaching")

    elif choice == "3":
        response.redirect("/english-quiz")

    elif choice == "4":
        response.redirect("/open-conversation")

    else:
        response.say("Invalid choice. Please try again.", voice="Polly.Matthew", rate="85%")
        response.redirect("/menu")

    return str(response)

@app.route("/fact-session", methods=["POST"])
def fact_session():
    """AI shares a fact and engages in discussion."""
    response = VoiceResponse()
    fact_prompt = "Tell me an interesting fact about the English language."
    fact = call_deepseek_ai(fact_prompt)
    
    response.say(fact, voice="Polly.Matthew", rate="85%")

    gather = Gather(input="speech", action="/fact-response", timeout=5)
    gather.say("What do you think about this fact?", voice="Polly.Matthew", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/fact-response", methods=["POST"])
def fact_response():
    """AI continues fact-based discussion."""
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")

    if not speech_text:
        response.redirect("/fact-session")
        return str(response)

    feedback = call_deepseek_ai(f"Give a thoughtful response to: {speech_text}")
    response.say(feedback, voice="Polly.Matthew", rate="85%")

    response.redirect("/fact-session")
    return str(response)

@app.route("/speech-coaching", methods=["POST"])
def speech_coaching():
    """AI provides real-time feedback as the student speaks."""
    response = VoiceResponse()
    
    gather = Gather(input="speech", action="/analyze-speech", timeout=5)
    gather.say("Tell me something, and I will help improve your pronunciation.", voice="Polly.Matthew", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/analyze-speech", methods=["POST"])
def analyze_speech():
    """AI gives real-time feedback on speech."""
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")

    if not speech_text:
        response.redirect("/speech-coaching")
        return str(response)

    feedback = call_deepseek_ai(f"Correct and improve this spoken response: {speech_text}")
    response.say(feedback, voice="Polly.Matthew", rate="85%")

    response.redirect("/speech-coaching")
    return str(response)

@app.route("/open-conversation", methods=["POST"])
def open_conversation():
    """AI Learning Buddy for English conversation practice."""
    response = VoiceResponse()
    
    gather = Gather(input="speech", action="/conversation-response", timeout=5)
    gather.say("Hi Happy! Welcome back! Let's practice speaking! What topic would you like to discuss today? Any fun stories from one of your class?", voice="Polly.Matthew", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/conversation-response", methods=["POST"])
def conversation_response():
    """AI continues the conversation dynamically."""
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")

    if not speech_text:
        response.redirect("/open-conversation")
        return str(response)

    ai_reply = call_deepseek_ai(f"Continue this conversation as a friendly tutor: {speech_text}")
    response.say(ai_reply, voice="Polly.Matthew", rate="85%")

    gather = Gather(input="speech", action="/conversation-response", timeout=5)
    gather.say("Your turn! Keep talking.", voice="Polly.Matthew", rate="85%")
    response.append(gather)

    return str(response)

if __name__ == "__main__":
    app.run(debug=True)

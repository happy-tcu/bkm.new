from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import requests

app = Flask(__name__)

# Temporary storage (to be replaced with a database later)
student_data = {}

# Get API Keys
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
        "temperature": 0.5
    }
    headers = {"Authorization": f"Bearer {deepseek_api_key}", "Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"]

def transcribe_audio(recording_url):
    """Transcribe speech using Deepgram."""
    url = "https://api.deepgram.com/v1/listen"
    headers = {"Authorization": f"Token {deepgram_api_key}"}
    response = requests.post(url, headers=headers, json={"url": recording_url})
    return response.json()["results"]["channels"][0]["alternatives"][0]["transcript"]

@app.route("/ivr", methods=["POST"])
def welcome_student():
    """Welcomes the student and collects their name."""
    response = VoiceResponse()
    gather = Gather(input="speech", action="/store-name", timeout=5)
    gather.say("Welcome to your interactive English learning session. Please say your full name.", voice="Polly.Matthew", rate="80%")
    response.append(gather)
    return str(response)

@app.route("/store-name", methods=["POST"])
def store_name():
    """Stores the student's name and asks for their student ID."""
    response = VoiceResponse()
    student_name = request.form.get("SpeechResult")

    if not student_name:
        response.say("I didn't catch that. Please say your full name again.", voice="Polly.Matthew", rate="80%")
        response.redirect("/ivr")
        return str(response)

    # Store name temporarily
    student_data["name"] = student_name

    gather = Gather(input="speech", action="/store-id", timeout=5)
    gather.say(f"Thank you, {student_name}. Now, please say your student ID number.", voice="Polly.Matthew", rate="80%")
    response.append(gather)

    return str(response)

@app.route("/store-id", methods=["POST"])
def store_id():
    """Stores the student's ID and moves to the main menu."""
    response = VoiceResponse()
    student_id = request.form.get("SpeechResult")

    if not student_id:
        response.say("I didn't hear your student ID. Please try again.", voice="Polly.Matthew", rate="80%")
        response.redirect("/store-name")
        return str(response)

    # Store student ID
    student_data["id"] = student_id
    student_name = student_data.get("name", "Student")

    response.say(f"Thank you, {student_name}. Now let's begin your learning session.", voice="Polly.Matthew", rate="80%")
    response.redirect("/menu")

    return str(response)

@app.route("/menu", methods=["POST"])
def menu():
    """Main interactive IVR menu."""
    student_name = student_data.get("name", "Student")
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/handle-key", method="POST")
    gather.say(f"{student_name}, press 1 for an interactive fact session. Press 2 for speech coaching. Press 3 for an English quiz. Press 4 to have a conversation in English.", voice="Polly.Matthew", rate="80%")
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
        response.say("Please speak. I will give you feedback as you talk.", voice="Polly.Matthew", rate="80%")
        response.record(timeout=30, playBeep=False, action="/analyze-speech")

    elif choice == "3":
        response.redirect("/english-quiz")

    elif choice == "4":
        response.redirect("/open-conversation")

    else:
        response.say("Invalid choice. Please try again.", voice="Polly.Matthew", rate="80%")
        response.redirect("/menu")

    return str(response)

@app.route("/analyze-speech", methods=["POST"])
def analyze_speech():
    """AI gives real-time feedback on speech."""
    response = VoiceResponse()
    recording_url = request.form.get("RecordingUrl")
    
    if not recording_url:
        return "Error: No recording URL received."

    transcript = transcribe_audio(recording_url)
    feedback = call_deepseek_ai(f"Provide live feedback on pronunciation and fluency for: {transcript}")
    
    response.say(feedback, voice="Polly.Matthew", rate="80%")

    gather = Gather(input="speech", action="/analyze-speech", timeout=5)
    response.say("Say something else and I will keep helping you.", voice="Polly.Matthew", rate="80%")
    response.append(gather)

    return str(response)

@app.route("/english-quiz", methods=["POST"])
def english_quiz():
    """AI asks an interactive English grammar question."""
    response = VoiceResponse()
    quiz_prompt = "Ask a multiple-choice English grammar question and wait for the answer."
    question = call_deepseek_ai(quiz_prompt)
    
    gather = Gather(input="speech", action="/quiz-answer", timeout=5)
    gather.say(question, voice="Polly.Matthew", rate="90%")
    response.append(gather)

    return str(response)

@app.route("/quiz-answer", methods=["POST"])
def quiz_answer():
    """AI evaluates the student's quiz answer."""
    response = VoiceResponse()
    answer = request.form.get("SpeechResult")

    if not answer:
        response.say("I didn't hear an answer. Let's try another question.", voice="Polly.Matthew", rate="80%")
        response.redirect("/english-quiz")
        return str(response)

    feedback = call_deepseek_ai(f"Evaluate if this answer is correct: {answer}")
    response.say(feedback, voice="Polly.Matthew", rate="80%")
    response.redirect("/english-quiz")

    return str(response)

if __name__ == "__main__":
    app.run(debug=True)

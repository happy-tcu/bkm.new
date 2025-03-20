from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import os
import requests

app = Flask(__name__)

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
def menu():
    """Main interactive IVR menu."""
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/handle-key", method="POST")
    gather.say("Press 1 for an interactive fact session. Press 2 for speech coaching. Press 3 for an English quiz. Press 4 to have a conversation in English.", voice="Polly.Brian", rate="85%")
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
        response.say("Please speak. I will give you feedback as you talk.", voice="Polly.Brian", rate="85%")
        response.record(timeout=30, playBeep=False, action="/analyze-speech")

    elif choice == "3":
        response.redirect("/english-quiz")

    elif choice == "4":
        response.redirect("/open-conversation")

    else:
        response.say("Invalid choice. Please try again.", voice="Polly.Brian", rate="85%")
        response.redirect("/ivr")

    return str(response)

@app.route("/fact-session", methods=["POST"])
def fact_session():
    """AI shares a fact, then asks follow-up questions."""
    response = VoiceResponse()
    fact_prompt = "Tell me an interesting fact about English language history."
    fact = call_deepseek_ai(fact_prompt)
    
    response.say(fact, voice="Polly.Brian", rate="85%")

    gather = Gather(input="speech", action="/fact-response", timeout=5)
    gather.say("What do you think about this fact?", voice="Polly.Brian", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/fact-response", methods=["POST"])
def fact_response():
    """AI listens to the student's response and continues interaction."""
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")

    if not speech_text:
        response.say("I didn't hear anything. Let's try another fact.", voice="Polly.Brian", rate="85%")
        response.redirect("/fact-session")
        return str(response)

    feedback = call_deepseek_ai(f"Provide an encouraging response to: {speech_text}")
    response.say(feedback, voice="Polly.Brian", rate="85%")

    response.redirect("/fact-session")
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
    
    response.say(feedback, voice="Polly.Brian", rate="85%")

    gather = Gather(input="speech", action="/analyze-speech", timeout=5)
    response.say("Say something else and I will keep helping you.", voice="Polly.Brian", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/english-quiz", methods=["POST"])
def english_quiz():
    """AI asks an interactive English grammar question."""
    response = VoiceResponse()
    quiz_prompt = "Ask a multiple-choice English grammar question and wait for the answer."
    question = call_deepseek_ai(quiz_prompt)
    
    gather = Gather(input="speech", action="/quiz-answer", timeout=5)
    gather.say(question, voice="Polly.Brian", rate="85%")
    response.append(gather)

    return str(response)

@app.route("/quiz-answer", methods=["POST"])
def quiz_answer():
    """AI evaluates the student's quiz answer."""
    response = VoiceResponse()
    answer = request.form.get("SpeechResult")

    if not answer:
        response.say("I didn't hear an answer. Let's try another question.", voice="Polly.Brian", rate="85%")
        response.redirect("/english-quiz")
        return str(response)

    feedback = call_deepseek_ai(f"Evaluate if this answer is correct: {answer}")
    response.say(feedback, voice="Polly.Brian", rate="85%")
    response.redirect("/english-quiz")

    return str(response)

@app.route("/open-conversation", methods=["POST"])
def open_conversation():
    """AI has a free-flowing conversation with the student."""
    response = VoiceResponse()
    gather = Gather(input="speech", action="/conversation-response", timeout=5)
    gather.say("Let's have a conversation! What would you like to talk about?", voice="Polly.Brian", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/conversation-response", methods=["POST"])
def conversation_response():
    """AI continues the open-ended conversation."""
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")

    if not speech_text:
        response.say("I didn't hear you. Try again.", voice="Polly.Brian", rate="85%")
        response.redirect("/open-conversation")
        return str(response)

    ai_reply = call_deepseek_ai(f"Continue this conversation: {speech_text}")
    response.say(ai_reply, voice="Polly.Brian", rate="85%")

    response.redirect("/open-conversation")
    return str(response)

if __name__ == "__main__":
    app.run(debug=True)

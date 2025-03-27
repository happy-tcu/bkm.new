from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather, Stream
import os
import redis
import json
import asyncio
import aiohttp
import websockets
from deepgram import Deepgram
import logging
from datetime import datetime
import langdetect
from googletrans import Translator
from werkzeug.serving import run_simple

app = Flask(__name__)

# Debug: Print environment variables at startup
print("DEEPSEEK_API_KEY:", os.getenv("DEEPSEEK_API_KEY"))
print("DEEPGRAM_API_KEY:", os.getenv("DEEPGRAM_API_KEY"))

# Redis setup
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
    password=os.getenv("REDIS_PASSWORD", None)
)

# API Keys
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not DEEPSEEK_API_KEY or not DEEPGRAM_API_KEY:
    raise ValueError("Missing API keys! Set DEEPSEEK_API_KEY and DEEPGRAM_API_KEY.")

# Deepgram and Translator
dg_client = Deepgram(DEEPGRAM_API_KEY)
translator = Translator()

# Logging
logging.basicConfig(level=logging.INFO, filename="ivr_advanced.log")
logger = logging.getLogger(__name__)

# Sentiment thresholds
SENTIMENT_POSITIVE = 0.3
SENTIMENT_NEGATIVE = -0.3

async def call_deepseek_api(prompt, session_id=None, language="en"):
    url = "https://api.deepseek.com/chat/completions"  # DeepSeek API endpoint
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    context = redis_client.get(f"session:{session_id}:context") or []
    if isinstance(context, str):
        context = json.loads(context)

    messages = context + [{"role": "user", "content": prompt}]
    payload = {"model": "deepseek-chat", "messages": messages, "max_tokens": 200}  # Using DeepSeek V3 chat model

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                reply = data["choices"][0]["message"]["content"]
                if language != "en":
                    reply = translator.translate(reply, dest=language).text
                context.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": reply}])
                redis_client.setex(f"session:{session_id}:context", 7200, json.dumps(context))
                return reply
            logger.error(f"DeepSeek API error: {resp.status}")
            return "I’m having trouble processing that. Let’s try again."

async def analyze_sentiment(text):
    sentiment_prompt = f"Analyze the sentiment of this text (positive, negative, neutral) and give a score (-1 to 1): {text}"
    sentiment = await call_deepseek_api(sentiment_prompt)
    score = float(sentiment.split("score:")[-1].strip()) if "score:" in sentiment else 0
    return score

def get_session_id(request):
    return request.form.get("CallSid", "default_session")

async def log_interaction(session_id, action, data):
    timestamp = datetime.now().isoformat()
    redis_client.lpush(f"analytics:{session_id}", json.dumps({"timestamp": timestamp, "action": action, "data": data}))

@app.route("/ivr", methods=["POST"])
async def welcome_student():
    session_id = get_session_id(request)
    response = VoiceResponse()
    response.say("Welcome! Say your full name.", voice="Polly.Matthew", rate="85%")
    stream = Stream(url=f"wss://{request.host}/stream/{session_id}", name="deepgram_stream")
    response.append(stream)
    response.redirect(f"/store-name?session_id={session_id}")
    await log_interaction(session_id, "welcome", {"state": "start"})
    return str(response)

@app.route("/store-name", methods=["POST"])
async def store_name():
    session_id = request.args.get("session_id", get_session_id(request))
    response = VoiceResponse()
    speech_result = request.form.get("SpeechResult")
    if not speech_result:
        response.say("I didn’t catch that. Try again.", voice="Polly.Matthew", rate="85%")
        response.redirect(f"/ivr?session_id={session_id}")
        return str(response)

    language = langdetect.detect(speech_result)
    redis_client.setex(f"session:{session_id}:name", 7200, speech_result)
    redis_client.setex(f"session:{session_id}:language", 7200, language)
    gather = Gather(input="speech", action=f"/store-id?session_id={session_id}", timeout=5)
    gather.say(f"Thanks, {speech_result}. Say your student ID.", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    await log_interaction(session_id, "name_stored", {"name": speech_result, "language": language})
    return str(response)

@app.route("/store-id", methods=["POST"])
async def store_id():
    session_id = request.args.get("session_id", get_session_id(request))
    response = VoiceResponse()
    student_id = request.form.get("SpeechResult")
    student_name = redis_client.get(f"session:{session_id}:name") or "Student"
    language = redis_client.get(f"session:{session_id}:language") or "en"

    if not student_id:
        response.say("I didn’t hear your ID. Try again.", voice="Polly.Matthew", rate="85%")
        response.redirect(f"/store-name?session_id={session_id}")
        return str(response)

    redis_client.setex(f"session:{session_id}:id", 7200, student_id)
    intent = await call_deepseek_api(f"Guess the intent of this ID input: {student_id}", session_id, language)
    if "help" in intent.lower():
        response.redirect(f"/open-conversation?session_id={session_id}")
    else:
        response.say(f"Thanks, {student_name}. Let’s begin.", voice="Polly.Matthew", rate="85%")
        response.redirect(f"/menu?session_id={session_id}")
    await log_interaction(session_id, "id_stored", {"id": student_id})
    return str(response)

@app.route("/menu", methods=["POST"])
async def menu():
    session_id = request.args.get("session_id", get_session_id(request))
    student_name = redis_client.get(f"session:{session_id}:name") or "Student"
    language = redis_client.get(f"session:{session_id}:language") or "en"
    response = VoiceResponse()
    sentiment = redis_client.get(f"session:{session_id}:sentiment") or 0
    sentiment = float(sentiment)

    menu_prompt = f"{student_name}, press 1 for facts, 2 for speech coaching, 3 for quiz, 4 for conversation."
    if sentiment < SENTIMENT_NEGATIVE:
        menu_prompt = f"{student_name}, you sound upset. Press 1 for facts, 2 for coaching, 3 for quiz, 4 to talk it out."
    elif sentiment > SENTIMENT_POSITIVE:
        menu_prompt = f"{student_name}, you sound excited! Press 1 for facts, 2 for coaching, 3 for quiz, 4 to chat."

    gather = Gather(num_digits=1, action=f"/handle-key?session_id={session_id}", method="POST")
    gather.say(menu_prompt, voice="Polly.Matthew", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/handle-key", methods=["POST"])
async def handle_key():
    session_id = request.args.get("session_id", get_session_id(request))
    response = VoiceResponse()
    choice = request.form.get("Digits")
    routes = {"1": "/fact-session", "2": "/speech-coaching", "3": "/english-quiz", "4": "/open-conversation"}
    if choice in routes:
        response.redirect(f"{routes[choice]}?session_id={session_id}")
    else:
        response.say("Invalid choice. Try again.", voice="Polly.Matthew", rate="85%")
        response.redirect(f"/menu?session_id={session_id}")
    await log_interaction(session_id, "menu_choice", {"choice": choice})
    return str(response)

@app.route("/fact-session", methods=["POST"])
async def fact_session():
    session_id = request.args.get("session_id", get_session_id(request))
    language = redis_client.get(f"session:{session_id}:language") or "en"
    response = VoiceResponse()
    fact = await call_deepseek_api("Tell me an interesting fact about the English language.", session_id, language)
    response.say(fact, voice="Polly.Matthew", rate="85%")
    gather = Gather(input="speech", action=f"/fact-response?session_id={session_id}", timeout=5)
    gather.say("What do you think?", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/fact-response", methods=["POST"])
async def fact_response():
    session_id = request.args.get("session_id", get_session_id(request))
    language = redis_client.get(f"session:{session_id}:language") or "en"
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")
    if not speech_text:
        response.redirect(f"/fact-session?session_id={session_id}")
        return str(response)

    sentiment = await analyze_sentiment(speech_text)
    redis_client.setex(f"session:{session_id}:sentiment", 7200, str(sentiment))
    feedback = await call_deepseek_api(f"Respond thoughtfully to: {speech_text}", session_id, language)
    response.say(feedback, voice="Polly.Matthew", rate="85%")
    response.redirect(f"/fact-session?session_id={session_id}")
    await log_interaction(session_id, "fact_response", {"text": speech_text, "sentiment": sentiment})
    return str(response)

@app.route("/speech-coaching", methods=["POST"])
async def speech_coaching():
    session_id = request.args.get("session_id", get_session_id(request))
    response = VoiceResponse()
    gather = Gather(input="speech", action=f"/analyze-speech?session_id={session_id}", timeout=5)
    gather.say("Say a sentence, and I’ll analyze your pronunciation with phonetics.", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/analyze-speech", methods=["POST"])
async def analyze_speech():
    session_id = request.args.get("session_id", get_session_id(request))
    language = redis_client.get(f"session:{session_id}:language") or "en"
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")
    if not speech_text:
        response.redirect(f"/speech-coaching?session_id={session_id}")
        return str(response)

    feedback = await call_deepseek_api(
        f"Analyze this speech: '{speech_text}'. Provide a score (1-10) and phonetic breakdown (IPA).",
        session_id, language
    )
    response.say(feedback, voice="Polly.Matthew", rate="85%")
    response.redirect(f"/speech-coaching?session_id={session_id}")
    await log_interaction(session_id, "speech_analysis", {"text": speech_text, "feedback": feedback})
    return str(response)

@app.route("/open-conversation", methods=["POST"])
async def open_conversation():
    session_id = request.args.get("session_id", get_session_id(request))
    response = VoiceResponse()
    gather = Gather(input="speech", action=f"/conversation-response?session_id={session_id}", timeout=5)
    gather.say("Hi! Let’s chat. What’s on your mind today?", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    return str(response)

@app.route("/conversation-response", methods=["POST"])
async def conversation_response():
    session_id = request.args.get("session_id", get_session_id(request))
    language = redis_client.get(f"session:{session_id}:language") or "en"
    response = VoiceResponse()
    speech_text = request.form.get("SpeechResult")
    if not speech_text:
        response.redirect(f"/open-conversation?session_id={session_id}")
        return str(response)

    sentiment = await analyze_sentiment(speech_text)
    redis_client.setex(f"session:{session_id}:sentiment", 7200, str(sentiment))
    intent = await call_deepseek_api(f"Guess the intent of: {speech_text}", session_id, language)
    reply = await call_deepseek_api(
        f"Continue this conversation as a tutor, considering intent '{intent}' and sentiment {sentiment}: {speech_text}",
        session_id, language
    )
    response.say(reply, voice="Polly.Matthew", rate="85%")
    gather = Gather(input="speech", action=f"/conversation-response?session_id={session_id}", timeout=5)
    gather.say("Your turn!", voice="Polly.Matthew", rate="85%")
    response.append(gather)
    await log_interaction(session_id, "conversation", {"text": speech_text, "sentiment": sentiment, "intent": intent})
    return str(response)

@app.route("/analytics/<session_id>", methods=["GET"])
async def get_analytics(session_id):
    interactions = redis_client.lrange(f"analytics:{session_id}", 0, -1)
    return jsonify([json.loads(i) for i in interactions])

async def deepgram_handler(websocket, path):
    session_id = path.split("/")[-1]
    async with dg_client.transcription.live({"punctuate": True, "interim_results": False}) as deepgram:
        async for message in websocket:
            data = json.loads(message)
            if data["event"] == "media":
                audio = data["media"]["payload"]
                await deepgram.send(audio)
                transcription = await deepgram.receive()
                if transcription.get("is_final"):
                    text = transcription["channel"]["alternatives"][0]["transcript"]
                    redis_client.setex(f"session:{session_id}:last_transcript", 60, text)
                    await websocket.send(json.dumps({"event": "transcription", "text": text}))

async def run_servers():
    port = int(os.getenv("PORT", 10000))  # Render assigns PORT
    server = websockets.serve(deepgram_handler, "0.0.0.0", port)
    await asyncio.gather(
        server,
        asyncio.to_thread(run_simple, "0.0.0.0", port, app, use_reloader=False)
    )

if __name__ == "__main__":
    asyncio.run(run_servers())

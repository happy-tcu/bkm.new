from flask import Flask, request, jsonify
from twilio.twiml.voice_response import VoiceResponse, Gather, Stream
import os

# Initialize Flask app
app = Flask(__name__)

# Running the app on the dynamic port
port = int(os.environ.get("PORT", 5000))

# Running Flask server on the dynamic port
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=False)

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

# The rest of the code follows with routes like /store-id, /menu, etc...

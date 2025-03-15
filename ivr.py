import openai
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import json
import asyncio

#####################################
# Your OpenAI & (Optional) Deepgram Keys
#####################################
openai.api_key = "YOUR_OPENAI_API_KEY"  # Replace with your actual OpenAI API key
DEEPGRAM_API_KEY = "YOUR_DEEPGRAM_API_KEY"  # Replace if using Deepgram
DEFAULT_MIMETYPE = "audio/mpeg"  # If Twilio recordings are MP3, else audio/wav

#####################################
# GPT Helper Function
#####################################
def get_gpt_response(prompt):
    """
    Fetch GPT response from OpenAI using ChatCompletion.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or 'gpt-4' if you have access
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print("Error calling OpenAI:", e)
        return f"Failed to get GPT response: {str(e)}"

#####################################
# (Optional) Deepgram Helper Functions
#####################################
try:
    from deepgram import Deepgram
except ImportError:
    # If you haven't installed deepgram-sdk, or if you don't need it, skip
    Deepgram = None

async def transcribe_audio_url(audio_url):
    """Use Deepgram v2 to transcribe the user's audio recording."""
    if not Deepgram:
        # If deepgram is not installed or available, just return a stub.
        return "Transcription not supported right now."

    deepgram = Deepgram(DEEPGRAM_API_KEY)
    options = {"punctuate": True, "language": "en-US"}

    source = {
        "url": audio_url,
        "mimetype": DEFAULT_MIMETYPE
    }
    response = await deepgram.transcription.prerecorded(source, options)

    if not response:
        return "No transcription available."

    if isinstance(response, str):
        try:
            response = json.loads(response)
        except Exception as e:
            print("Error parsing JSON:", e)
            return "Transcription parsing error."

    results = response.get("results")
    if not results:
        return "No transcription found."

    channels = results.get("channels")
    if not channels or len(channels) == 0:
        return "No channels in response."

    alternatives = channels[0].get("alternatives")
    if not alternatives or len(alternatives) == 0:
        return "No alternatives found."

    transcript = alternatives[0].get("transcript")
    if not transcript:
        return "Transcript not found."

    return transcript

def get_transcript(audio_url):
    """Helper to run the async transcription in a synchronous context."""
    return asyncio.run(transcribe_audio_url(audio_url))

#####################################
# Flask App & IVR Routes
#####################################
app = Flask(__name__)

@app.route("/")
def home():
    return "Bakame AI is running with GPT integration!"

@app.route("/ivr", methods=["POST"])
def ivr():
    """Main IVR Menu"""
    response = VoiceResponse()
    gather = Gather(num_digits=1, action="/menu", method="POST")
    gather.say(
        "Hello! Welcome to Bakame AI. "
        "Press 1 to learn a GPT-generated word of the day. "
        "Press 2 to record your speech for analysis. "
        "Press 3 for a GPT quiz. "
        "Press 4 for a GPT-created story."
    )
    response.append(gather)
    response.say("We didn't receive input. Please try again.")
    return str(response)

@app.route("/menu", methods=["POST"])
def menu():
    """Handles user menu selection."""
    response = VoiceResponse()
    choice = request.form.get("Digits")
    print(f"/menu: Received choice = {choice}")  # Debug

    if choice == "1":
        # GPT-generated word of the day
        prompt = "Give me a random advanced English word, its definition, and an example sentence."
        gpt_output = get_gpt_response(prompt)
        response.say("Here is your GPT-generated word of the day.")
        response.say(gpt_output)

    elif choice == "2":
        # Record user speech for transcription & GPT analysis
        response.say("Please speak after the beep. Then we'll analyze it with GPT.")
        response.record(max_length=10, action="/thank_you")

    elif choice == "3":
        # GPT quiz example
        prompt = "Generate a simple 1-question English quiz with 3 multiple-choice answers."
        quiz_text = get_gpt_response(prompt)
        response.say("Here is your GPT-generated quiz.")
        response.say(quiz_text)

    elif choice == "4":
        # GPT-created story
        prompt = "Tell me a short, interesting story suitable for a 10-year-old."
        story_text = get_gpt_response(prompt)
        response.say("Here is your GPT-created story.")
        response.say(story_text)

    else:
        response.say("Invalid choice. Please try again.")
        response.redirect("/ivr")

    return str(response)

@app.route("/thank_you", methods=["POST"])
def thank_you():
    """Analyze the user's recording with GPT if needed."""
    recording_url = request.form.get("RecordingUrl")
    response = VoiceResponse()

    if recording_url:
        try:
            transcript = get_transcript(recording_url)
            print("Transcript:", transcript)

            # GPT analysis of the transcript
            prompt = f"Analyze this text for grammar mistakes and provide feedback:\n{transcript}"
            gpt_analysis = get_gpt_response(prompt)
            response.say("Thank you! Here is some GPT feedback on what you said:")
            response.say(gpt_analysis)

        except Exception as e:
            print("Error in transcription or GPT analysis:", e)
            response.say("There was an error analyzing your recording.")
    else:
        response.say("No recording URL provided.")

    response.redirect("/ivr")
    return str(response)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)

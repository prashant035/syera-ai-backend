import requests
import io
import os
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

API_URL = "https://api.sarvam.ai/text-to-speech/stream"

def speak(text: str):
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "target_language_code": "en-IN",   # change to hi-IN if Hindi interview
        "speaker": "roopa",
        "model": "bulbul:v3",
        "pace": 1.2,  # Increased from 1.05 for faster speech (reduce waiting time for long sentences)
        "speech_sample_rate": 22050,
        "output_audio_codec": "mp3",
        "enable_preprocessing": True
    }

    try:
        # Add a timeout to prevent long waits (10 seconds)
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=10  # Timeout in seconds to avoid indefinite waiting
        )
        response.raise_for_status()

        audio_buffer = io.BytesIO()

        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                audio_buffer.write(chunk)

        audio_buffer.seek(0)
        return audio_buffer.read()

    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
        print("Sarvam TTS Error or Timeout:", e)
        # Fallback to a simple placeholder or skip - frontend can use browser TTS
        return None
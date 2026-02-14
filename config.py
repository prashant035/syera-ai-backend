import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CAMB_API_KEY = os.getenv("CAMB_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
ARTESIA_API_KEY=os.getenv("CARTESIA_API_KEY")


import os
import sys

from dotenv import load_dotenv

load_dotenv()

BLACKHOLE_2CH = "BlackHole 2ch"
BLACKHOLE_16CH = "BlackHole 16ch"
MEET_OUTPUT_MULTI = "Meet Output (Multi)"

SAMPLE_RATE = 48000
ASR_SAMPLE_RATE = 16000  # Google STT streaming + webrtcvad both expect this

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

_REQUIRED_ENV = {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "GOOGLE_APPLICATION_CREDENTIALS": GOOGLE_APPLICATION_CREDENTIALS,
}


def check_required_env():
    missing = [name for name, value in _REQUIRED_ENV.items() if not value]
    if missing:
        sys.exit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )

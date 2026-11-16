"""
Google Cloud TTS synthesis for the outgoing leg's Mandarin voice (Chirp3-HD,
per CLAUDE.md - natural voice, shares auth/billing with Google STT). Returns
raw PCM samples rather than a WAV file, so the mixer can inject them directly
into the BlackHole 16ch output stream without extra parsing downstream.
"""

import io
import wave

import numpy as np
from google.cloud import texttospeech

import config

VOICE_NAME = "cmn-CN-Chirp3-HD-Achernar"
LANGUAGE_CODE = "cmn-CN"

_client = texttospeech.TextToSpeechClient()


def synthesize(text, sample_rate=config.ASR_SAMPLE_RATE):
    """Returns a mono float32 numpy array of synthesized Mandarin speech at sample_rate."""
    if not text.strip():
        return np.zeros(0, dtype=np.float32)

    response = _client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code=LANGUAGE_CODE, name=VOICE_NAME
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
        ),
    )

    with wave.open(io.BytesIO(response.audio_content)) as wav:
        assert wav.getframerate() == sample_rate
        assert wav.getnchannels() == 1
        pcm = wav.readframes(wav.getnframes())

    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


if __name__ == "__main__":
    import sounddevice as sd

    samples = synthesize("你好，我在学中文。", sample_rate=config.ASR_SAMPLE_RATE)
    print(f"Synthesized {len(samples) / config.ASR_SAMPLE_RATE:.2f}s of audio")
    sd.play(samples, config.ASR_SAMPLE_RATE)
    sd.wait()

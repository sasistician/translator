# Live English ↔ Mandarin Voice Translator for Google Meet (macOS)

A live, two-way voice translator that runs alongside a Google Meet call. Built as a learning aid for Mandarin classes.

- **Incoming (Mandarin → English):** captures what Meet plays, transcribes the Mandarin, and prints English captions.
- **Outgoing (English → Mandarin):** transcribes your English, translates it, synthesizes Mandarin speech, and mixes it into your Meet mic *on top of* your real voice, so others hear both.

```
INCOMING   Meet speaker ─► "Meet Output (Multi)" ─► BlackHole 2ch ─► VAD ─► Google STT (zh) ─► Claude (zh→en) ─► captions
                                   └─► your headphones

OUTGOING   real mic ─┬─────────────────────────────────────────────────────────────► mixer ─► BlackHole 16ch ─► Meet mic
                     └─► VAD ─► Google STT (en) ─► Claude (en→zh) ─► Google TTS (cmn) ─┘
```

## Stack

| Stage | Service |
|---|---|
| Speech-to-text (en & zh), streaming | Google Cloud Speech-to-Text |
| Translation (both directions) | Anthropic Claude (Haiku) |
| Mandarin speech synthesis | Google Cloud Text-to-Speech (Chirp3-HD) |
| Voice activity detection (cost gate) | `webrtcvad` (local) |
| Audio I/O & routing | `sounddevice` + BlackHole virtual audio devices |

A local voice-activity detector gates both legs, so audio is only streamed (and billed) to Google while someone is speaking. Each utterance gets its own short streaming session.

## Requirements

- macOS, Python 3.12
- [BlackHole](https://github.com/ExistentialAudio/BlackHole) **2ch** and **16ch**: `brew install --cask blackhole-2ch blackhole-16ch`, then reboot
- A Google Cloud project with the Speech-to-Text and Text-to-Speech APIs enabled
- An Anthropic API key
- **Headphones.** Without them, your mic picks up the call audio and feeds it back.

## Setup

1. **Python environment**
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Credentials:** copy `.env.example` to `.env` and fill in both values.
3. **Audio routing (one-time):**
   - In *Audio MIDI Setup*, create a **Multi-Output Device** named `Meet Output (Multi)` that combines your headphones and **BlackHole 2ch**.
   - In Google Meet's settings: **Speaker** → `Meet Output (Multi)`, **Microphone** → `BlackHole 16ch`.
4. **Check your devices:** `python audio_io.py` lists what's visible.

## Run

```bash
python main.py              # both legs together
python pipeline_incoming.py # Mandarin → English captions only
python pipeline_outgoing.py # English → Mandarin voice only
```

`milestone1_passthrough.py` and `milestone1_capture_test.py` are standalone checks for the audio routing.

## Status

Both legs work end to end in solo and synthesized-audio tests. A full live-class test is next, followed by polish: a proper captions window, a startup device check, volume ducking, and a push-to-translate toggle.

Expect a delay of about 2–4 seconds per utterance on the outgoing leg. It works like consecutive interpretation, not simultaneous dubbing.

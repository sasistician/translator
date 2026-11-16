# Live EN↔Mandarin Voice Translator (Google Meet, macOS)

## What this project is

A live, bidirectional English↔Mandarin voice translator that runs alongside Google Meet during the user's Mandarin classes, on this MacBook.

- **Incoming leg** (teacher/class speaks Mandarin → user): capture Meet's played audio, streaming ASR (zh), translate to English, show as on-screen captions only. No synthesized audio for this leg.
- **Outgoing leg** (user speaks English → class): capture the user's physical mic, streaming ASR (en), translate to Mandarin, synthesize Mandarin speech via TTS, and inject it into the Meet call **mixed with** (not replacing) the user's raw English voice, so classmates hear both.

Full design rationale and alternatives considered live in the plan doc — see "Where the full plan lives" below. This file is the durable, load-bearing summary for future sessions.

## Full plan document

The complete architecture/plan is written at:
`~/.claude/plans/so-i-am-doing-crispy-horizon.md` (local only, not in this repo)

Read it before making architectural changes — it has the reasoning behind each API/library choice, not just the choice.

## Key constraints and decisions (don't relitigate these without reason)

- **Cloud APIs, not local models** — user explicitly chose this for Mandarin accuracy/latency over local Whisper etc.
- **Mix, not replace**, for the outgoing leg — classmates should hear the user's real English voice AND the synthesized Mandarin simultaneously.
- **Captions only** for the incoming (Mandarin→English) leg — no TTS needed there.
- **Python**, using a dedicated venv (see Environment below) — do not use the system Python 3.9.6 or touch the base Anaconda environment.
- **Do not invoke the superpowers skill system on this project** — the user explicitly asked for it to be skipped here. Work directly.

## API/service choices

| Leg | Choice | Why (short) |
|---|---|---|
| Streaming ASR (zh & en) | Google Cloud Speech-to-Text (streaming) | Best Mandarin streaming accuracy; native interim/final + endpointing |
| Translation (both directions) | Anthropic Claude (small/fast model) | Handles fragmentary/informal classroom speech better than a literal translation API |
| TTS (Mandarin synth, outgoing only) | Google Cloud TTS (Chirp3-HD/Neural2 `cmn-CN`) | Natural Mandarin voice, shares auth/billing with Google STT |

**Cost control:** Google STT bills per minute streamed, not per utterance — this is the dominant cost (~$2-3/hr if streamed continuously). Both legs must be gated with a local VAD (`webrtcvad`) so audio only streams to the paid API during detected speech, not silence. This roughly halves cost to **~$1-2/hr**. Don't skip the VAD gate as a "later" optimization — it's part of the base design.

Required env vars (in `.env`, git-ignored): `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON path), `ANTHROPIC_API_KEY`.

## macOS audio routing (the hard, non-code part)

Two BlackHole virtual devices are required, deliberately using two different driver variants rather than renaming two same-type instances (more reliable, no name collisions):

- **BlackHole 2ch** → incoming leg. Feeds into a macOS **Multi-Output Device** ("Meet Output (Multi)") combined with real speakers/headphones, set as Meet's speaker output. Our app reads BlackHole 2ch as an input device to capture whatever Meet plays.
- **BlackHole 16ch** → outgoing leg. Set as Meet's **microphone** input in-browser. Our app opens the real hardware mic directly (Meet never touches it), continuously passes it through to BlackHole 16ch, and mixes in synthesized Mandarin TTS clips on top as they become ready.

**Headphones are required, not optional** — without them, the open-air mic picks up Meet's speaker output (duplicated via the Multi-Output Device) and feeds it back into the outgoing stream, causing echo/feedback.

Device name constants (keep code and manual Audio MIDI Setup / Meet settings consistent): `BlackHole 2ch`, `BlackHole 16ch`, `Meet Output (Multi)`.

## Current setup status (update this section as work progresses)

- [x] Plan written and approved.
- [x] Homebrew present (`/opt/homebrew/bin/brew`).
- [x] `brew install --cask blackhole-2ch blackhole-16ch` completed by the user in their own terminal (the installer needs an interactive `sudo` password prompt, which cannot be run from an agent's sandboxed shell — always hand this command to the user to run themselves).
- [x] Reboot completed — confirmed 2026-07-07 that both `BlackHole 2ch` and `BlackHole 16ch` show up via `system_profiler SPAudioDataType`.
- [x] Python venv created at `venv/` from Anaconda's `python3.12` (not system Python, not Anaconda base). `requirements.txt` now covers all milestones through 4 (sounddevice, numpy, python-dotenv, google-cloud-speech, anthropic, webrtcvad, google-cloud-texttospeech).
- [x] `config.py` (device name constants) and `audio_io.py` (device list/lookup helpers) written and smoke-tested — `python audio_io.py` lists all devices; on this Mac `BlackHole 16ch` resolves to output index 2, `BlackHole 2ch` to input index 3.
- [x] `milestone1_passthrough.py` written (mic → BlackHole 16ch, duplicated to first two of its 16 channels) — smoke-tested that the stream opens and runs with no errors. **Not yet verified by ear in a real Meet call.**
- [x] `milestone1_capture_test.py` written (records N seconds from BlackHole 2ch to a WAV file) — smoke-tested that it records and writes a valid file. **Not yet verified to actually contain Meet's played audio**, since that needs the Multi-Output Device + Meet speaker picker below.
- [x] Multi-Output Device ("Meet Output (Multi)") created in Audio MIDI Setup and verified 2026-07-07: played a 440Hz test tone through it (`sd.playrec`) while recording from BlackHole 2ch — captured cleanly (RMS 0.19, peak matched source amplitude) — and user confirmed hearing the tone through real speakers/headphones. Both legs of the Multi-Output Device confirmed working.
- [x] Google Meet device pickers configured (speaker → "Meet Output (Multi)", mic → "BlackHole 16ch") — confirmed by user in a live Meet call.
- [x] **Milestone 1 complete (2026-07-07)** — verified end-to-end: mic → BlackHole 16ch passthrough carries real signal (RMS test) and was confirmed working live in a Meet call by the user; Meet Output (Multi) → BlackHole 2ch capture confirmed via test tone. Audio routing is proven; safe to start Milestone 2 (outgoing leg, captions only — no TTS/mixing yet).
- [x] **Milestone 2 complete** — outgoing leg, captions only.
  - `config.py` loads `.env` via `python-dotenv` and fail-fasts (`check_required_env()`) if `ANTHROPIC_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS` are missing.
  - `.env.example` created as the template for the two required vars.
  - `asr.py`: `VadGate` (webrtcvad-based, 20ms frames, 10-frame pre-roll / 50-frame ~1000ms post-roll — bumped up from an initial 15-frame post-roll because Google's endpointer needs enough trailing silence to emit `is_final`) gating a Google STT `streaming_recognize` generator (`latest_long` model, `interim_results=True`, parameterized by `language_code` so it serves both `en-US` now and `cmn-Hans-CN` in Milestone 4). Rewritten to open one bounded Google streaming session **per utterance** (opened at speech onset, closed at post-roll elapsed) rather than one long-lived session for the whole run — required because gRPC's streaming_recognize times out (`Audio Timeout Error`) if no audio is sent during silence gaps, and per-utterance sessions also make Google reliably emit `is_final` on close.
  - `translate.py`: `translate(text, direction)` using Claude (`claude-haiku-4-5-20251001`), with scoped interpreter-style system prompts for `en->zh`/`zh->en` for fragmentary streaming-ASR input.
  - **Translation quality eval (2026-07-20)**: after live testing surfaced "not great" translations, evaluated the real STT→Claude path against a battery of spoken-style test phrases (fillers, false starts, short fragments, idioms, self-corrections) by feeding synthesized audio (macOS `say` for English, `tts.py` for Mandarin) directly to Google STT's one-shot `recognize()`, bypassing mic/speaker hardware entirely. Found and fixed a real bug: on short/ambiguous fragments (e.g. `对对对`, `你说的对不对啊`), Claude sometimes hedged with multiple slash-separated alternative translations instead of committing to one — unusable as a live caption. Fixed by adding an explicit "always commit to exactly one translation, never list alternatives" instruction to both system prompts; retested and confirmed. Separately identified (but can't fix here) that Google STT itself occasionally drops or mishears short function words/foreign particles embedded in speech (e.g. "le and guo" → STT dropped "guo" entirely) — an upstream ASR limitation, not a translation prompt issue.
  - Auth: GCP org policy (`iam.disableServiceAccountKeyCreation`) blocks downloadable service-account JSON keys, so this project uses `gcloud auth application-default login` (ADC) instead — `.env`'s `GOOGLE_APPLICATION_CREDENTIALS` points directly at the ADC file (`~/.config/gcloud/application_default_credentials.json`), not a downloaded service-account key. Both Speech-to-Text and Text-to-Speech APIs enabled via `gcloud services enable`.
  - Dependency note: `webrtcvad` imports `pkg_resources`, removed in `setuptools>=81` — pinned `setuptools<81` in `requirements.txt`.
  - Verified live: real mic → real Google STT (en-US) → real Claude translation, finalized `[EN]`/`[ZH]` output confirmed in a live terminal run.
  - **Multi-minute live test + max_tokens bug fix (2026-07-20)**: ran a ~3-minute continuous live speech test (mic → file, via `pipeline_outgoing.py`'s stdout) and found that speaking continuously with no long pause means the VAD never closes the utterance, so a multi-sentence monologue becomes one single STT utterance/translation call — by design (matches how the VAD/per-utterance session works), not a bug, but worth knowing when testing. That single long utterance's Claude translation came back visibly truncated mid-sentence, which traced to `translate()`'s `max_tokens=200` (fine for short conversational turns, too small once an utterance runs to ~150+ words) — bumped to `max_tokens=1024` in `translate.py`. Also noticed `[EN interim] ...` lines end with `\r` (correct for overwriting in a live terminal) which, when stdout is redirected to a plain log file instead of a TTY, get embedded mid-line rather than starting a new line — harmless for the live terminal UI this is designed for, but means naive `grep '^\[EN\]'`-style parsing of a captured log needs to first translate `\r` to `\n` (or a future captions_ui/log-writer should write finalized lines with a clean trailing newline instead of relying on carriage-return overwrite).
- [x] **Milestone 3 complete (2026-07-19)** — Mandarin TTS + mixer injection added to the outgoing pipeline.
  - `tts.py` created: `synthesize(text, sample_rate)` wraps Google Cloud TTS (`cmn-CN-Chirp3-HD-Achernar` voice, LINEAR16), parses the WAV response into a mono float32 array. Verified standalone — user audibly confirmed clear Mandarin playback.
  - `mixer.py` created: `Mixer` class opens a single duplex `sounddevice` stream (mic in, BlackHole 16ch out) that continuously passes the raw mic through AND additively mixes in queued TTS clips (`inject()`) in int16 space with overflow clipping — mix, not replace, per the design constraint. Also fans mic frames out to a shared `frame_queue` so the ASR pipeline doesn't need a second mic stream. Standardized on `config.SAMPLE_RATE` (48000Hz, matching the already-proven Milestone 1 rate) throughout rather than `config.ASR_SAMPLE_RATE` (16000Hz), since both webrtcvad and Google STT accept 48kHz directly and the mic (AirPods, native 24kHz) / BlackHole (native 48kHz) chain made resampling worth avoiding.
  - `pipeline_outgoing.py` rewritten around the shared `Mixer`: mic → `asr.streaming_recognize` (en-US) → on `is_final`, `translate.translate(text, "en->zh")` → `tts.synthesize(zh, sample_rate=config.SAMPLE_RATE)` → `mixer.inject(...)`.
  - **Verified live end-to-end**, including audible/measured confirmation: ran `pipeline_outgoing.py` while a separate process recorded BlackHole 16ch directly (two-process test, matching how Meet will read it in production). Recording showed two distinct amplitude bursts — the live English voice passthrough, then ~4.5s later (matching expected STT+translate+TTS latency) a second, larger burst corresponding to the injected Mandarin TTS clip. Confirms both signals reach BlackHole 16ch simultaneously during a real pipeline run, not just in the isolated mixer-only test.
  - Known non-blocking quirk: opening the same virtual device (BlackHole 16ch) as both input and output from two separate streams *within the same process* triggers a CoreAudio AUHAL error; doing so from two separate OS processes works fine and matches production (our app writes to BlackHole 16ch, Meet — a separate process — reads it), so this only affects same-process test harnesses, not the real app.
- [x] **Milestone 4 complete (2026-07-19)** — incoming leg, captions only.
  - `pipeline_incoming.py` created: opens a plain `sounddevice.InputStream` on BlackHole 2ch (stereo), downmixes to mono int16 frames, feeds the same `asr.streaming_recognize` used by the outgoing leg but with `language_code="cmn-Hans-CN"` — the per-utterance VAD-gated session design from Milestone 2 needed no changes to support the second language. On `is_final`, prints `[ZH]` then `translate.translate(text, "zh->en")` → `[EN]`. No TTS/mixer — captions only, per CLAUDE.md.
  - **Verified live end-to-end** without needing an actual Meet call: played a synthesized Mandarin test clip (via the already-verified `tts.py`) through the "Meet Output (Multi)" device (same technique used to validate the Multi-Output Device in Milestone 1) while `pipeline_incoming.py` listened on BlackHole 2ch in a separate process. Correctly transcribed "老师你好今天我们学习新的语法" and translated it to "Hello teacher, today we're learning new grammar."
  - Still to verify: a real live Meet class (actual teacher audio, real classroom acoustics/accents) rather than a synthesized test clip — the pipeline logic is proven, but real-world audio hasn't been run through it yet.
- [x] `main.py` created — launches `pipeline_outgoing.py` and `pipeline_incoming.py` together as two subprocesses (kept separate per-process rather than merged into one, matching the two-process pattern already proven safe for shared BlackHole device access), tags and interleaves their stdout (`[OUT]`/`[IN]`), and shuts both down on Ctrl+C.
  - Fixed a real shutdown bug during testing: Python's default SIGINT→KeyboardInterrupt handling did not reliably fire in the sandboxed test shell used for verification, leaving orphaned child processes after a blocked `subprocess.wait()`. Fixed by registering an explicit `signal.signal(SIGINT, ...)` handler (confirmed to work where the default disposition didn't) that sets a flag checked in a polling loop, plus an unconditional `wait(timeout=5)` → `kill()` fallback per child so shutdown can never leave orphans regardless of whether a child's own graceful shutdown responds in time. Verified clean: both children exit and no orphaned processes remain after Ctrl+C.
- [ ] **Milestone 4.5 not yet started** — first live test of both legs together in an actual Google Meet call (real conversation with the teacher/class, not synthesized or solo-speech test audio). This is the very next step. It needs to run in the user's own terminal (`python main.py`) during a real call, not via agent-driven timed test harnesses — those work well for solo speech tests (see the multi-minute test above and [[feedback-live-testing-methodology]]), but an actual live class conversation isn't something the agent can drive or time.
- Milestone 5 (polish) not yet started: startup device-check, replace terminal printouts with a real captions UI, mixer volume/ducking tuning, push-to-translate fallback if always-on proves unreliable. Prioritize once the Milestone 4.5 live-Meet test surfaces what actually needs attention.

## Build order (see plan doc for full detail)

1. Prove audio routing manually (BlackHole + Multi-Output Device + Meet device pickers + a trivial mic→BlackHole16ch passthrough script + a BlackHole2ch capture test). Nothing else starts until this works.
2. Outgoing leg, captions only (mic → ASR en → translate en→zh → print/basic UI, no TTS/mixing yet).
3. Add Mandarin TTS + mixer injection to the outgoing pipeline.
4. Incoming leg (BlackHole 2ch → ASR zh → translate zh→en → captions).
5. Polish: unified two-pane caption overlay UI, startup device-check, graceful shutdown, mixer volume/ducking tuning, push-to-translate fallback if always-on passthrough proves unreliable.

## Project structure

```
translator/
├── .gitignore                        # created (venv/, .env, __pycache__/, *.wav)
├── requirements.txt                  # created (sounddevice, numpy, python-dotenv, google-cloud-speech, anthropic, webrtcvad, google-cloud-texttospeech)
├── config.py                         # created — device name constants, sample rate
├── audio_io.py                       # created — device list/lookup helpers
├── milestone1_passthrough.py         # created — mic -> BlackHole 16ch sanity script
├── milestone1_capture_test.py        # created — records BlackHole 2ch -> WAV sanity script
├── venv/                             # created, git-ignored
├── .env.example                      # created — template for GOOGLE_APPLICATION_CREDENTIALS, ANTHROPIC_API_KEY
├── .env                               # created — GOOGLE_APPLICATION_CREDENTIALS points at the ADC file (not a service-account key), ANTHROPIC_API_KEY set
├── asr.py                            # created — VadGate + per-utterance Google STT streaming_recognize wrapper
├── translate.py                      # created — Claude-backed translate(text, direction)
├── tts.py                            # created — Google Cloud TTS (cmn-CN Chirp3-HD) synth wrapper
├── mixer.py                          # created — duplex mic passthrough + additive TTS injection stream
├── pipeline_outgoing.py              # created — mic -> asr(en) -> translate(en->zh) -> tts(cmn) -> mixer.inject
├── pipeline_incoming.py               # created — BlackHole 2ch -> asr(cmn-Hans-CN) -> translate(zh->en) -> printed captions
├── main.py                            # created — runs both pipeline_outgoing.py and pipeline_incoming.py together, tagged/interleaved output
├── captions_ui.py                     # not yet created (Milestone 5)
└── tests/ (test_mixer.py, test_translate.py, fixtures/*.wav)     # not yet created
```

## Known risks (see plan doc for full list + mitigations)

- Audio device settings can silently reset (OS updates, Bluetooth reconnects) — add a startup device-name check.
- ~2-4s latency per utterance on the outgoing/TTS leg is expected (consecutive-interpretation style, not simultaneous dubbing) — not a bug.
- Echo/feedback risk without headphones.
- If always-on mic passthrough glitches in real testing, fall back to a push-to-translate toggle rather than always-on.

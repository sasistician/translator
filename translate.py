"""
Claude-backed translation for live classroom speech. An LLM handles the
fragmentary/informal nature of streaming ASR output (false starts, filler
words, mid-sentence cutoffs) better than a literal translation API.
"""

import anthropic

import config

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPTS = {
    "en->zh": (
        "You are a live interpreter in a Mandarin class. Translate the following "
        "spoken English utterance into natural, conversational Mandarin Chinese. "
        "The input is streaming speech-to-text output, so it may be a sentence "
        "fragment or contain false starts and filler words. Output ONLY the "
        "Mandarin translation - no pinyin, no notes, no quotes. Always commit to "
        "the single most likely reading and output exactly one translation - "
        "never list multiple alternatives or options separated by slashes, even "
        "if the input is short or ambiguous."
    ),
    "zh->en": (
        "You are a live interpreter in a Mandarin class. Translate the following "
        "spoken Mandarin Chinese utterance into natural, conversational English. "
        "The input is streaming speech-to-text output, so it may be a sentence "
        "fragment or contain false starts and filler words. Output ONLY the "
        "English translation - no notes, no quotes. Always commit to the single "
        "most likely reading and output exactly one translation - never list "
        "multiple alternatives or options separated by slashes, even if the "
        "input is short or ambiguous."
    ),
}


def translate(text, direction):
    if direction not in _SYSTEM_PROMPTS:
        raise ValueError(
            f"Unknown direction {direction!r}; expected one of {list(_SYSTEM_PROMPTS)}"
        )
    if not text.strip():
        return ""

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPTS[direction],
        messages=[{"role": "user", "content": text}],
    )
    return response.content[0].text.strip()

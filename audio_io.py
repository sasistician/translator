import sounddevice as sd


def list_devices():
    for index, device in enumerate(sd.query_devices()):
        print(
            f"[{index}] {device['name']!r}  "
            f"in={device['max_input_channels']} out={device['max_output_channels']} "
            f"default_sr={device['default_samplerate']:.0f}"
        )


def find_input_device_index(name_substring):
    return _find_device_index(name_substring, "max_input_channels")


def find_output_device_index(name_substring):
    return _find_device_index(name_substring, "max_output_channels")


def _find_device_index(name_substring, channel_key):
    matches = [
        (index, device)
        for index, device in enumerate(sd.query_devices())
        if name_substring.lower() in device["name"].lower() and device[channel_key] > 0
    ]
    if not matches:
        raise LookupError(
            f"No device matching {name_substring!r} with {channel_key} > 0 found. "
            f"Run audio_io.list_devices() to see what's available."
        )
    if len(matches) > 1:
        raise LookupError(
            f"Multiple devices match {name_substring!r}: {[d['name'] for _, d in matches]}. "
            f"Be more specific."
        )
    return matches[0][0]


if __name__ == "__main__":
    list_devices()

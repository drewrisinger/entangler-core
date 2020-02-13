"""Minimal ARTIQ Device DB for demonstrating the Entangler."""

using_running_output = False

device_db = {
    "core": {
        "type": "local",
        "module": "artiq.coredevice.core",
        "class": "Core",
        "arguments": {"ref_period": 1e-9, "host": "192.168.78.185"},
    },
    "entangler": {
        "type": "local",
        "module": "entangler.driver",
        "class": "Entangler",
        "arguments": {
            "channel": 15 if using_running_output else 16,
            "is_master": True,
        },
        "comments": [
            "Change the channel to match console when building gateware. "
            "Run 'python -m entangler.kasli_generic entangler_gateware_example.json "
            "--no-compile-software --no-compile-gateware'. "
            "If you use a running_output (in JSON), you must decrement this channel."
        ],
    },
}
for i in range(16):
    if i < 12:
        if i == 11 and using_running_output:
            # skip this channel
            continue
        device_db["out{}-{}".format(i // 8, i % 8)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLOut",
            "arguments": {"channel": i},
        }
    else:
        if using_running_output:
            # -1 to skip running_output channel
            channel = i - 1
        else:
            channel = i
        device_db["in{}-{}".format(i // 8, i % 8)] = {
            "type": "local",
            "module": "artiq.coredevice.ttl",
            "class": "TTLInOut",
            "arguments": {"channel": channel},
        }

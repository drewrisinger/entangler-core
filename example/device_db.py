"""Minimal ARTIQ Device DB for demonstrating the Entangler."""

import pkg_resources
from dynaconf import LazySettings

# Get default settings from entangler package's settings.toml
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "")
)
# change if your JSON file has this set
using_running_output = False

# Number of I/O from settings.toml
num_outputs = settings.NUM_OUTPUT_CHANNELS
num_inputs = settings.NUM_ENTANGLER_INPUT_SIGNALS + settings.NUM_GENERIC_INPUT_SIGNALS

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
            # NOTE: channels are 0-indexed
            "channel": (num_outputs + num_inputs - 1)
            if using_running_output
            else (num_inputs + num_outputs),
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

# Add TTL drivers for each I/O in the example.
for i in range(num_outputs + num_inputs):
    if i < num_outputs:
        if i == (num_outputs - 1) and using_running_output:
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

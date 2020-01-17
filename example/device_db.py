"""Minimal ARTIQ Device DB for demonstrating the Entangler."""

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
        "arguments": {"channel": 17, "is_master": True},
        "comments": [
            "Change the channel to match console when building gateware. "
            "Run 'python -m entangler.kasli_generic entangler_gateware_example.json "
            "--no-compile-software --no-compile-gateware'",
        ]
    },
}

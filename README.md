# Entangler

FPGA code & ARTIQ coredevice driver for generating entanglement between multiple ions.

## Functionality

An ``entangler`` works by repeating the same sequence of outputs continuously until it
receives an entanglement signature (herald) within a certain time window.
The output sequence and desired inputs can be configured at runtime with software calls.
One sequence of setting outputs and then observing inputs is called a "cycle".
Then you trigger the sequencers & pattern matchers to run successive cycles,
and it will either time out or stop when it has detected entanglement.

## Components

This repository is organized into several folders.

The ``entangler`` folder holds the gateware ([core.py](./entangler/core.py)
and [phy.py](./entangler/phy.py)) that describes how the entangler works.
It also holds the [ARTIQ](http://github.com/m-labs/artiq) coredevice driver
[driver.py](./entangler/driver.py) that sets up the entangler, triggers it,
and gets information from it.

There are also tests in a separate directory, which can be run with ``pytest -m "not slow"``.

See the [README](./entangler/README.md) for complete information.

## Authors

Originally designed by the Oxford Ion Trap Group (@cjbe & @dnadlinger), extended/modified
by Drew Risinger (University of Maryland, Chris Monroe Ion Trap Group) (@drewrisinger).

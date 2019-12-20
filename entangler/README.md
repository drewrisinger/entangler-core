# Entangler Gateware Notes

## Running tests

Each test can be run individually (with python PATH/TO/TEST.py), or all together using ``pytest``.
To run most tests (~3 min runtime) without running SUPER SLOW tests, run ``pytest -m "not slow"``.

## Building FPGA Gateware

The Entangler requires an FPGA to include it in its gateware before it can do anything.
To accomplish this, we inserted our module into the ARTIQ build process.
You can build the ARTIQ gateware including Entangler by using [kasli_generic.py](./kasli_generic.py).

You simply start a Nix shell ``nix-shell ./nix/entangler-shell-dev.nix``, and then run
``python -m entangler.kasli_generic PATH/TO/KASLI_DESCRIPTION.json``.

### Device Database Entry

To use the Entangler in your experiment code, you need to add it to the device database
``device_db.py``. You must find the RTIO channel for the ``Entangler`` (check the build log),
and fill that in the appropriate spot below:

    ```python
    "entangler": {
        "type": "local",
        "module": "entangler.driver",
        "class": "Entangler",
        "arguments": {"channel": YOUR_CHANNEL_HERE, "is_master": True},
    },
    ```

The Input & Output TTL channels are still accessible as normal, and will need their own
device database entries.

See below for more example code

## Pin Configuration Notes

### Master Entangler -> Slave Entangler Communication

5 pins (Oxford) or 4 pins (UMD) are used for Master <-> Slave entangler communication. These must be connected
to correctly synchronize the two devices/gateware modules.

**NOTE:** Communication can be disabled by passing the PHY no
``core_link_pad``s. This is good for maximizing output pins, if no
inter-Entangler communication is needed.

To do this:
    1. Build two gateware modules. Provide appropriate TTL/GPIO pins to communicate
        between the two modules.
    2. Configure the two gateware modules using appropriate driver calls.
        NOTE: the is_master flag is set on driver instantiation, so you can change
        this between ARTIQ experiments but probably not within the same experiment.
        An example sequence:
        ```python
        # In device_db.py:
        {
            "entangler_device_master": {
                "type": "local",
                "module": "entangler.driver",
                "class": "Entangler",
                "arguments": {
                    "channel": ENTANGLER_RTIO_CHANNEL,
                    "is_master": True,  # CHANGE THIS for slave
                },
            },
        }
        ```
        ```python
        # in user/experiment code
        @host_only
        def build():
            self.setattr_device("entangler_device_master")

        @kernel
        def prep_entangler()
            self.entangler_device_master.init()
        ```

The synchronization pins are used as follows (in order they must be input into the Gateware builder):
    1. (Slave -> Master) Ready: if ready to start the next entanglement cycle
    2. (Master -> Slave): Trigger output
    3. (Master -> Slave): Entanglement success output
    4. (Master -> Slave): Entanglement cycle has timed out
    5. (With Reference ONLY): (Slave -> Master): Sharing of the 422 laser pulse (disabled in Ion-Photon version of Entangler)

NOTE: these definitions can be found in [core.EntanglerCore](./core.py).

## Timestamp Configuration

Input timestamp resolution is 1ns.
Max cycle length is ~10us.
So let's use 14 bits per timestamp (16.38us max).
    * 11 upper bits are for the coarse timestamp (8 ns resolution),
    * 3 lowest bits are for the fine timestamp (< 8 ns resolution).

**Core should only be enabled after sensible values are loaded into the registers.**
E.g. if n_cycles=0 when the core is enabled it will saturate the ififo with timeout events...

## Coredevice Driver/PHY Register Notes

### CAUTION

All these numbers can be changed in [settings.toml](../settings.toml),
but they are not all guaranteed to work 100% as expected.
There are still some hard-coded values, like communication bus bit widths that can
cause unexpected errors.
This has only been extensively tested with 4 Inputs & 4 Outputs, and 4 Inputs & 12 Outputs.
To test that your configuration works, I recommend running ``pytest ..\test\test_ion_photon.py``.

**IMPORTANT:** You must change some values in [settings.toml](../settings.toml) to
correspond to the proper register addresses. The methodology is laid out below,
but it is your responsibility to change those values and run tests to ensure that
they work properly.

### Register Address Format

The register address field is variable length.
It depends ONLY on the total number of I/O channels you are controlling,
The length is:

    ```python
    channel_bits = ceil(log2(num_inputs + num_outputs))
    address_length = 2 + channel_bits
    ```

Let's call the variable part of the previous expression ``channel_bits``
The layout of the register address is (MSB on left):

| Read or Write?    | I/O Channel?          | Channel Num or Other  |
| ----------------- | --------------------- | --------------------- |
| 1 bit             | 1 bit                 | ``channel_bits``      |
| 1 = read, 0 = write | Control an I/O channel | Described in **Write/Read Registers** below. Either a specific channel or other function |

For simplicity, we call the upper two bits ``control`` below, and we specify their
values using Verilog constant syntax.
Example: ``2'd3`` represents the decimal number 3 in 2 bits.
We specify the other fields using ``X'd3``, where ``X=channel_bits`` from above.

### Write Registers

#### Writing Special Registers

Set ``control = 2'd0``.
When defining bits below, let ``H`` be NUM_PATTERNS (heralds), ``I`` be NUM_INPUT_SIGNALS
(set in [settings.toml](../settings.toml)).

| Function  | Other field value | Data field   |
| --------- | ----------------- | ------------- |
| Config    | X'd0              | From MSB->LSB: [standalone, is_master, enable]. Set if master or slave, set if core enabled (i.e. un-tris master / slave outputs, override output phys) |
| Run       | X'd1              | Trigger the entanglement sequence. Data consists of Max time (in coarse units) to run for (i.e. timeout). |
| Cycle Len | X'd2              | Length of cycle (1 attempt) in coarse clock units (8 ns). Divide desired time (in ns) by 8 (or RSHIFT(3)) to get this value. |
| Heralds   | X'd3              | Control the patterns that stop the state machine. Defined as ``(enables, patternH, patternH-1, ..., pattern0)``, where len(enables)=``H`` (MSB of enables = patternH), and len(patternX)=``I``. Set ``enable[p]=1`` to enable a pattern. This allows working with fewer patterns. Default = 20 bits. |

#### Writing I/O Channel Registers

The timing registers are special, somewhat multiplexed, and dependent on the number of
Input/Output Channels defined in [settings.toml](../settings.toml).

The general concept is that writing them sets the functionality of the state machine,
while reading them checks the status of the state machine after generating entanglement.

The Registers are arranged in order of (output, input), which means that the absolute
index of setting a timing register depends on the number of inputs & outputs.

To write a I/O channel register, you must set the control bits to ``2'd1``
(i.e. ``read=0, i/o channel=1``).
The remainder of the address bits are which timing channel should be written.

**Example**: 4 inputs, 4 outputs. To write to output0, address should be ``5'b01000``.
To write to input0, address should be ``5'd01100`` (i.e. output0 address + 4 (# of outputs)).

The timing data that you send depends on whether you are controlling an input or an output.
If you are controlling an output, you are sending the start and stop times of the output
pulse (set to HIGH b/w [start, stop]), relative to the start of the cycle.
If you are controlling an input, this controls the gating window, i.e. when to start looking for an event and when to stop.

Data expects a 32-bit word, though only 2x14 bits are used, with each data word aligned to
16 bit words. The upper word is the stop time, and the lower word is the start time.
That is, the 32-bit word should be arranged ``[stop, start]``.

The smallest start/stop time valid for output events is 1 (0 makes the output stay off permanently).

### Reading Registers

#### Reading Status Registers

To read the status registers, you must set ``control=2'd0``.

| Function  | Other field value | Data field   |
| Status    | X'd0              | Returns 1 if the core is running. |
| NCycles   | X'd1              | How many cycles have been completed in this run? (14 bits, will roll over if too many cycles) |
| Time Remaining | X'd2         | How much time is remaining before timeout (in coarse cycles). This will continue decreasing after success. |
| NTriggers | X'd3              | How many triggers the Entangler received in a run. Only non-zero if a reference PHY is provided on instantiation. |

#### Reading Timing Registers

You can read out the timestamps of the signals at the end of an entanglement run.
Every timestamp (including reference trigger, if enabled) can be read out, with timestamps
relative to the start of the entanglement cycle. If the timestamp is invalid
(i.e. the channel did not trigger), then the timestamp will be ``0``.

Timestamps are organized in order provided to ``input_phys`` on instantiation, with
the reference at the end.

To read a timestamp, set the control bits to ``2'd3``, and then add the number of the
input channel that you would like to read.

Example: (4 inputs, 4 outputs). Read channel 3: ``control_bits=2'd3, other_bits=3'b011``.

"""Simplest possible Entangler experiment.

For demo/example/testing purposes only.
"""
import artiq.language.environment as artiq_env
import artiq.language.units as aq_units
import numpy
import pkg_resources
from artiq.language.core import kernel, delay, delay_mu, parallel
from artiq.language.types import TInt32
from artiq.coredevice.rtio import rtio_output
from dynaconf import LazySettings


# Get the number of inputs & outputs from the settings file.
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "")
)
num_inputs = settings.NUM_INPUT_SIGNALS
num_outputs = settings.NUM_OUTPUT_CHANNELS


class EntanglerDemo(artiq_env.EnvExperiment):
    """Demo experiment for the Entangler.

    Uses the example files in this folder.
    """

    def build(self):
        """Add the Entangler driver."""
        self.setattr_device("core")
        self.setattr_device("entangler")
        self.out0_0 = self.get_device("out0-0")
        self.inputs = [self.get_device("in1-{}".format(i)) for i in range(4, 8)]

    @kernel
    def run(self):
        """Init and run the Entangler on the kernel.

        Pretty much every line in here is important. Make sure you use ALL of them.
        Note that this can be used in loopback mode. If you connect an output to
        one of the end outputs and observe a different output on an oscilloscope,
        you can see the entanglement end early when it detects an "event".
        However, when the loopback cable is unplugged it will run for the full duration.
        """
        self.core.reset()
        self.core.break_realtime()
        self.init()
        self.setup_entangler(
            cycle_len=1200,
            out_start=100,
            out_stop=1000,
            in_start=10,
            in_stop=1000,
            pattern_list=[0b1111, 0b1000, 0b0011],
        )
        end_timestamp, reason = self.run_entangler(10000)
        self.check_entangler_status()

        print("entangler", "Finished", reason)

    @kernel
    def init(self):
        """One-time setup on device != entangler."""
        self.out0_0.pulse(1.5 * aq_units.us)  # marker signal for observing timing
        for ttl_input in self.inputs:
            ttl_input.input()

    @kernel
    def setup_entangler(
        self, cycle_len, out_start, out_stop, in_start, in_stop, pattern_list
    ):
        """Configure the entangler.

        These mostly shouldn't need to be changed between entangler runs, though
        you can with most of the set commands.

        Args:
            cycle_len (int): Length of each entanglement cycle.
            out_start (int): Time in cycle when all outputs should turn on.
            out_stop (int): Time in cycle when all outputs should turn off (deassert)
            in_start (int): Time in cycle when all inputs should start looking for
                input signals
            in_stop (int): Time in cycle when all inputs should STOP looking for
                input signals.
            pattern_list (list(int)): List of patterns that inputs are matched
                against. Matching ANY will stop the entangler.
        """
        self.entangler.init()
        for channel in range(num_outputs):
            self.entangler.set_timing_mu(channel, out_start, out_stop)
        for channel in range(num_inputs):
            self.entangler.set_timing_mu(channel + num_outputs, in_start, in_stop)

        # NOTE: must set enable, defaults to disabled. If not standalone, tries to sync
        # w/ slave (which isn't there) & doesn't start
        self.entangler.set_config(enable=True, standalone=True)
        self.entangler.set_cycle_length_mu(cycle_len)
        self.entangler.set_patterns(pattern_list)

    @kernel
    def run_entangler(self, timeout_length: TInt32):
        """Run the entangler for a max time and wait for it to succeed/timeout."""
        with parallel:
            # This generates output events on the bus -> entangler
            # when rising edges are detected
            self.inputs[0].gate_rising_mu(numpy.int64(timeout_length))
            self.inputs[1].gate_rising_mu(numpy.int64(timeout_length))
            self.inputs[2].gate_rising_mu(numpy.int64(timeout_length))
            self.inputs[3].gate_rising_mu(numpy.int64(timeout_length))
            end_timestamp, reason = self.entangler.run_mu(timeout_length)
        # must wait after entangler ends to schedule new events.
        # Doesn't strictly NEED to break_realtime, but it's safe.
        self.core.break_realtime()
        # Disable entangler control of outputs
        self.entangler.set_config(enable=False)

        # You might also want to disable gating for inputs, but out-of-scope

        return end_timestamp, reason

    @kernel
    def check_entangler_status(self):
        """Get Entangler end status and log to coreanalyzer.

        Not required in normal usage, recognized pattern is returned by run_entangler().
        """
        delay(100 * aq_units.us)
        status = self.entangler.get_status()
        if status & 0b010:
            rtio_log("entangler", "succeeded")
        else:
            rtio_log("entangler", "End status:", status)

        delay(100 * aq_units.us)
        num_cycles = self.entangler.get_ncycles()
        rtio_log("entangler", "#cycles:", num_cycles)
        delay(100 * aq_units.us)
        ntriggers = self.entangler.get_ntriggers()
        rtio_log("entangler", "#triggers (0 if no ref)", ntriggers)
        for channel in range(num_inputs):
            delay(150 * aq_units.us)
            channel_timestamp = self.entangler.get_timestamp_mu(channel)
            rtio_log("entangler", "Ch", channel, ": ts=", channel_timestamp)
        delay(150 * aq_units.us)

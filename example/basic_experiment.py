"""Simplest possible Entangler experiment.

For demo/example/testing purposes only.
"""
import artiq.language.environment as artiq_env
import artiq.language.units as aq_units
import numpy
import pkg_resources
from artiq.language.core import kernel, delay, delay_mu, parallel
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
        However, when the cable is unplugged it will run for the entire duration.
        """

        # NOTE: following break_realtimes/delays are for rtio_log statements, should not be used in production
        # *** Setup ***
        self.core.reset()
        self.core.break_realtime()
        self.entangler.init()   # disable Entangler outputs, write master
        self.out0_0.pulse(1.5 * aq_units.us)
        rtio_log("entangler", "setting inputs")
        delay(15 * aq_units.us)
        # setup inputs & set edge sensitivity (0b01 for rising edge sensitivity, 0b10 for falling, 0b11=both)
        for ttl_inout in self.inputs:
            ttl_inout.input()
            # delay_mu(1)
            # ttl_inout._set_sensitivity(1)
        rtio_log("entangler", "start demo")
        # self.core.break_realtime()
        for channel in range(num_outputs):
            # delay(1 * aq_units.us)
            self.entangler.set_timing_mu(channel, 100, 1000)
        for channel in range(num_inputs):
            # input window start must be at least 8mu
            self.entangler.set_timing_mu(channel + num_outputs, 10, 1000)
        # delay(1 * aq_units.us)
        # NOTE: must set enable, defaults to disabled. If not standalone, tries to sync w/ slave (which isn't there) & doesn't start
        self.entangler.set_config(enable=True, standalone=True)
        # delay(1 * aq_units.us)
        self.entangler.set_cycle_length_mu(1200)
        # delay(1 * aq_units.us)
        self.entangler.set_heralds([0b1111, 0b1000, 0b0011])
        # delay(1 * aq_units.us)
        rtio_log("entangler", "Ended setup")
        delay(10 * aq_units.us)
        # self.core.break_realtime()
        status = self.entangler.get_status()
        # self.core.break_realtime()
        rtio_log("entangler", "Status:", status)
        # self.core.break_realtime()

        # # *** Run ***
        delay(60 * aq_units.us)
        runtime_mu = numpy.int32(10000)
        with parallel:
            # ONE OF FOLLOWING IS REQUIRED
            # This generates output events on the bus -> entangler
            # when rising edges are detected
            self.inputs[0].gate_rising_mu(numpy.int64(runtime_mu))
            self.inputs[1].gate_rising_mu(numpy.int64(runtime_mu))
            self.inputs[2].gate_rising_mu(numpy.int64(runtime_mu))
            self.inputs[3].gate_rising_mu(numpy.int64(runtime_mu))
            # rtio_output(self.inputs[0].target_sample, 1)
            # rtio_output(self.inputs[3].target_sample, 1)
            end_timestamp, reason = self.entangler.run_mu(runtime_mu)
        self.core.break_realtime()  # must wait after entangler ends to schedule new events
        self.entangler.set_config(enable=False)
        if reason != 0x3FFF:
            rtio_log("entangler", "run timestamp:", end_timestamp)
        else:
            rtio_log("entangler", "timeout@", end_timestamp)
        delay(100 * aq_units.us)
        # self.core.break_realtime()
        rtio_log("entangler", "end reason:", reason)
        # self.core.break_realtime()

        # Check status, not required
        delay(100 * aq_units.us)
        status = self.entangler.get_status()
        if status & 0b010:
            rtio_log("entangler", "succeeded")
        else:
            rtio_log("entangler", "End status:", status)

        # self.core.break_realtime()
        delay(100 * aq_units.us)
        num_cycles = self.entangler.get_ncycles()
        rtio_log("entangler", "#cycles:", num_cycles)
        # self.core.break_realtime()
        delay(100 * aq_units.us)
        ntriggers = self.entangler.get_ntriggers()
        rtio_log("entangler", "#triggers (0 if no ref)", ntriggers)
        for channel in range(num_inputs):
            # self.core.break_realtime()
            delay(150 * aq_units.us)
            channel_timestamp = self.entangler.get_timestamp_mu(channel)
            rtio_log("entangler",
                "Ch",
                channel,
                ": ts=",
                channel_timestamp,
            )
        delay(100 * aq_units.us)
        self.out0_0.pulse(5 * aq_units.us)
        print("entangler", "Finished", status)

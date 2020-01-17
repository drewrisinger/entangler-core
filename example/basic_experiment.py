"""Simplest possible Entangler experiment.

For demo/example/testing purposes only.
"""
import artiq.language.environment as artiq_env
import artiq.language.units as aq_units
import pkg_resources
from artiq.language.core import kernel
from dynaconf import LazySettings


# Get the number of inputs & outputs from the settings file.
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)
num_inputs = settings.NUM_INPUTS
num_outputs = settings.NUM_OUTPUTS


class EntanglerDemo(artiq_env.EnvExperiment):
    """Demo experiment for the Entangler.

    Uses the example files in this folder.
    """

    def build(self):
        """Add the Entangler driver."""
        self.setattr_device("entangler")

    @kernel
    def run(self):
        """Init and run the Entangler on the kernel."""
        self.entangler.init()
        for channel in range(num_outputs + num_inputs):
            self.entangler.set_timing(channel, 0 * aq_units.us, 1 * aq_units.us)
        self.entangler.set_cycle_length(1.5 * aq_units.us)
        self.entangler.set_heralds([0b1111, 0b0001, 0b0011])
        # TODO: print results of get() calls
        print("Start Status: ", self.entangler.get_status())
        timestamp, reason = self.entangler.run(1 * aq_units.s)
        if timestamp != 0x3FFF:
            print("Run's timestamp: ", timestamp)
        else:
            print("Run timed out")
        print("Run end reason: ", reason)

        # Check status, not required
        print("End status: ", self.entangler.get_status())
        print("Num cycles before end: ", self.entangler.get_ncycles())
        print(
            "Num triggers: (0 if not using reference)", self.entangler.get_ntriggers()
        )
        for channel in range(num_inputs):
            print(
                "Channel ",
                channel,
                ": timestamp=",
                self.entangler.get_timestamp_mu(channel),
            )

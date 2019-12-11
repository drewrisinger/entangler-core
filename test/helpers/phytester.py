"""Test functions and harness for creating an Entangler PHY device."""
import logging
import typing

import pkg_resources
import migen
from dynaconf import LazySettings
from gateware_utils import MockPhy
from gateware_utils import rtio_output_event

import entangler.phy

_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)


class PhyTestHarness(migen.Module):
    """PHY Test Harness for :class:`entangler.phy.Entangler`."""

    def __init__(self, use_ref: bool = True):
        """Connect the mocked PHY devices to this device.

        Set ``use_ref=False`` if for Ion-Photon.
        """
        self.use_ref = use_ref
        self.counter = migen.Signal(32)

        self.submodules.phy_apd0 = MockPhy(self.counter)
        self.submodules.phy_apd1 = MockPhy(self.counter)
        self.submodules.phy_apd2 = MockPhy(self.counter)
        self.submodules.phy_apd3 = MockPhy(self.counter)
        if use_ref:
            self.submodules.phy_ref = MockPhy(self.counter)
        input_phys = [self.phy_apd0, self.phy_apd1, self.phy_apd2, self.phy_apd3]

        core_link_pads = None
        output_pads = None
        passthrough_sigs = None
        self.submodules.core = entangler.phy.Entangler(
            core_link_pads,
            output_pads,
            passthrough_sigs,
            input_phys,
            reference_phy=self.phy_ref if use_ref else None,
            simulate=True,
        )

        self.comb += self.counter.eq(self.core.core.msm.m)

    def write(self, address: int, data: int) -> None:
        """Write data to the ``EntanglerPHY`` using the data bus.

        Equivalent of ARTIQ ``rtio_output`` method.
        """
        device_address = address & 0xFF
        channel = address >> 8
        _LOGGER.debug(
            "Writing: (chan, addr, data) = %i, %x, %x", channel, device_address, data
        )
        yield from rtio_output_event(self.core.rtlink, address, data)
        # wait 1 cycle for data to settle after sync logic
        # not strictly necessary, but simpler testing
        yield

    def read(self, address: int, data_ref: list) -> None:
        """Read data from a PHY device.

        Meant to be patched into an ARTIQ coredevice-level driver over
        ``rtio_input`` for simulation, or can be called without patch.
        """
        # HACK: sets an input buffer to the value read from the register.
        # essentially forces pass-by-ref
        # TODO: untested/might not work
        _LOGGER.debug("Reading from address %x", address)
        yield from rtio_output_event(self.core.rtlink, address, 0)
        yield
        data_ref[0] = yield self.core.rtlink.i.data
        _LOGGER.debug("Read data: %x", data_ref[0])

    def write_heralds(self, heralds: typing.Sequence[int] = None):
        """Set the heralding patterns for the Entangler via PHY interface."""
        data = 0
        assert len(heralds) <= settings.NUM_PATTERNS_ALLOWED
        for i, h in enumerate(heralds):
            # enable bit
            data |= (1 << i) << (
                settings.NUM_INPUT_SIGNALS * settings.NUM_PATTERNS_ALLOWED
            )
            # move herald to appropriate position in register
            data |= h << (settings.NUM_INPUT_SIGNALS * i)
        yield from self.write(settings.ADDRESS_WRITE.HERALD, data)

    def set_event_times(
        self, ref_time: int, event_time_offsets: typing.Sequence[int]
    ) -> None:
        """Set the input signal event times within a cycle, in mu (ns).

        ``event_time_offsets`` set the event times relative to the ``ref_time``.
        The reference PHY output time is only set if the module is configured
        to have a Reference (see :meth:`__init__`).
        """
        real_event_times = (ref_time + offset for offset in event_time_offsets)
        if self.use_ref:
            yield self.phy_ref.t_event.eq(ref_time)
        for i, t in enumerate(real_event_times):
            yield getattr(self, "phy_apd{}".format(i)).t_event.eq(t)

"""Shared functions for testing ``EntanglerCore``."""
import logging
import typing

import migen
import pkg_resources
from dynaconf import LazySettings
from gateware_utils import MockPhy  # pylint: disable=import-error

import entangler.core

_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "")
)


class CoreTestHarness(migen.Module):
    """Utility functions for testing ``EntanglerCore`` gateware."""

    def __init__(self, use_reference: bool = False):
        """Pass through signals to an ``EntanglerCore`` instance.

        Set ``use_reference=True`` for legacy (Oxford)-style
        Triggered gating (only accepts times relative to input trigger).
        """
        self.counter = migen.Signal(32)

        self.input_phys = [
            MockPhy(self.counter) for _ in range(settings.NUM_ENTANGLER_INPUT_SIGNALS)
        ]
        self.submodules += self.input_phys
        if use_reference:
            self.submodules.phy_ref = MockPhy(self.counter)

        self.submodules.core = entangler.core.EntanglerCore(
            core_link_pads=None,
            output_pads=None,
            passthrough_sigs=None,
            input_phys=self.input_phys,
            reference_phy=self.phy_ref if use_reference else None,
            simulate=True,
        )

        self.comb += self.counter.eq(self.core.msm.m)

    def setup_core(self, cycle_length: int, timeout: int):
        """Initialize the basic settings for the ``EntanglerCore``."""
        msm = self.core.msm
        _LOGGER.debug(
            "Setting up Entangler: CycTime (coarse) = %i, timeout (coarse) = %i",
            cycle_length,
            timeout,
        )
        yield msm.cycle_length_input.eq(cycle_length)
        yield msm.timeout_input.eq(timeout)
        yield msm.is_master.eq(1)
        yield msm.standalone.eq(1)

    def set_sequencer_outputs(
        self, time_pairs: typing.Sequence[typing.Tuple[int, int]]
    ) -> None:
        """Set output TTL/GPIO timings."""
        sequencers = self.core.sequencers
        i = -1
        for i, timing_pair in enumerate(time_pairs):
            start, stop = timing_pair
            yield sequencers[i].m_start.eq(start)
            yield sequencers[i].m_stop.eq(stop)
        for disable_ind in range(i + 1, len(sequencers)):
            yield sequencers[disable_ind].m_start.eq(0)
            yield sequencers[disable_ind].m_stop.eq(0)

    def set_gating_times(
        self, time_pairs: typing.Sequence[typing.Tuple[int, int]]
    ) -> None:
        """Set time windows when the input gaters will register input events."""
        gaters = self.core.apd_gaters
        i = -1
        for i, timing_pair in enumerate(time_pairs):
            start, stop = timing_pair
            yield gaters[i].gate_start.eq(start)
            yield gaters[i].gate_stop.eq(stop)
        for disable_ind in range(i + 1, len(gaters)):
            yield gaters[disable_ind].gate_start.eq(0)
            yield gaters[disable_ind].gate_stop.eq(0)

    def set_event_times(self, event_times: typing.Sequence[int]) -> None:
        """Set the times when the mocked 'input' signals will occur."""
        for i, time in enumerate(event_times):
            yield self.input_phys[i].t_event.eq(time)

    def set_patterns(self, pattern_list: typing.Sequence[int]):
        """Set the patterns that the ``EntanglerCore`` will try to match."""
        patterns = self.core.heralder.patterns
        enables = self.core.heralder.pattern_ens
        for i, pattern in enumerate(pattern_list):
            assert pattern < 2 ** len(patterns[i])
            _LOGGER.debug("Setting pattern %i = %x", i, pattern)
            yield patterns[i].eq(pattern)
            # yield
            # assert (yield patterns[i]) == pattern
        # set enables. Convert # of patterns -> one-hot encoding
        yield enables.eq((2 ** len(pattern_list)) - 1)

        # Verify enable setting
        # yield
        # _LOGGER.debug(
        #     "Enables val: %i, should be %i",
        #     (yield enables),
        #     ((2 ** len(pattern_list) - 1)),
        # )
        # assert (yield enables) == (2 ** len(pattern_list) - 1)

    def start_entanglement_generator(self) -> None:
        """Start the state machine that generates & checks for entanglement."""
        yield self.core.msm.run_stb.eq(1)
        yield
        yield self.core.msm.run_stb.eq(0)

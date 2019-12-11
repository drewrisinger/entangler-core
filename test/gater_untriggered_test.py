"""Test the :class:`entangler.core.UntriggeredInputGater` registers input events."""
import itertools
import logging
import os
import sys

import pkg_resources
from dynaconf import LazySettings
from migen import If
from migen import Module
from migen import run_simulation
from migen import Signal

# add gateware simulation tools "module" (at ./helpers/*)
sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))


from entangler.core import UntriggeredInputGater  # noqa: E402
from gateware_utils import MockPhy  # noqa: E402 pylint: disable=import-error

#  ./helpers/gateware_utils
_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)

class UntriggeredGaterHarness(Module):
    """Test harness to wrap & pass signals to a ``UntriggeredInputGater``."""

    def __init__(self):
        """Create a test harness for the :class:`UntriggeredInputGater`."""
        # current time counter (state machine cycle counter)
        self.m = Signal(settings.FULL_COUNTER_WIDTH)
        self.reset = Signal()
        self.sync += [self.m.eq(self.m + 1), If(self.reset, self.m.eq(0))]

        self.submodules.phy_sig = MockPhy(self.m)

        gater = UntriggeredInputGater(self.m, self.phy_sig)
        self.submodules.gater = gater
        # self.comb += gater.clear.eq(self.reset)


def gater_test(
    dut: UntriggeredGaterHarness, gate_start: int, gate_stop: int, t_sig: int
):
    """Test a ``UntriggeredInputGater`` correctly registers inputs."""
    _LOGGER.info(
        "Starting basic gater test: time_(start, stop, signal) = %d, %d, %d",
        gate_start,
        gate_stop,
        t_sig,
    )
    # setup input signals
    yield dut.gater.gate_start.eq(gate_start)
    yield dut.gater.gate_stop.eq(gate_stop)
    yield dut.phy_sig.t_event.eq(t_sig)
    yield
    yield
    yield dut.reset.eq(1)
    yield dut.gater.clear.eq(1)
    yield
    yield dut.reset.eq(0)
    yield dut.gater.clear.eq(0)

    yield

    # check setup was correct
    assert (yield dut.m) == 0
    assert (yield dut.gater.gate_start) == gate_start
    assert (yield dut.gater.gate_stop) == gate_stop
    assert (yield dut.gater.clear) == 0

    end_time = max((gate_start, gate_stop, t_sig))

    has_ever_triggered = False
    while (yield dut.m) * 8 < end_time + 5:
        # advance 1 clock cycle
        yield

        triggered = (yield dut.gater.triggered) == 1
        sig_ts = (yield dut.gater.sig_ts)
        current_time = (yield dut.m) * 8
        clear_signal = (yield dut.gater.clear) == 1

        signal_in_window = gate_start <= t_sig <= gate_stop
        signal_occurred = current_time > t_sig

        # print(triggered, sig_ts, current_time)

        # should trigger if the signal is in the window & the signal time has passed,
        # or if it ever triggered in the past (without clear)
        should_trigger = (
            (signal_in_window and signal_occurred) or has_ever_triggered
        ) and not clear_signal
        assert triggered == should_trigger
        if triggered:
            has_ever_triggered = True
            assert sig_ts == t_sig
        else:
            assert sig_ts == 0

    # Clear the output if there was one, and check timestamp reset.
    yield dut.gater.clear.eq(1)
    yield
    yield dut.gater.clear.eq(0)
    yield
    assert not bool((yield dut.gater.triggered))
    assert (yield dut.gater.sig_ts) == 0


def gater_invalid_window_test(dut: UntriggeredGaterHarness):
    """Test that gater does not trigger when window is invalid."""
    _LOGGER.info("Starting Invalid window test")

    def set_window_and_test(window_start: int, window_stop: int):
        yield dut.phy_sig.t_event.eq(0)
        yield dut.gater.gate_start.eq(window_start)
        yield dut.gater.gate_stop.eq(window_stop)
        yield dut.reset.eq(1)
        yield dut.gater.clear.eq(1)

        yield

        yield dut.reset.eq(0)
        yield dut.gater.clear.eq(0)

        window_should_be_invalid = (
            window_start < 8 or window_stop < 8 or window_start >= window_stop
        )
        for _ in range(20):
            yield

            sig_triggered = (yield dut.gater.triggered) == 1
            # inverted logic
            sig_window_invalid = (yield dut.gater.is_window_valid) == 0
            assert not sig_triggered
            assert sig_window_invalid == window_should_be_invalid

    for i, j in itertools.product(range(15), range(15)):
        yield from set_window_and_test(i, j)


def gater_clear_test(dut: UntriggeredGaterHarness):
    """Test the clear signal, and also that it will not accidentally trigger.

    I observed behavior where it would trigger when ``time == 0`` (when uninit)
    b/c the input PHY would be set to trigger at 0, which matches the default values
    of the gate window, which causes a "fake" trigger. Fixed in this commit.
    """
    _LOGGER.info("Starting UntriggeredGater Clear Test")
    yield dut.gater.clear.eq(1)

    # advance clock cycles
    for _ in range(10):
        yield
        assert (yield dut.gater.triggered) == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dut = UntriggeredGaterHarness()
    run_simulation(
        dut,
        gater_test(dut, gate_start=20, gate_stop=30, t_sig=25),
        vcd_name="untrig_gater.vcd",
    )

    gate_start = 8
    gate_stop = 25

    for t_sig in range(0, gate_stop + 25):
        dut = UntriggeredGaterHarness()
        run_simulation(
            dut,
            gater_test(dut, gate_start, gate_stop, t_sig),
            vcd_name="untrig_gater_sig-{}.vcd".format(t_sig),
        )

    # Test window validity functionality
    dut = UntriggeredGaterHarness()
    run_simulation(
        dut, gater_invalid_window_test(dut), vcd_name="untrig_gater_window.vcd"
    )

    # Test Clear functionality
    dut = UntriggeredGaterHarness()
    run_simulation(dut, gater_clear_test(dut), vcd_name="untrig_gater_clear.vcd")

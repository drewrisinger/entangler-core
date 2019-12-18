"""Test the :class:`entangler.core.TriggeredInputGater` registers input events."""
import os
import sys

import pkg_resources
import pytest
from dynaconf import LazySettings
from migen import If
from migen import Module
from migen import run_simulation
from migen import Signal

# add gateware simulation tools "module" (at ./helpers/*)
sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))


#  ./helpers/gateware_utils
from entangler.core import TriggeredInputGater  # noqa: E402
from gateware_utils import MockPhy  # noqa: E402 pylint: disable=import-error


settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)


class TriggeredGaterHarness(Module):
    """Test harness to wrap & pass signals to a ``TriggeredInputGater``."""

    def __init__(self):
        """Create a test harness for the :class:`TriggeredInputGater`."""
        self.m = Signal(settings.FULL_COUNTER_WIDTH)
        self.rst = Signal()
        self.sync += [self.m.eq(self.m + 1), If(self.rst, self.m.eq(0))]

        self.submodules.phy_ref = MockPhy(self.m)
        self.submodules.phy_sig = MockPhy(self.m)

        core = TriggeredInputGater(self.m, self.phy_ref, self.phy_sig)
        self.submodules.core = core
        self.comb += core.clear.eq(self.rst)


def gater_test(dut, gate_start: int, gate_stop: int, t_ref: int, t_sig: int):
    """Test a ``TriggeredInputGater`` correctly registers inputs."""
    yield dut.core.gate_start.eq(gate_start)
    yield dut.core.gate_stop.eq(gate_stop)
    yield dut.phy_ref.t_event.eq(t_ref)
    yield dut.phy_sig.t_event.eq(t_sig)
    yield
    yield
    yield dut.rst.eq(1)
    yield
    assert (yield dut.core.sig_ts) == 0
    yield dut.rst.eq(0)

    end_time = max((t_ref + gate_stop), (t_ref + t_sig))

    has_triggered_ever = False
    while (yield dut.m) * 8 < end_time + 5:
        yield

        triggered = (yield dut.core.triggered) == 1
        # TODO: why dut.m +1??
        current_time = (yield dut.m) * 8
        # time_since_ref = current_time - t_ref

        ref_ts = yield dut.core.ref_ts
        sig_ts = yield dut.core.sig_ts
        dt = t_sig - t_ref
        signal_in_window = gate_start <= dt <= gate_stop
        signal_occurred = current_time > t_sig

        # should trigger if the signal is in the window & the signal time has passed,
        # or if it ever triggered in the past
        should_trigger = (signal_in_window and signal_occurred) or has_triggered_ever
        assert triggered == should_trigger
        if triggered:
            has_triggered_ever = True
            assert sig_ts == t_sig

    print(triggered, ref_ts, sig_ts)


@pytest.fixture
def gater_dut() -> TriggeredGaterHarness:
    """Create a TriggeredInputGater for sim."""
    return TriggeredGaterHarness()


# @pytest.mark.parametrize("gate_start,gate_stop,t_ref,t_sig", (20, 30, 20, 41))
@pytest.mark.parametrize("gate_start,gate_stop,t_ref", [(8, 25, 20), (20, 30, 20)])
@pytest.mark.parametrize("t_sig", range(20, 20 + 25 + 10))
def test_triggered_gater(
    request,
    gater_dut: TriggeredGaterHarness,
    gate_start: int,
    gate_stop: int,
    t_ref: int,
    t_sig: int,
):
    """Test the TriggeredInputGater by scanning signal through its gating window."""
    run_simulation(
        gater_dut,
        gater_test(gater_dut, gate_start, gate_stop, t_ref, t_sig),
        vcd_name=(request.node.name + ".vcd"),
    )


if __name__ == "__main__":
    dut = TriggeredGaterHarness()
    run_simulation(dut, gater_test(dut, 20, 30, 20, 41), vcd_name="gater.vcd")

    gate_start = 8
    gate_stop = 25
    t_ref = 20

    for t_sig in range(t_ref, t_ref + gate_stop + 25):
        dut = TriggeredGaterHarness()
        run_simulation(dut, gater_test(dut, gate_start, gate_stop, t_ref, t_sig))

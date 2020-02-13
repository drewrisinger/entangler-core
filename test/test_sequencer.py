"""Test the output event scheduler :class:`entangler.core.ChannelSequencer`."""
import pytest
from migen import Module
from migen import run_simulation
from migen import Signal

from entangler.core import ChannelSequencer


class ChannelSequencerHarness(Module):
    """Test harness for the :class:`ChannelSequencer`."""

    def __init__(self):
        """Wrap & provide passthroughs for the :class:`ChannelSequencer`."""
        self.m = Signal(10)
        self.submodules.core = ChannelSequencer(self.m)


def check_sequencer_timing(dut):
    """Test the outputs of a :class:`ChannelSequencer`."""
    start_time = 10
    stop_time = 30
    yield dut.core.clear.eq(1)
    yield dut.core.m_start.eq(start_time)
    yield dut.core.m_stop.eq(stop_time)
    yield
    yield dut.core.clear.eq(0)

    for i in range(100):
        yield dut.m.eq(i)
        yield

        # Check strobes on proper times
        assert bool((yield dut.core.stb_start)) == (i == start_time)
        assert bool((yield dut.core.stb_stop)) == (i == stop_time)

        # check output values
        if i <= start_time:
            assert (yield dut.core.output) == 0
        if start_time < i <= stop_time:
            assert (yield dut.core.output) == 1
        if i > stop_time:
            assert (yield dut.core.output) == 0


def check_output_glitch(dut):
    """Can get startup glitch when clock (m) is 0 & all inputs are 0.

    This issue is due to sync vs combinational logic on the clear signal.
    """
    yield dut.m.eq(0)
    yield
    assert (yield dut.core.output) == 1
    yield dut.core.clear.eq(1)
    yield
    # yield # We don't want this yield, this yield made the test pass pre-bugfix
    assert (yield dut.core.output) == 0


@pytest.fixture
def sequencer_dut() -> ChannelSequencerHarness:
    """Create a ChannelSequencer for sim."""
    return ChannelSequencerHarness()


@pytest.mark.parametrize("test_function", [check_sequencer_timing, check_output_glitch])
def test_channel_sequencer(request, sequencer_dut: ChannelSequencer, test_function):
    """Test the timing output of a ChannelSequencer."""
    run_simulation(
        sequencer_dut,
        test_function(sequencer_dut),
        vcd_name=(request.node.name + ".vcd"),
    )


if __name__ == "__main__":
    dut = ChannelSequencerHarness()
    run_simulation(dut, check_sequencer_timing(dut), vcd_name="sequencer.vcd")
    dut = ChannelSequencerHarness()
    run_simulation(dut, check_output_glitch(dut), vcd_name="sequencer_glitch.vcd")

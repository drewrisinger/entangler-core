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
    yield dut.core.m_start.eq(10)
    yield dut.core.m_stop.eq(30)
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


@pytest.fixture
def sequencer_dut() -> ChannelSequencerHarness:
    """Create a ChannelSequencer for sim."""
    return ChannelSequencerHarness()


def test_channel_sequencer(request, sequencer_dut: ChannelSequencer):
    """Test the timing output of a ChannelSequencer."""
    run_simulation(
        sequencer_dut,
        check_sequencer_timing(sequencer_dut),
        vcd_name=(request.node.name + ".vcd"),
    )


if __name__ == "__main__":
    dut = ChannelSequencerHarness()
    run_simulation(dut, check_sequencer_timing(dut), vcd_name="sequencer.vcd")

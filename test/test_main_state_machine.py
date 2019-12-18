"""Test the entangler state machine logic in :class`entangler.core.MainStateMachine`."""
import pytest
from migen import Module
from migen import run_simulation

from entangler.core import MainStateMachine


def msm_master_test(dut: MainStateMachine):
    """Test the main state machine in master configuration."""
    yield dut.cycle_length_input.eq(10)
    yield dut.is_master.eq(1)
    yield dut.time_remaining.eq(100)

    for i in range(30):
        if i == 5:
            yield dut.slave_ready.eq(1)
        yield


def msm_slave_test(dut: MainStateMachine):
    """Test the state machine in slave configuration."""
    yield dut.cycle_length_input.eq(10)
    yield dut.is_master.eq(1)
    yield dut.cycles_remaining.eq(3)

    for i in range(30):
        if i == 5:
            yield dut.slave_ready.eq(1)
        yield


class MsmPair(Module):
    """Create a master/slave pair of state machines in one gateware module."""

    def __init__(self):
        """Instantiate the modules for the master/slave state machines."""
        self.submodules.master = MainStateMachine()
        self.submodules.slave = MainStateMachine()

        self.comb += [
            self.master.is_master.eq(1),
            self.master.slave_ready_raw.eq(self.slave.ready),
            self.slave.trigger_in_raw.eq(self.master.trigger_out),
            self.slave.success_in_raw.eq(self.master.success),
            self.slave.timeout_in_raw.eq(self.master.timeout),
        ]


def msm_standalone_test(dut):
    """Test the ``Entangler`` state machine logic in standalone mode."""
    yield dut.cycle_length_input.eq(10)
    yield dut.is_master.eq(1)
    yield dut.standalone.eq(1)
    yield dut.timeout_input.eq(80)

    yield
    yield

    def run(allow_success=True):
        # Run and check we finish when we get a herald (if allow_success) or
        # that we time out
        for _ in range(20):
            yield
        yield dut.run_stb.eq(1)
        yield
        yield dut.run_stb.eq(0)
        finished = False
        for i in range(100):
            if i == 40 and allow_success:
                yield dut.herald.eq(1)
            if i > 40 and (yield dut.done_stb):
                finished = True
            yield
        yield dut.herald.eq(0)
        assert finished
        success = yield dut.success
        assert success == allow_success

    yield from run()

    # Check core still works with a full reset
    yield from run()

    # Check timeout works
    yield from run(False)


def msm_pair_test(dut: MsmPair):
    """Test the master/slave state machines working together."""
    yield dut.master.cycle_length_input.eq(10)
    yield dut.slave.cycle_length_input.eq(10)
    yield dut.master.timeout_input.eq(100)
    yield dut.slave.timeout_input.eq(100)

    def run(t_start_master: int, t_start_slave: int, t_herald: int = None):
        yield dut.master.herald.eq(0)
        for _ in range(5):
            yield
        t_master_done = None
        success_master = False
        success_slave = False
        t_slave_done = None
        for i in range(200):
            if i == t_start_master:
                yield dut.master.run_stb.eq(1)
            elif i == t_start_master + 1:
                yield dut.master.run_stb.eq(0)
            if i == t_start_slave:
                yield dut.slave.run_stb.eq(1)
            elif i == t_start_slave + 1:
                yield dut.slave.run_stb.eq(0)
            if t_herald and i == t_herald:
                yield dut.master.herald.eq(1)

            if (yield dut.master.done_stb):
                t_master_done = i
                success_master = yield dut.master.success
            if (yield dut.slave.done_stb):
                t_slave_done = i
                success_slave = yield dut.slave.success

            m_master = yield dut.master.m
            m_slave = yield dut.slave.m
            if m_master == 1:
                assert m_master == m_slave

            yield
        print(t_master_done, t_slave_done)

        # Master and slave should agree on success
        assert success_master == success_slave
        success = success_master

        # Success only if we expect it
        assert success == (t_herald is not None)

        # Master and slave should finish at the same time (modulo registering offsets)
        # on success, this is obvious
        # without success, when the master times out it should stop the slave -
        # this can only occur if the master times out before the slave
        if success or t_start_slave > t_start_master:
            assert t_master_done == t_slave_done - 2

    # Start at different times, but sync up and agree on success
    yield from run(t_start_master=10, t_start_slave=20, t_herald=80)

    # Time out without success, slave timing out first
    # Slave does not run - just starts and times out because master is not running
    yield from run(t_start_master=60, t_start_slave=10, t_herald=None)

    # Time out without success, master timing out first
    yield from run(t_start_master=10, t_start_slave=60, t_herald=None)


@pytest.fixture
def msm_standalone() -> MainStateMachine:
    """Create a single StateMachine for sim."""
    return MainStateMachine()


@pytest.fixture
def msm_pair() -> MsmPair:
    """Create two paired StateMachines for sim."""
    return MsmPair()


def test_msm_standalone(request, msm_standalone):
    """Test the standalone StateMachine."""
    run_simulation(
        msm_standalone,
        msm_standalone_test(msm_standalone),
        vcd_name=(request.node.name + ".vcd"),
    )


def test_msm_pair(request, msm_pair):
    """Test communication between a StateMachine pair."""
    run_simulation(
        msm_pair, msm_pair_test(msm_pair), vcd_name=(request.node.name + ".vcd")
    )


if __name__ == "__main__":
    dut = MsmPair()
    run_simulation(dut, msm_pair_test(dut), vcd_name="msm_pair.vcd")

    dut = MainStateMachine()
    run_simulation(dut, msm_standalone_test(dut), vcd_name="msm_standalone.vcd")

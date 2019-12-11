"""Test the :class:`entangler.core.EntanglerCore` functionality."""
import functools
import logging
import os
import sys
import typing

# add gateware simulation tools "module" (at ./helpers/*)
sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))


import pkg_resources
from dynaconf import LazySettings  # noqa: E402
from migen import run_simulation  # noqa: E402

# pylint: disable=import-error
from coretester import CoreTestHarness  # noqa: E402
from gateware_utils import advance_clock  # noqa: E402
from gateware_utils import wait_until  # noqa: E402

_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)


def int_to_bool_array(val: int, num_binary_digits: int) -> typing.Sequence[bool]:
    """Convert a one-hot-encoded (binary) number to the equivalent boolean array."""
    bool_arr = [bool(val & 1 << (i - 1)) for i in range(num_binary_digits, 0, -1)]
    assert len(bool_arr) == num_binary_digits
    return bool_arr


def standalone_test(dut: CoreTestHarness):
    """Test the standalone :class:``EntanglerCore`` works properly."""
    yield from dut.setup_core(cycle_length=20, timeout=1000)

    yield from dut.set_sequencer_outputs([(1, 9), (2, 5), (3, 4)])

    yield from dut.set_gating_times([(18, 30), (8, 30), (18, 30)])

    yield dut.phy_ref.t_event.eq(75)
    yield from dut.set_event_times([1000] * 4)  # make events "impossible"

    yield from dut.set_patterns((0b0101, 0b1111))

    yield from advance_clock(5)

    assert (yield dut.core.uses_reference_trigger) == 1

    yield from dut.start_entanglement_generator()

    yield from advance_clock(500)

    # eventually, make an event happen.
    ref_event_time = 8 * 10 + 3
    yield dut.phy_ref.t_event.eq(ref_event_time)
    yield from dut.set_event_times([ref_event_time + i for i in (18, 40, 30, 30)])

    yield from advance_clock(50)

    # check the EntanglerCore succeeded as expected.
    assert (yield dut.core.msm.success) == 1
    assert (yield dut.core.msm.running) == 0
    assert (yield dut.core.msm.timeout) == 0


def standalone_test_parametrized(
    dut: CoreTestHarness, cycle_length: int, failed_cycles: int
):
    """Test that all possible combinations of input signals occur."""
    _LOGGER.info("Starting EntCore param test: cycle_length=%i", cycle_length)
    input_chans = settings.NUM_INPUT_SIGNALS
    output_chans = settings.NUM_OUTPUT_CHANNELS
    yield from dut.setup_core(cycle_length, 10000)
    yield from dut.set_sequencer_outputs([(i, 10 - i) for i in range(output_chans)])

    # setup input checking (patterns & gating)
    ref_time = int(cycle_length / 4 * 8)
    cycle_length_ns = int(cycle_length * 8)
    yield dut.phy_ref.t_event.eq(ref_time)
    # delay window by 1 coarse clock cycle (8ns) b/c it doesn't work in same clock as
    # reference
    gate_windows = [
        (ref_time + (i + 1) * 8, cycle_length_ns - ref_time) for i in range(input_chans)
    ]
    yield from dut.set_gating_times(gate_windows)
    patterns = (0b0011,)
    yield from dut.set_patterns(patterns)
    pattern_to_bool = functools.partial(int_to_bool_array, num_binary_digits=4)
    bool_patterns = list(map(pattern_to_bool, patterns))

    gates_did_trigger = []

    def read_gates_triggered() -> None:
        gates_did_trigger.clear()
        for gater in dut.core.apd_gaters:
            # NOTE: doesn't like yield in iterator syntax...
            gates_did_trigger.append(bool((yield gater.triggered)))

    # Sweep the event times through the window, and check that it triggers properly.
    for signal_time in range(ref_time, cycle_length_ns + 20):
        _LOGGER.info("Testing signal_time (mod cycle_length) = %i", signal_time)

        # run a few dummy cycles where no signal occurs
        yield from dut.set_event_times([cycle_length_ns + 10] * input_chans)
        yield from dut.start_entanglement_generator()
        for cyc in range(failed_cycles):
            yield from wait_until(dut.core.msm.cycle_ending, max_cycles=cycle_length_ns)
            yield from read_gates_triggered()
            yield
            try:
                assert not any(gates_did_trigger)
            except AssertionError as err:
                _LOGGER.error("Gates triggered (none should): %s", gates_did_trigger)
                raise err
            assert not bool((yield dut.core.msm.success))
            cyc_completed = yield dut.core.msm.cycles_completed
            # _LOGGER.debug("Cycles completed: %i", cyc_completed)
            assert cyc_completed == cyc + 1

        # now, allow entanglement to happen
        yield from dut.set_event_times([signal_time] * input_chans)

        yield from wait_until(dut.core.msm.cycle_ending, max_cycles=cycle_length_ns)
        yield  # advance to IDLE state, I think

        # check the proper output events occurred
        yield from read_gates_triggered()
        gates_should_trigger = [
            t1 <= (signal_time - ref_time) <= t2 for t1, t2 in gate_windows
        ]
        try:
            assert gates_did_trigger == gates_should_trigger
        except AssertionError as err:
            _LOGGER.debug("Time elapsed since ref: %i", signal_time - ref_time)
            _LOGGER.debug("Window times (rel to reference): %s", gate_windows)
            _LOGGER.error(
                "Triggered: %s, should_trigger: %s",
                gates_did_trigger,
                gates_should_trigger,
            )
            raise err

        entanglement_did_succeed = yield dut.core.msm.success
        triggers_in_pattern_format = list(reversed(gates_did_trigger))
        entanglement_should_succeed = any(
            triggers_in_pattern_format == pat for pat in bool_patterns
        )
        try:
            assert entanglement_did_succeed == entanglement_should_succeed
        except AssertionError as err:
            _LOGGER.error(
                "Expected, measured entanglement: %s, %s",
                entanglement_should_succeed,
                bool(entanglement_did_succeed),
            )
            raise err
        assert (yield dut.core.msm.cycles_completed) == failed_cycles + 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    dut = CoreTestHarness(use_reference=True)
    run_simulation(dut, standalone_test(dut), vcd_name="core_standalone.vcd")

    dut = CoreTestHarness(use_reference=True)
    run_simulation(
        dut,
        standalone_test_parametrized(dut, cycle_length=20, failed_cycles=3),
        vcd_name="core_standalone_param_1.vcd",
    )

    dut = CoreTestHarness(use_reference=True)
    run_simulation(
        dut,
        standalone_test_parametrized(dut, cycle_length=50, failed_cycles=3),
        vcd_name="core_standalone_param_2.vcd",
    )

"""Test the :class:`entangler.core.PatternMatcher` properly pattern matches."""
import itertools
import logging

import pkg_resources
import pytest
from dynaconf import LazySettings
from migen import run_simulation

from entangler.core import PatternMatcher

_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)


def check_one_pattern_set(dut, pattern_set):
    """Test pattern recognition in the :class:`PatternMatcher`."""
    # set patterns to be matched to the given pattern_set
    num_signals = len(dut.sig)
    for i, p in enumerate(pattern_set):
        yield dut.patterns[i].eq(p)
    yield

    # check that is_match is only asserted on a valid pattern match
    for j in range(2 ** len(pattern_set)):
        yield dut.pattern_ens.eq(j)
        yield
        for i in range(2 ** num_signals):
            yield dut.sig.eq(i)
            yield
            assert (yield dut.is_match) == any(
                (p == i and (j & 2 ** n) for n, p in enumerate(pattern_set))
            )


def check_all_possible_patterns(dut: PatternMatcher):
    """Test all possible pattern sets in the :class:`PatternMatcher`.

    Args:
        num_patterns: number of patterns that the ``dut`` can match against
    """
    num_inputs = len(dut.sig)
    num_patterns = len(dut.patterns)
    all_possible_patterns = itertools.permutations(range(2 ** num_inputs), num_patterns)

    for pattern_set in all_possible_patterns:
        _LOGGER.debug("Testing pattern: %s", pattern_set)
        yield from check_one_pattern_set(dut, pattern_set)


@pytest.fixture()
def pattern_dut() -> PatternMatcher:
    """Create a PatternMatcher for sim."""
    return PatternMatcher(
        num_inputs=settings.NUM_INPUT_SIGNALS,
        num_patterns=settings.NUM_PATTERNS_ALLOWED,
    )


@pytest.mark.slow
def test_all_patterns(request, pattern_dut):
    """Test every possible pattern combination on a PatternMatcher."""
    run_simulation(
        pattern_dut,
        check_all_possible_patterns(pattern_dut),
        vcd_name=(request.node.name + ".vcd"),
    )


@pytest.mark.parametrize("pattern", [(0b1100, 0b0011, 0b1010, 0b0101)])
def test_one_pattern(request, pattern_dut, pattern):
    """Test a single pattern set at a time of the PatternMatcher."""
    run_simulation(
        pattern_dut,
        check_one_pattern_set(pattern_dut, pattern),
        vcd_name=(request.node.name + ".vcd"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    num_patterns = settings.NUM_PATTERNS_ALLOWED
    num_signals = settings.NUM_INPUT_SIGNALS
    dut = PatternMatcher(num_inputs=num_signals, num_patterns=num_patterns)
    run_simulation(
        dut, check_all_possible_patterns(dut), vcd_name="heralder.vcd",
    )

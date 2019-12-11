"""Test the :class:`entangler.core.PatternMatcher` properly pattern matches."""
import itertools
import logging

import pkg_resources
from dynaconf import LazySettings
from migen import run_simulation

from entangler.core import PatternMatcher

_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)


def test_match_one_pattern_set(dut, pattern_set, num_signals):
    """Test pattern recognition in the :class:`PatternMatcher`."""
    # set patterns to be matched to the given pattern_set
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


def test_all_possible_patterns(dut, num_inputs, num_patterns):
    """Test all possible pattern sets in the :class:`PatternMatcher`.

    Args:
        num_patterns: number of patterns that the ``dut`` can match against
    """
    all_possible_patterns = itertools.permutations(range(2 ** num_inputs), num_patterns)

    for pattern_set in all_possible_patterns:
        _LOGGER.debug("Testing pattern: %s", pattern_set)
        yield from test_match_one_pattern_set(dut, pattern_set, num_signals=num_inputs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    num_patterns = settings.NUM_PATTERNS_ALLOWED
    num_signals = settings.NUM_INPUT_SIGNALS
    dut = PatternMatcher(num_inputs=num_signals, num_patterns=num_patterns)
    run_simulation(
        dut,
        test_all_possible_patterns(dut, num_signals, num_patterns),
        vcd_name="heralder.vcd",
    )

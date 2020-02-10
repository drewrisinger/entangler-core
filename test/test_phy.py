"""Test the :class:`entangler.phy.Entangler` functionality."""
import logging
import os
import sys

import pkg_resources
import pytest
from dynaconf import LazySettings
from migen import run_simulation  # noqa: E402

import entangler.phy

# add gateware simulation tools "module" (at ./helpers/*)
sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))


# ./helpers/gateware_utils
from gateware_utils import advance_clock  # noqa: E402 pylint: disable=import-error
from phytester import PhyTestHarness  # noqa: E402 pylint: disable=import-error


settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)
_LOGGER = logging.getLogger(__name__)

def basic_phy_check(dut: PhyTestHarness):
    """Test the entire :mod:`entangler` gateware basic functionality works."""
    _LOGGER.debug("Starting basic_phy_check")
    yield dut.phy_ref.t_event.eq(1000)
    yield dut.phy_apd0.t_event.eq(1000)
    yield dut.phy_apd1.t_event.eq(1000)

    yield from advance_clock(5)
    yield from dut.write(entangler.phy.ADDRESS_WRITE.CONFIG, 0b110)  # standalone, master, disable
    yield from dut.write_heralds([0b0101, 0b1010, 0b1100, 0b0101])
    for i in range(settings.NUM_OUTPUT_CHANNELS):
        # set outputs to be on for 1 coarse clock cycle
        yield from dut.write(
            entangler.phy.ADDRESS_WRITE.TIMING + i, (2 * i + 2) * (1 << 16) | 2 * i + 1
        )
    # for i in [0, 2]:
    #     yield from dut.write(entangler.phy.ADDRESS_WRITE.TIMING + 4 + i, (30 << 16) | 18)
    # for i in [1, 3]:
    #     yield from dut.write(entangler.phy.ADDRESS_WRITE.TIMING + 4 + i, (1000 << 16)
    #       | 1000)
    yield from dut.write(entangler.phy.ADDRESS_WRITE.TCYCLE, 30)
    yield from dut.write(entangler.phy.ADDRESS_WRITE.CONFIG, 0b111)  # Enable standalone
    yield from dut.write(entangler.phy.ADDRESS_WRITE.RUN, int(2e3 / 8))

    yield from advance_clock(1000)
    # for i in range(1000):
    #     # if i==200:
    #     #     yield dut.phy_ref.t_event.eq( 8*10+3 )
    #     #     yield dut.phy_apd0.t_event.eq( 8*10+3 + 18)
    #     #     yield dut.phy_apd1.t_event.eq( 8*10+3 + 30)
    #     yield

    yield from dut.write(entangler.phy.ADDRESS_READ.STATUS, 0)  # Read status
    yield
    yield from dut.write(entangler.phy.ADDRESS_READ.NCYCLES, 0)  # Read n_cycles
    yield
    yield from dut.write(entangler.phy.ADDRESS_READ.TIME_REMAINING, 0)  # Read time elapsed
    yield
    for i in range(5):
        yield from dut.write(entangler.phy.ADDRESS_READ.TIMESTAMP + i, 0)  # Read input timestamps
        yield
    yield from advance_clock(5)


def check_phy_timeout(dut: PhyTestHarness):
    """Test that :mod:`entangler` timeout works.

    Sweeps the timeout to occur at all possible points in the state machine operation.
    """
    _LOGGER.debug("Starting basic_phy_check")
    # Declare internal helper functions.
    def do_timeout(timeout, n_cycles=10):
        yield
        yield from dut.write(
            entangler.phy.ADDRESS_WRITE.CONFIG, 0b110
        )  # disable, standalone
        yield from dut.write(entangler.phy.ADDRESS_WRITE.TCYCLE, n_cycles)
        yield from dut.write(entangler.phy.ADDRESS_WRITE.CONFIG, 0b111)  # Enable standalone
        yield from dut.write(entangler.phy.ADDRESS_WRITE.RUN, timeout)

        timedout = False
        for i in range(timeout + n_cycles + 50):
            if (yield dut.core.rtlink.i.stb):
                data = yield dut.core.rtlink.i.data
                if data == 0x3FFF:
                    # This should be the first and only timeout
                    assert not timedout
                    # Timeout should happen in a timely fashion
                    assert i <= timeout + n_cycles + 5
                    timedout = True
            yield
        assert timedout

    for i in range(1, 20):
        yield from do_timeout(i, n_cycles=10)


@pytest.fixture
def phy_dut() -> PhyTestHarness:
    """Create an EntanglerPHY test harness for sim."""
    return PhyTestHarness()


ARTIQ_CLOCKS = {"sys": 8, "rio": 8, "rio_phy": 8}


@pytest.mark.parametrize("test_function", [basic_phy_check, check_phy_timeout],)
def test_phy_func(request, phy_dut: PhyTestHarness, test_function):
    """Run test functions on an Entangler PHY."""
    run_simulation(
        phy_dut,
        test_function(phy_dut),
        vcd_name=(request.node.name + ".vcd"),
        clocks=ARTIQ_CLOCKS,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    dut = PhyTestHarness()
    run_simulation(
        dut,
        basic_phy_check(dut),
        vcd_name="phy.vcd",
        clocks=ARTIQ_CLOCKS,
    )

    dut = PhyTestHarness()
    run_simulation(
        dut,
        check_phy_timeout(dut),
        vcd_name="phy_timeout.vcd",
        clocks=ARTIQ_CLOCKS,
    )

"""Gateware-side ARTIQ RTIO interface to the entangler core."""
import logging
import math
import typing

import pkg_resources
from artiq.gateware.rtio import rtlink
from dynaconf import LazySettings
from migen import Case
from migen import Cat
from migen import ClockDomainsRenamer
from migen import If
from migen import Module
from migen import Mux
from migen import Signal

from entangler.core import EntanglerCore

_LOGGER = logging.getLogger(__name__)
settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "/")
)
# noqa: E203


class Entangler(Module):
    """A module that can be plugged into the ARTIQ gateware build process.

    It takes inputs from the ARTIQ RTIO bus, and passes them into the lower level
    Entangler class (:class:`.core.EntanglerCore`).
    """

    def __init__(
        self,
        core_link_pads,
        output_pads,
        passthrough_sigs: typing.Sequence[Signal],
        input_phys: typing.Sequence["PHY"],
        reference_phy=None,
        simulate: bool = False,
    ):
        """
        Define the interface between an ARTIQ RTIO bus and low-level gateware.

        Args:
            core_link_pads: EEM pads for inter-Kasli link (see ``README.md`` in
                this folder for more info)
            output_pads: pads for 4 output signals
                (Oxford: 422sigma, 1092, 422 ps trigger, aux)
            passthrough_sigs (Sequence[PHY]): signals from output PHYs, connected to
                output_pads when core not running
            input_phys: serializer-deserializer PHYs for 4 inputs: APD0-3
            reference_phy (PHY): a reference trigger signaling that this is a valid
                cycle and triggering the start of the input windows.
                In Oxford's experiment, this is a 422ps pulsed laser. This is an
                optional parameter, this module works perfectly fine without a
                reference trigger.
            simulate (bool): Whether this module is being simulated. Simulation disables
                some checks (for input sizes) that are run on instantiation.
                This is mostly passed through to lower levels, where the behavior
                actually does change in simulation/non-simulation modes.
        """
        # width of fine & coarse timestamp/timer
        FULL_COUNTER_WIDTH = settings.FULL_COUNTER_WIDTH

        def max_value_to_bit_width(max_value: int) -> int:
            """Calculate how many bits are needed to represent an unsigned int."""
            return math.ceil(math.log2(max_value))

        # should eval to 14, but might change.
        PHY_DATA_INPUT_WIDTH = max(
            (
                FULL_COUNTER_WIDTH,
                max_value_to_bit_width(settings.MAX_CYCLES_PER_RUN),
                max_value_to_bit_width(settings.MAX_TRIGGER_COUNTS),
            )
        )
        num_herald_patterns = settings.NUM_PATTERNS_ALLOWED
        num_inputs = settings.NUM_INPUT_SIGNALS
        num_outputs = settings.NUM_OUTPUT_CHANNELS
        timing_bit_width = math.ceil(math.log2(num_inputs + num_outputs))
        _LOGGER.debug(
            "PHY Comm (addr) format: [read?, external IO?, addr] = (MSB->LSB): "
            "[%i,%i,%i:0]",
            timing_bit_width + 1,
            timing_bit_width,
            timing_bit_width - 1,
        )
        _LOGGER.debug("Total output address bits: %i", timing_bit_width + 2)
        if num_inputs != 4 or num_outputs != 4:
            _LOGGER.warning(
                "Using non-standard number of I/O to Entangler. "
                "Make sure that your addresses (in settings.toml) correspond to "
                "correct # of bits! Format (MSB->LSB): [read?, external I/O, "
                "len=Log2(I + O)]"
            )

        self.rtlink = rtlink.Interface(
            rtlink.OInterface(
                data_width=32, address_width=timing_bit_width + 2, enable_replace=False
            ),
            rtlink.IInterface(data_width=PHY_DATA_INPUT_WIDTH, timestamped=True),
        )

        assert len(input_phys) == num_inputs
        if not simulate:
            assert len(core_link_pads) >= 5 if reference_phy is not None else 4
            assert len(output_pads) == num_outputs
            assert len(passthrough_sigs) == num_outputs

        # # #

        self.submodules.core = ClockDomainsRenamer("rio")(
            EntanglerCore(
                core_link_pads,
                output_pads,
                passthrough_sigs,
                input_phys,
                reference_phy=reference_phy,
                simulate=simulate,
            )
        )

        read_en = self.rtlink.o.address[timing_bit_width + 1]  # MSB in address
        write_timings = Signal()
        self.comb += [
            self.rtlink.o.busy.eq(0),
            write_timings.eq(
                self.rtlink.o.address[timing_bit_width : timing_bit_width + 2] == 1
            ),
        ]

        output_t_starts = [seq.m_start for seq in self.core.sequencers]
        output_t_ends = [seq.m_stop for seq in self.core.sequencers]
        output_t_starts += [gater.gate_start for gater in self.core.apd_gaters]
        output_t_ends += [gater.gate_stop for gater in self.core.apd_gaters]
        cases = {}
        for i in range(len(output_t_starts)):
            cases[i] = [
                output_t_starts[i].eq(self.rtlink.o.data[:16]),
                output_t_ends[i].eq(self.rtlink.o.data[16:]),
            ]

        # Write timeout counter and start core running
        self.comb += [
            self.core.msm.timeout_input.eq(self.rtlink.o.data),
            self.core.msm.run_stb.eq((self.rtlink.o.address == 1) & self.rtlink.o.stb),
        ]

        herald_enable_bit_range = (
            num_herald_patterns * num_inputs,
            num_herald_patterns * num_inputs + num_herald_patterns,
        )
        self.sync.rio += [
            If(
                write_timings & self.rtlink.o.stb,
                Case(self.rtlink.o.address[0:timing_bit_width], cases),
            ),
            If(
                (self.rtlink.o.address == settings.ADDRESS_WRITE.CONFIG)
                & self.rtlink.o.stb,  # noqa: W503
                # Write config
                self.core.enable.eq(self.rtlink.o.data[0]),
                self.core.msm.standalone.eq(self.rtlink.o.data[2]),
            ),
            If(
                (self.rtlink.o.address == settings.ADDRESS_WRITE.TCYCLE)
                & self.rtlink.o.stb,  # noqa: W503
                # Write cycle length
                self.core.msm.cycle_length_input.eq(self.rtlink.o.data[:10]),
            ),
            If(
                (self.rtlink.o.address == settings.ADDRESS_WRITE.HERALD)
                & self.rtlink.o.stb,  # noqa: W503
                # Write herald patterns and enables
                *[
                    self.core.heralder.patterns[i].eq(
                        self.rtlink.o.data[num_inputs * i : num_inputs * (i + 1)]
                    )
                    for i in range(num_herald_patterns)
                ],
                self.core.heralder.pattern_ens.eq(
                    self.rtlink.o.data[
                        herald_enable_bit_range[0] : herald_enable_bit_range[1]
                    ]
                )
            ),
        ]

        # Write is_master bit in rio_phy reset domain to not break 422ps trigger
        # forwarding on core.reset().
        self.sync.rio_phy += If(
            (self.rtlink.o.address == 0) & self.rtlink.o.stb,
            self.core.msm.is_master.eq(self.rtlink.o.data[1]),
        )
        # TODO: what is reset domain??

        read = Signal()
        read_timings = Signal()
        read_addr = Signal(3)

        # Input timestamps are [apd0, apd1, apd2, apd3, (OPTIONAL: reference)]
        # timestamps will be 0 if they did not trigger
        input_timestamps = [gater.sig_ts for gater in self.core.apd_gaters]
        if reference_phy is not None:
            input_timestamps.append(self.core.apd_gaters[0].ref_ts)
        cases = {}
        timing_data = Signal(FULL_COUNTER_WIDTH)
        for i, ts in enumerate(input_timestamps):
            cases[i] = [timing_data.eq(ts)]
        self.comb += Case(read_addr, cases)

        # on bus strobe, set signals to read register
        self.sync.rio += [
            If(read, read.eq(0)),
            If(
                self.rtlink.o.stb,
                read.eq(read_en),
                read_timings.eq(
                    self.rtlink.o.address[timing_bit_width : timing_bit_width + 2]
                    == 0b11  # noqa: W503
                ),
                read_addr.eq(self.rtlink.o.address[:timing_bit_width]),
            ),
        ]

        status = Signal(3)
        self.comb += status.eq(
            Cat(self.core.msm.ready, self.core.msm.success, self.core.msm.timeout)
        )

        reg_read = Signal(PHY_DATA_INPUT_WIDTH)
        cases = {}
        cases[0] = [reg_read.eq(status)]
        cases[1] = [reg_read.eq(self.core.msm.cycles_completed)]
        cases[2] = [reg_read.eq(self.core.msm.time_remaining)]
        cases[3] = [reg_read.eq(self.core.triggers_received)]
        self.comb += Case(read_addr, cases)

        # Generate an input event if we have a read request RTIO Output event, or if the
        # core has finished. If the core is finished output the herald match, or 0x3fff
        # on timeout.
        #
        # Simultaneous read requests and core-done events are not currently handled, but
        # are easy to avoid in the client code.
        self.comb += [
            self.rtlink.i.stb.eq(read | self.core.enable & self.core.msm.done_stb),
            self.rtlink.i.data.eq(
                Mux(
                    self.core.enable & self.core.msm.done_stb,
                    Mux(self.core.msm.success, self.core.heralder.matches, 0x3FFF),
                    Mux(read_timings, timing_data, reg_read),
                )
            ),
        ]

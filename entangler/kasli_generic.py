"""Add support for the Entangler to the generic Kasli builder.

Effectively adds :mod:`entangler` to kasli_generic builder
(artiq/gateware/kasli_generic.py) and the EEM module
(artiq/gateware/eem.py).

This requires that either your ARTIQ branch include
``52112d54f9c052159b88b78dc6bd712abd4f062c``, or use the equivalent
``kasli_generic-expose-peripheral_processors-dict.patch`` in this module.

You can apply patches with ``$ git apply PATCH_FILE``.
"""
import logging
import typing

import artiq.gateware.eem as eem_mod
import artiq.gateware.rtio as rtio
import artiq.gateware.targets.kasli_generic as kasligen
import pkg_resources
from artiq.gateware.rtio.phy import ttl_serdes_7series
from artiq.gateware.rtio.phy import ttl_simple
from dynaconf import LazySettings
from migen import Signal
from migen.build.generic_platform import ConstraintError
from migen.build.generic_platform import IOStandard
from migen.build.generic_platform import Pins
from migen.build.generic_platform import Subsignal

import entangler.phy

_LOGGER = logging.getLogger(__name__)
entangler_settings = LazySettings(
    ROOT_PATH_FOR_DYNACONF=pkg_resources.resource_filename("entangler", "")
)


def peripheral_entangler(module, peripheral: typing.Dict[str, list]):
    """Add an Ion-Photon entangling gateware device to an ARTIQ SoC.

    Expected format:
        {
            "type": "entangler",
            "ports": [list of ints],
            {OPTIONAL} "uses_reference": bool,
            {OPTIONAL} "link_eem": int,
            {OPTIONAL} "interface_on_lower": bool,
        }

    More details in :class:`EntanglerEEM`.
    """
    using_ref = peripheral.get("uses_reference", False)
    num_inputs = entangler_settings.NUM_INPUT_SIGNALS
    num_outputs = entangler_settings.NUM_OUTPUT_CHANNELS
    if using_ref:
        # add reference
        num_inputs += 1

    num_eem = len(peripheral["ports"]) + len(peripheral.get("link_eem", list()))
    if peripheral.get("link_eem", None) is not None:
        # Using inter-Kasli/Entangler communication
        num_link_pins = 5 if using_ref else 4
    else:
        num_link_pins = 0

    if (num_eem * 8) < num_inputs + num_outputs + num_link_pins:
        _LOGGER.warning(
            "Maybe insufficient number of I/O EEM boards. "
            "Must use Interface to get sufficient number, or another DIO EEM. "
            "Expecting %i total I/O",
            num_inputs + num_outputs + num_link_pins,
        )
    _LOGGER.info("Adding entangler to Kasli. Params: %s", peripheral)
    EntanglerEEM.add_std(
        module,
        eem_dio=peripheral["ports"],
        eem_interface=peripheral.get("link_eem", None),
        uses_reference=using_ref,
        interface_on_lower=peripheral.get("interface_on_lower", True),
    )


# add entangler processor to the standard kasli_generic processors
kasligen.peripheral_processors["entangler"] = peripheral_entangler


# pylint: disable=protected-access
class EntanglerEEM(eem_mod._EEM):
    """Define the pins and gateware/logic used by the Entangler.

    If you are using this extension, you should NOT use the corresponding EEM(s)
    elsewhere (e.g. as DIO).
    """

    @staticmethod
    def io(
        eem_dio: typing.Sequence[int],
        eem_interface: int = None,
        uses_reference: bool = False,
        interface_on_lower: bool = True,
        iostandard: str = "LVDS_25",
    ) -> typing.Sequence["Pad_Assignments"]:
        """Define the IO pins used by the Entangler device.

        Args:
            eem_interface (Optional[int]): An optional EEM for interfacing between
                distributed Entanglers (on separate Kasli).
                Set to None for no interface.
            eem_dio (Sequence[int]): EEM numbers for the DIO cards to be used by
                the Entangler. Should be <= (num_inputs + num_outputs, in
                ``settings.toml``). Must have at least one.
            uses_reference (bool): If you are using a reference signal/trigger
                to the Entangler. Defaults to False.
            interface_on_lower (bool): If not using a reference, you need less
                interface pins, which this supports by assigning half of one
                I/O bank (=4 pins) to Interface, and other half to DIO.
                This selects whether the lower (0-3) or upper (4-7) pins should
                be Interface. Others will be DIO.
            iostandard (str): Defines the voltage/communication standard for the pins.
                Defaults to differential ("LVDS_25").

        Returns:
            Sequence["Pad_Assignments"]: Pins meant for defining an EEM platform
            extension.
            Each consists of a connector/bus name, pin name, Subsignals, and other
            parameters like IO Standards.
            Similar to Xilinx/Altera pin config files (``*.ucf``).

        """
        ios = []
        if not isinstance(eem_dio, list):
            eem_dio = [eem_dio]
        for eem in eem_dio:
            ios.extend(eem_mod.DIO.io(eem))
        if eem_interface is not None:
            if not uses_reference:
                num_interface_pads = 4
                if interface_on_lower:
                    pad_range = list(range(0, 4))
                    dio_range = list(range(4, 8))
                else:
                    pad_range = list(range(4, 8))
                    dio_range = list(range(0, 4))
            else:
                # doesn't give lower/upper option for reference, just start at 0
                num_interface_pads = 5
                pad_range = list(range(num_interface_pads))
                dio_range = list(range(num_interface_pads, 8))

            _LOGGER.debug(
                "Creating inter-Kasli Entangler state machine interface on "
                "EEM %i, using %i pads (%s)",
                eem_interface,
                num_interface_pads,
                pad_range,
            )
            # pylint: disable=protected-access
            if_io = [
                (
                    "if{}".format(eem_interface),
                    i,
                    Subsignal("p", Pins(eem_mod._eem_pin(eem_interface, i, "p"))),
                    Subsignal("n", Pins(eem_mod._eem_pin(eem_interface, i, "n"))),
                    IOStandard(iostandard),
                )
                for i in pad_range
            ]
            if len(dio_range) != 0:
                # populate remainder with DIO
                if_io.extend(
                    [
                        (
                            "dio{}".format(eem_interface),
                            i,
                            Subsignal(
                                "p",
                                Pins(eem_mod._eem_pin(eem_interface, real_pin, "p")),
                            ),
                            Subsignal(
                                "n",
                                Pins(eem_mod._eem_pin(eem_interface, real_pin, "n")),
                            ),
                            IOStandard(iostandard),
                        )
                        for i, real_pin in enumerate(dio_range)
                    ]
                )
            ios.extend(if_io)
        else:
            _LOGGER.info("NOT using inter-Kasli Entangler interface")
        return ios

    @classmethod
    def add_std(
        cls,
        target: "MiniSoC",  # noqa: F821
        eem_dio: typing.Sequence[int],
        eem_interface: typing.Optional[int] = None,
        uses_reference: bool = False,
        interface_on_lower: bool = True,
    ):
        """Add an Entangler PHY to a Kasli gateware module.

        Args:
            target (Module): The gateware module the Entangler will be added to.
            eem_dio (typing.Sequence[int]): A list of EEM ports that are connected
                to DIO boards, which are used for the inputs & outputs from the
                Entangler.
            eem_interface (typing.Optional[int]): The EEM number where the
                inter-Entangler interface pins will be located.
                Should be connected to a DIO board.
                If set to None, assumes the Entangler is standalone (no remote
                Entangler on a different Kasli) and does not instantiate interface.
            uses_reference (bool, optional): If the Entangler PHY is designed
                to be used in conjunction with a reference trigger/signal.
                For example, if the entanglement can only be generated relative
                to a pulsed laser (as in Oxford). Defaults to False.
            interface_on_lower (bool, optional): See :meth:`io` for details.
                Basically, if no reference is used, should the 4 pins for
                communication be on the lower or upper half of the DIO bank.
                Defaults to True.

        Note:
            Pin assignment ordering: Pins are assigned in the following order:
            Outputs, Inputs.
            We first try to fill up the eem_dio pads, then the eem_interface pads.
            This means that the Input pins could be assigned to the same EEM
            as the inter-Kasli Entangler communication.
            If that's not desired, feel free to rewrite it yourself.

            Built liberally off Oxford's draft EEM code, though greatly extended.
        """
        cls.add_extension(
            target,
            eem_dio,
            eem_interface=eem_interface,
            uses_reference=uses_reference,
            interface_on_lower=interface_on_lower,
        )

        io_class = {
            "input": ttl_serdes_7series.Input_8X,
            "output": ttl_simple.Output,
        }
        num_outputs = entangler_settings.NUM_OUTPUT_CHANNELS
        num_inputs = entangler_settings.NUM_INPUT_SIGNALS
        if uses_reference:
            num_inputs += 1
        num_if_pins = 5 if uses_reference else 4

        # Wanted to do this with itertools, but didn't know how. So this is quick
        # Chains eem_dio pins, then eem_interface's DIO pins (if exist).
        # Forces outputs,inputs to go to DIO EEM (ports in JSON) first, then interface
        all_dio_pins = []
        for eem in eem_dio:
            all_dio_pins.extend(
                (target.platform.request("dio{}".format(eem), i) for i in range(8))
            )
        if eem_interface is not None:
            try:
                for i in range(8):
                    all_dio_pins.append(
                        target.platform.request("dio{}".format(eem_interface), i)
                    )
            except ConstraintError:
                _LOGGER.debug(
                    "Added %i DIO pins from EEM_interface %i (expected %i)",
                    i,
                    eem_interface,
                    8 - num_if_pins,
                )
        dio_pins_iter = iter(all_dio_pins)
        _LOGGER.debug(
            "Total of %i DIO pins are available for Input/Output", len(all_dio_pins)
        )
        if num_inputs + num_outputs > len(all_dio_pins):
            _LOGGER.error(
                "Trying to allocate more output pins (%i) than provided (%i)",
                num_inputs + num_outputs,
                len(all_dio_pins),
            )

        # *** Create PHYs for outputs then inputs (then reference, opt) ***
        output_pads = []
        output_sigs = [Signal() for _ in range(num_outputs)]
        # Assign Entangler outputs to pads, create PHYs
        for i in range(num_outputs):
            pads = next(dio_pins_iter)
            output_pads.append(pads)
            phy = io_class["output"](output_sigs[i])
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        # Create specified # of inputs, add them to list for Entangler creation.
        input_phys = []
        for i in range(num_inputs):
            pads = next(dio_pins_iter)
            if int(pads.name.lstrip("dio")) == eem_interface:
                _LOGGER.info("Assigning Input[%i] to Interface Board", i)
            phy = io_class["input"](pads.p, pads.n)
            target.submodules += phy
            input_phys.append(phy.rtlink.i)
            target.rtio_channels.append(rtio.Channel.from_phy(phy))

        # add reference PHY
        if uses_reference:
            _LOGGER.debug("Adding reference PHY")
            pads = next(dio_pins_iter)
            phy = io_class["input"](pads.p, pads.n)
            target.submodules += phy
            reference_phy = phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
        else:
            reference_phy = None

        if eem_interface is not None:
            if_pads = [
                target.platform.request("if{}".format(eem_interface), i)
                for i in range(num_if_pins)
            ]
        else:
            if_pads = None

        # *** Add PHYs to Entangler gateware ***
        phy = entangler.phy.Entangler(
            core_link_pads=if_pads,
            output_pads=output_pads,
            passthrough_sigs=output_sigs,
            input_phys=input_phys,
            reference_phy=reference_phy,
            simulate=False,
        )
        target.submodules += phy
        target.rtio_channels.append(rtio.Channel.from_phy(phy))

        # allocate the leftover pins to DIO output. Could maybe change to InOut?
        for pad in dio_pins_iter:
            phy = io_class["output"](pad.p, pad.n)
            target.submodules += phy
            target.rtio_channels.append(rtio.Channel.from_phy(phy))
            _LOGGER.debug(
                "Added output %s to Entangler DIO (either interface or port "
                "if In + Out < len(ports) * 8)",
                pad.name,
            )


if __name__ == "__main__":
    # run the basic kasli_generic with logging & the entangler processor.
    logging.basicConfig(level=logging.DEBUG)
    kasligen.main()

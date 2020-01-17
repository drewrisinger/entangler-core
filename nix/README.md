# Nix Scripts

## Assumptions

This assumes that you have already added the main ARTIQ Nix channel (<artiq-full>, see [ARTIQ Manual](https://m-labs.hk/artiq/manual/installing.html#installing-via-nix-linux)).

## Entangler package

To build gateware, the entangler package relies on a relatively new ARTIQ commit (52112d54f9c052159b88b78dc6bd712abd4f062c),
seen in artiq/gateware/targets/kasli_generic.py.
We need to patch <artiq-full>.artiq to apply this, but other than that we use standard ARTIQ.
If you just want to use the entangler package, simply call ``$(entanglerSrc)/nix``, and add that to your environment.

## Building Entangler Gateware

To launch a shell where you can build Entangler Gateware, you need a Xilinx license and a local ARTIQ repo clone. You can then build the
Entangler gateware with

```bash
nix-shell -I artiqSrc=/PATH/TO/ARTIQ/REPO/ /ENTANGLER/PATH/nix/entangler-shell-dev.nix --run "python -m entangler.kasli_generic /PATH/TO/KASLI_DESCRIPTOR.json"
```

This can then be flashed with:
```bash
# following line from ARTIQ manual
artiq_mkfs flashstorage_with_mac_and_ip.img -s ip IP.ADDRESS.X.Y -s mac FU:LL:MA:C0:AD:DR
artiq_flash -t kasli -V KASLI_DESCRIPTOR_NAME -d ./artiq_kasli/ --srcbuild -f flashstorage_with_mac_and_ip.img
```

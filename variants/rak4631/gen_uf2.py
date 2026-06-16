# PlatformIO post-build: convert firmware.hex -> firmware.uf2 for RAK4631 (nRF52840)
# drag-and-drop flashing via the Adafruit/WisBlock UF2 bootloader.
Import("env")
import os

NRF52840_UF2_FAMILY = "0xADA52840"

def gen_uf2(source, target, env):
    build_dir = env.subst("$BUILD_DIR")
    hexfile = os.path.join(build_dir, "firmware.hex")
    uf2file = os.path.join(build_dir, "firmware.uf2")
    if not os.path.isfile(hexfile):
        print("gen_uf2: %s not found, skipping uf2 generation" % hexfile)
        return
    fw_dir = env.PioPlatform().get_package_dir("framework-arduinoadafruitnrf52")
    uf2conv = os.path.join(fw_dir, "tools", "uf2conv", "uf2conv.py")
    if not os.path.isfile(uf2conv):
        print("gen_uf2: uf2conv.py not found at %s, skipping" % uf2conv)
        return
    env.Execute('"$PYTHONEXE" "%s" "%s" -c -f %s -o "%s"' %
                (uf2conv, hexfile, NRF52840_UF2_FAMILY, uf2file))
    print("gen_uf2: wrote %s" % uf2file)

env.AddPostAction("$BUILD_DIR/${PROGNAME}.hex", gen_uf2)

import os
import platform


def _detect_platform():
    system = platform.system()
    machine = platform.machine().lower()

    if "ANDROID_STORAGE" in os.environ:
        if "arm64" in machine or "aarch64" in machine:
            return "android_arm", "libtorrest.so", "torrest"
        if "arm" in machine:
            return "android_arm", "libtorrest.so", "torrest"
        return "android_arm", "libtorrest.so", "torrest"

    raise RuntimeError("Lordplayer Droid only supports Android: %s / %s" % (system, machine))


PLATFORM, LIB_NAME, EXE_NAME = _detect_platform()

import os
import platform
import struct


def _detect_platform():
    system = platform.system()
    machine = platform.machine().lower()

    if "ANDROID_STORAGE" in os.environ:
        if "arm64" in machine or "aarch64" in machine:
            return "android_arm64", "libtorrest.so", "torrest"
        if "arm" in machine:
            return "android_arm", "libtorrest.so", "torrest"
        if "x86_64" in machine or "amd64" in machine:
            return "android_x64", "libtorrest.so", "torrest"
        if "x86" in machine or "i686" in machine or "i386" in machine:
            return "android_x86", "libtorrest.so", "torrest"

    if system == "Windows":
        bits = struct.calcsize("P") * 8
        plat = "windows_x64" if bits == 64 else "windows_x86"
        return plat, "libtorrest.dll", "torrest.exe"

    if system == "Linux":
        if "arm64" in machine or "aarch64" in machine:
            return "linux_arm64", "libtorrest.so", "torrest"
        if "arm" in machine:
            return "linux_arm", "libtorrest.so", "torrest"
        return "linux_x64", "libtorrest.so", "torrest"

    if system == "Darwin":
        return "darwin", "libtorrest.dylib", "torrest"

    raise RuntimeError("Unsupported platform: %s / %s" % (system, machine))


PLATFORM, LIB_NAME, EXE_NAME = _detect_platform()

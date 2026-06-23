import os
import platform
import struct


def _get_android_abi():
    try:
        import subprocess
        return subprocess.check_output(["getprop", "ro.product.cpu.abi"], timeout=2).decode("utf-8", errors="replace").strip()
    except:
        return ""

def _detect_platform():
    system = platform.system()
    machine = platform.machine().lower()

    if "ANDROID_STORAGE" in os.environ:
        abi = _get_android_abi()
        if abi == "arm64-v8a":
            return "android_arm64", "libtorrest.so", "torrest"
        if abi in ("armeabi-v7a", "armeabi"):
            return "android_arm", "libtorrest.so", "torrest"
        if abi == "x86_64":
            return "android_x64", "", "torrest"
        if abi == "x86":
            return "android_x86", "", "torrest"
        # Fallback to platform.machine() if getprop fails
        if "arm64" in machine or "aarch64" in machine:
            return "android_arm64", "libtorrest.so", "torrest"
        if "arm" in machine:
            return "android_arm", "libtorrest.so", "torrest"
        if "x86_64" in machine or "amd64" in machine:
            return "android_x64", "", "torrest"
        if "x86" in machine or "i686" in machine or "i386" in machine:
            return "android_x86", "", "torrest"

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

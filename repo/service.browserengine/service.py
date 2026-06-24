# -*- coding: utf-8 -*-
import os
import subprocess
import time
import threading
import urllib.request
import zipfile
import xbmc
import xbmcvfs
import xbmcaddon

ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath("special://home/addons/service.browserengine")
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
FLARESOLVERR_DIR = os.path.join(ADDON_PATH, "bin", "flaresolverr")
FLARESOLVERR_EXE = os.path.join(FLARESOLVERR_DIR, "flaresolverr.exe")
FLARESOLVERR_URL = "https://github.com/FlareSolverr/FlareSolverr/releases/download/v3.3.21/flaresolverr_windows_x64.zip"
PORT = 8191

class FlareSolverrService:
    def __init__(self):
        self.process = None
        self.running = False
        self.monitor = None

    def _download_flaresolverr(self):
        if os.path.exists(FLARESOLVERR_EXE):
            return True
        xbmc.log("[BrowserEngine] Downloading FlareSolverr...", xbmc.LOGINFO)
        try:
            os.makedirs(FLARESOLVERR_DIR, exist_ok=True)
            zip_path = os.path.join(ADDON_DATA, "flaresolverr.zip")
            os.makedirs(ADDON_DATA, exist_ok=True)
            
            urllib.request.urlretrieve(FLARESOLVERR_URL, zip_path)
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(FLARESOLVERR_DIR)
            os.remove(zip_path)
            
            if os.path.exists(FLARESOLVERR_EXE):
                xbmc.log("[BrowserEngine] FlareSolverr downloaded", xbmc.LOGINFO)
                return True
        except Exception as e:
            xbmc.log("[BrowserEngine] Download failed: %s" % str(e), xbmc.LOGERROR)
        return False

    def start(self):
        if not self._download_flaresolverr():
            return False
        # Clean chromedriver cache to avoid permission errors
        try:
            import shutil
            chromedriver_cache = os.path.join(os.path.expanduser("~"), "appdata", "roaming", "undetected_chromedriver")
            if os.path.exists(chromedriver_cache):
                shutil.rmtree(chromedriver_cache, ignore_errors=True)
                xbmc.log("[BrowserEngine] Cleaned chromedriver cache", xbmc.LOGINFO)
        except:
            pass
        try:
            self.process = subprocess.Popen(
                [FLARESOLVERR_EXE],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                cwd=FLARESOLVERR_DIR,
            )
            xbmc.log("[BrowserEngine] FlareSolverr started", xbmc.LOGINFO)
            for _ in range(45):
                time.sleep(1)
                if self.monitor and self.monitor.abortRequested():
                    return False
                try:
                    req = urllib.request.Request("http://127.0.0.1:%d/" % PORT)
                    with urllib.request.urlopen(req, timeout=3):
                        xbmc.log("[BrowserEngine] FlareSolverr ready", xbmc.LOGINFO)
                        return True
                except:
                    pass
            return True
        except Exception as e:
            xbmc.log("[BrowserEngine] Failed to start: %s" % str(e), xbmc.LOGERROR)
            return False

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except:
                try: self.process.kill()
                except: pass
            self.process = None
            xbmc.log("[BrowserEngine] FlareSolverr stopped", xbmc.LOGINFO)

class BrowserEngineMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.service = FlareSolverrService()
        self.service.monitor = self

    def start(self):
        self.service.start()
        while not self.abortRequested():
            if self.waitForAbort(30):
                break
        self.service.stop()

monitor = BrowserEngineMonitor()
monitor.start()

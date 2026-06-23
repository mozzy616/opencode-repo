# -*- coding: utf-8 -*-
import os
import subprocess
import time
import threading

import xbmc
import xbmcvfs

ADDON_PATH = xbmcvfs.translatePath("special://home/addons/service.browserengine")
FLARESOLVERR_PATH = os.path.join(ADDON_PATH, "bin", "flaresolverr", "flaresolverr.exe")
PORT = 8191

class FlareSolverrService:
    def __init__(self):
        self.process = None
        self.running = False

    def start(self):
        if not os.path.exists(FLARESOLVERR_PATH):
            xbmc.log("[BrowserEngine] FlareSolverr not found at %s" % FLARESOLVERR_PATH, xbmc.LOGERROR)
            return False
        try:
            self.process = subprocess.Popen(
                [FLARESOLVERR_PATH, "--port", str(PORT), "--headless", "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            self.running = True
            xbmc.log("[BrowserEngine] FlareSolverr started on port %d" % PORT, xbmc.LOGINFO)

            # Wait for it to be ready
            for _ in range(30):
                time.sleep(1)
                if self.monitor and self.monitor.abortRequested():
                    break
                try:
                    import urllib.request
                    req = urllib.request.Request("http://127.0.0.1:%d/v1" % PORT)
                    with urllib.request.urlopen(req, timeout=3):
                        xbmc.log("[BrowserEngine] FlareSolverr ready", xbmc.LOGINFO)
                        return True
                except:
                    pass
            return True
        except Exception as e:
            xbmc.log("[BrowserEngine] Failed to start FlareSolverr: %s" % str(e), xbmc.LOGERROR)
            return False

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
            xbmc.log("[BrowserEngine] FlareSolverr stopped", xbmc.LOGINFO)

    def set_monitor(self, monitor):
        self.monitor = monitor

class BrowserEngineMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.service = FlareSolverrService()
        self.service.set_monitor(self)

    def start(self):
        self.service.start()
        while not self.abortRequested():
            if self.waitForAbort(30):
                break
        self.service.stop()

monitor = BrowserEngineMonitor()
monitor.start()

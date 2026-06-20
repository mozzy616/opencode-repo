# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import sys
import os
import json
import urllib.request
import urllib.parse
import time

HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()
REPO_URL = "https://mozzy616.github.io/opencode-repo"

ADDONS = [
    ("script.module.six", "script.module.six-1.16.0+matrix.1.zip"),
    ("script.module.kodi-six", "script.module.kodi-six-0.1.3.1.zip"),
    ("script.module.simplejson", "script.module.simplejson-3.19.1+matrix.1.zip"),
    ("script.module.requests", "script.module.requests-2.31.0.zip"),
    ("script.module.routing", "script.module.routing-0.2.3+matrix.1.zip"),
    ("script.module.resolveurl", "script.module.resolveurl-5.1.199.zip"),
    ("script.module.cocoscrapers", "script.module.cocoscrapers-1.0.29.zip"),
    ("script.favourites", "script.favourites-8.1.2.zip"),
    ("script.skinshortcuts", "script.skinshortcuts-2.0.3.zip"),
    ("script.image.resource.select", "script.image.resource.select-3.0.2.zip"),
    ("resource.images.studios.white", "resource.images.studios.white-0.0.34.zip"),
    ("resource.images.recordlabels.white", "resource.images.recordlabels.white-0.0.7.zip"),
    ("resource.images.weatherfanart.single", "resource.images.weatherfanart.single-0.0.6.zip"),
    ("inputstream.adaptive", "inputstream.adaptive-21.5.19.zip"),
    ("plugin.video.lordplayer", "plugin.video.lordplayer-1.0.0.zip"),
    ("plugin.video.streamlord", "plugin.video.streamlord-1.0.0.zip"),
    ("plugin.video.xprime", "plugin.video.xprime-1.0.1.zip"),
    ("plugin.program.koditoolbox", "plugin.program.koditoolbox-1.0.0.zip"),
    ("plugin.video.lordplayerxbox", "plugin.video.lordplayerxbox-1.0.0.zip"),
    ("skin.marmalade", "skin.marmalade-1.0.0.zip"),
]

def log(msg):
    xbmc.log("[MarmaladeWizard] %s" % msg, xbmc.LOGINFO)

def is_installed(addon_id):
    return os.path.exists(xbmcvfs.translatePath("special://home/addons/%s" % addon_id))

def download(url, dest):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MarmaladeWizard/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception as e:
        log("DOWNLOAD FAIL: %s -> %s" % (url, str(e)))
        return False

def main():
    progress = xbmcgui.DialogProgress()
    progress.create("Marmalade Wizard", "Installing repository...")

    # Step 1: Install repo
    rzip = xbmcvfs.translatePath("special://temp/repository.opencode.zip")
    rurl = REPO_URL + "/repository.opencode.zip"
    if download(rurl, rzip):
        xbmc.executebuiltin("InstallAddon(%s)" % rzip)
        xbmc.sleep(2000)
        xbmc.executebuiltin("UpdateAddonRepos")
        log("Repo installed")
    else:
        progress.close()
        xbmcgui.Dialog().ok("Error", "Failed to download repository. Check internet.")
        return

    # Step 2: Install each addon
    total = len(ADDONS)
    installed = 0
    failed = 0
    skipped = 0

    for i, (addon_id, zip_name) in enumerate(ADDONS):
        if progress.iscanceled():
            progress.close()
            return

        name = addon_id.split(".")[-1]
        pct = 5 + int(90 * (i + 1) / total)
        progress.update(pct, "%s (%d/%d) OK:%d Fail:%d" % (name, i+1, total, installed, failed))

        if is_installed(addon_id):
            log("%s already installed" % addon_id)
            skipped += 1
            continue

        zip_url = "%s/repo/zips/%s/%s" % (REPO_URL, addon_id, zip_name)
        local = xbmcvfs.translatePath("special://temp/%s" % zip_name)

        if download(zip_url, local):
            result = xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0",
                "method": "Addons.InstallAddon",
                "params": {"addonid": local},
                "id": 1
            }))
            log("Install RPC result: %s" % str(result)[:100])
            xbmc.sleep(3000)
            if is_installed(addon_id):
                log("%s OK" % addon_id)
                installed += 1
            else:
                log("%s install failed" % addon_id)
                failed += 1
        else:
            failed += 1

    progress.update(96, "Finalizing...")

    try:
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "method": "Addons.SetAddonEnabled",
            "params": {"addonid": "plugin.video.lordplayer", "enabled": True}, "id": 1
        }))
    except:
        pass

    _apply_skin_config()
    xbmc.executebuiltin("Skin.Set(skin.marmalade)")
    xbmc.sleep(2000)

    progress.update(100, "Done!")
    progress.close()
    xbmc.sleep(500)

    if failed > 0:
        xbmcgui.Dialog().ok("Marmalade Wizard",
                             "Installed: %d  Failed: %d  Skipped: %d" % (installed, failed, skipped))
    xbmc.executebuiltin("Notification(Marmalade Build, Done! Restarting..., 4000)")
    xbmc.sleep(4000)
    xbmc.executebuiltin("RestartApp()")

def _apply_skin_config():
    try:
        import shutil
        wizard_dir = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
        config_src = os.path.join(wizard_dir, "resources", "skinconfig")
        profile = xbmcvfs.translatePath("special://profile")

        for fname in ["guisettings.xml", "sources.xml", "favourites.xml", "profiles.xml"]:
            src = os.path.join(config_src, fname)
            dst = os.path.join(profile, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)

        skin_data = xbmcvfs.translatePath("special://profile/addon_data/skin.marmalade")
        os.makedirs(skin_data, exist_ok=True)
        src = os.path.join(config_src, "skin_settings.xml")
        dst = os.path.join(skin_data, "settings.xml")
        if os.path.exists(src):
            shutil.copy2(src, dst)

        shortcuts_data = xbmcvfs.translatePath("special://profile/addon_data/script.skinshortcuts")
        os.makedirs(shortcuts_data, exist_ok=True)
        sc_src = os.path.join(config_src, "skin_shortcuts")
        if os.path.isdir(sc_src):
            for fname in os.listdir(sc_src):
                src = os.path.join(sc_src, fname)
                dst = os.path.join(shortcuts_data, fname)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)

        hash_file = os.path.join(shortcuts_data, "skin.marmalade.hash")
        if os.path.exists(hash_file):
            os.remove(hash_file)
    except Exception as e:
        log("Config error: %s" % str(e))

if __name__ == "__main__":
    main()

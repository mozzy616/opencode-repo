import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import xbmcplugin
import sys
import os
import json
import urllib.request
import urllib.parse
import threading
import time

HANDLE = int(sys.argv[1])
ADDON = xbmcaddon.Addon()
REPO_URL = "https://mozzy616.github.io/opencode-repo"

ADDONS_TO_INSTALL = [
    # Core dependencies first
    "script.module.six",
    "script.module.kodi-six",
    "script.module.simplejson",
    "script.module.requests",
    "script.module.routing",
    "script.module.resolveurl",
    "script.module.cocoscrapers",
    "script.favourites",
    "script.skinshortcuts",
    "script.image.resource.select",
    "resource.images.studios.white",
    "resource.images.recordlabels.white",
    "resource.images.weatherfanart.single",
    "inputstream.adaptive",
    # Our addons
    "plugin.video.lordplayer",
    "plugin.video.streamlord",
    "plugin.video.xprime",
    "plugin.program.koditoolbox",
    # Skin last
    "skin.marmalade",
]

def log(msg):
    xbmc.log("[MarmaladeWizard] %s" % msg, xbmc.LOGINFO)

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MarmaladeWizard/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except:
        return None

def download_file(url, dest):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MarmaladeWizard/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            with open(dest, "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return True
    except Exception as e:
        log("Download error %s: %s" % (url, str(e)))
        return False

def install_addon_from_zip(zip_path):
    try:
        result = xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Addons.Install",
            "params": {"addonid": zip_path},
            "id": 1
        }))
        return result
    except:
        pass
    try:
        xbmc.executebuiltin("InstallAddon(%s)" % zip_path)
        return "ok"
    except:
        pass
    try:
        xbmc.executebuiltin("XBMC.InstallAddon(%s)" % zip_path)
        return "ok"
    except:
        return None

def is_addon_installed(addon_id):
    addon_path = xbmcvfs.translatePath("special://home/addons/%s" % addon_id)
    return os.path.exists(addon_path)

def get_addon_version(addon_id):
    try:
        addon = xbmcaddon.Addon(addon_id)
        return addon.getAddonInfo("version")
    except:
        return None

def main():
    if not xbmcgui.Dialog().yesno("Marmalade Wizard",
                                   "Install Marmalade Build?",
                                   "",
                                   "This installs: skin, StreamLord, XPrime,",
                                   "LordPlayer, Kodi Toolbox + dependencies.",
                                   "",
                                   "Repository: %s" % REPO_URL):
        return

    progress = xbmcgui.DialogProgress()
    progress.create("Marmalade Wizard", "Preparing installation...")

    # Step 1: Download and install repo addon
    progress.update(5, "Adding OpenCode Repository...")
    repo_zip = xbmcvfs.translatePath("special://temp/repository.opencode.zip")
    if download_file(REPO_URL + "/repository.opencode.zip", repo_zip):
        install_addon_from_zip(repo_zip)
        log("Repository installed")
    xbmc.sleep(1000)

    # Step 2: Install each addon
    total = len(ADDONS_TO_INSTALL)
    installed = 0
    failed = 0
    skipped = 0

    for i, addon_id in enumerate(ADDONS_TO_INSTALL):
        if progress.iscanceled():
            progress.close()
            xbmcgui.Dialog().ok("Marmalade Wizard", "Installation cancelled.")
            return

        pct = 5 + int(90 * (i + 1) / total)
        name = addon_id.replace("script.module.", "").replace("plugin.video.", "").replace("plugin.program.", "").replace("resource.images.", "").replace("skin.", "")
        progress.update(pct, "Installing: %s (%d/%d)" % (name, i+1, total),
                       "Installed: %d  Failed: %d  Skipped: %d" % (installed, failed, skipped))

        if is_addon_installed(addon_id):
            ver = get_addon_version(addon_id)
            log("%s already installed v%s" % (addon_id, ver or "?"))
            skipped += 1
            continue

        zip_url = "%s/%s.zip" % (REPO_URL, addon_id)
        local_zip = xbmcvfs.translatePath("special://temp/%s.zip" % addon_id)

        if download_file(zip_url, local_zip):
            result = install_addon_from_zip(local_zip)
            if result:
                log("%s installed successfully" % addon_id)
                installed += 1
                xbmc.sleep(500)
            else:
                log("%s install failed" % addon_id)
                failed += 1
        else:
            log("%s download failed" % addon_id)
            failed += 1

    progress.update(96, "Finalizing...")

    # Enable LordPlayer service
    try:
        xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0",
            "method": "Addons.SetAddonEnabled",
            "params": {"addonid": "plugin.video.lordplayer", "enabled": True},
            "id": 1
        }))
        log("LordPlayer enabled")
    except:
        pass

    # Apply skin settings and menu/widget config
    _apply_skin_config()

    # Set Marmalade Build as skin
    xbmc.executebuiltin("Skin.Set(skin.marmalade)")
    xbmc.sleep(2000)
    log("Skin set to Marmalade Build")

    progress.update(100, "Installation complete!")
    progress.close()
    xbmc.sleep(500)

    xbmcgui.Dialog().ok("Marmalade Wizard",
                         "Installation Complete!",
                         "",
                         "Installed: %d  Already: %d  Failed: %d" % (installed, skipped, failed),
                         "",
                         "Skin set to: Marmalade Build")

    if xbmcgui.Dialog().yesno("Restart Kodi?", "Restart now to apply changes?"):
        xbmc.executebuiltin("RestartApp()")

def _apply_skin_config():
    """Copy full configuration: guisettings, sources, favourites, skin settings, shortcuts."""
    try:
        import shutil
        wizard_dir = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
        config_src = os.path.join(wizard_dir, "resources", "skinconfig")

        profile = xbmcvfs.translatePath("special://profile")
        skin_data = xbmcvfs.translatePath("special://profile/addon_data/skin.marmalade")
        shortcuts_data = xbmcvfs.translatePath("special://profile/addon_data/script.skinshortcuts")

        # Core config files
        for fname in ["guisettings.xml", "sources.xml", "favourites.xml", "profiles.xml"]:
            src = os.path.join(config_src, fname)
            dst = os.path.join(profile, fname)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                log("Applied %s" % fname)

        # Skin settings
        os.makedirs(skin_data, exist_ok=True)
        src = os.path.join(config_src, "skin_settings.xml")
        dst = os.path.join(skin_data, "settings.xml")
        if os.path.exists(src):
            shutil.copy2(src, dst)
            log("Skin settings applied")

        # Skinshortcuts - all files
        os.makedirs(shortcuts_data, exist_ok=True)
        sc_src = os.path.join(config_src, "skin_shortcuts")
        if os.path.isdir(sc_src):
            for fname in os.listdir(sc_src):
                src = os.path.join(sc_src, fname)
                dst = os.path.join(shortcuts_data, fname)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
            log("Shortcuts config applied (%d files)" % len(os.listdir(sc_src)))

        # Remove hash so skin regenerates menu on next load
        hash_file = os.path.join(shortcuts_data, "skin.marmalade.hash")
        if os.path.exists(hash_file):
            os.remove(hash_file)

    except Exception as e:
        log("Config apply error: %s" % str(e))


if __name__ == "__main__":
    main()

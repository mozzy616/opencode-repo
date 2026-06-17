import xbmcgui
import xbmc
import xbmcvfs
import xbmcaddon
import xbmcplugin
import sys
import os
import json
import time
import re
import sqlite3
import shutil
import datetime
import threading
import urllib.request
import xml.etree.ElementTree as ET

HANDLE = int(sys.argv[1])
URL = sys.argv[0]
PARAMS = sys.argv[2]
ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
KODI_PATH = xbmcvfs.translatePath("special://home")
KODI_TEMP = xbmcvfs.translatePath("special://temp")
KODI_LOG = xbmcvfs.translatePath("special://logpath") + "kodi.log"

COLORS = {
    "red": "[COLOR red]",
    "green": "[COLOR green]",
    "blue": "[COLOR blue]",
    "yellow": "[COLOR yellow]",
    "orange": "[COLOR orange]",
    "cyan": "[COLOR cyan]",
    "white": "[COLOR white]",
    "end": "[/COLOR]",
}

def get_url(**kwargs):
    return "{0}?{1}".format(URL, urllib.parse.urlencode(kwargs))

def parse_params(p):
    params = {}
    if p and p.startswith("?"):
        p = p[1:]
    if p:
        for part in p.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = urllib.parse.unquote(v)
    return params

def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return "{:.1f} {}".format(n, unit)
        n /= 1024
    return "{:.1f} PB".format(n)

def dir_size(path):
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except:
                    pass
    except:
        pass
    return total

# ============================================================
#  MAIN MENU
# ============================================================
def show_menu():
    items = [
        ("[B]System Dashboard[/B]", "dashboard",
         "CPU, RAM, disk, Kodi health overview"),
        ("[B]Disk Cleaner[/B]", "cleaner",
         "Clean thumbnails, packages, cache, temp files"),
        ("[B]Log Viewer[/B]", "logs",
         "View, search & export kodi.log"),
        ("[B]Backup & Restore[/B]", "backup",
         "Backup/restore Kodi config"),
        ("[B]Addon Manager[/B]", "addons",
         "View sizes, enable/disable, find orphans"),
        ("[B]Network Tools[/B]", "network",
         "Speed test, connectivity check, DNS lookup"),
        ("[B]Database Tools[/B]", "database",
         "Vacuum, repair, view database stats"),
    ]
    for label, action, desc in items:
        li = xbmcgui.ListItem(label)
        li.setInfo("video", {"title": label, "plot": desc})
        li.setArt({"icon": "DefaultAddon.png"})
        xbmcplugin.addDirectoryItem(HANDLE, get_url(action=action), li, isFolder=True)
    xbmcplugin.endOfDirectory(HANDLE)

# ============================================================
#  DASHBOARD
# ============================================================
def dashboard():
    lines = []
    lines.append("=== KODI TOOLBOX DASHBOARD ===")
    lines.append("")

    # Uptime
    try:
        info = json.loads(xbmc.executeJSONRPC(
            '{"jsonrpc":"2.0","method":"XBMC.GetInfoLabels","params":{"labels":["System.Uptime","System.ScreenResolution","System.BuildVersion"]},"id":1}'))
        labels = info.get("result", {})
        uptime_sec = int(labels.get("System.Uptime", 0) or 0)
        h, m = divmod(uptime_sec // 60, 60)
        lines.append("  Uptime: %dh %dm" % (h, m))
        res = labels.get("System.ScreenResolution", "?")
        lines.append("  Resolution: %s" % res)
        ver = labels.get("System.BuildVersion", "?")
        lines.append("  Kodi Build: %s" % ver)
    except:
        pass

    # CPU
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        lines.append("")
        lines.append("  --- SYSTEM ---")
        lines.append("  CPU: %.1f%%" % cpu)
        lines.append("  RAM: %s / %s (%.1f%%)" % (
            fmt_size(mem.used), fmt_size(mem.total), mem.percent))
        disk = psutil.disk_usage(KODI_PATH)
        lines.append("  Disk: %s / %s (%.1f%%)" % (
            fmt_size(disk.used), fmt_size(disk.total), disk.percent))
    except:
        lines.append("")
        lines.append("  (Install psutil for CPU/RAM/Disk stats: pip install psutil)")

    # Kodi directories
    lines.append("")
    lines.append("  --- KODI DIRECTORIES ---")
    dirs = [
        ("Userdata", xbmcvfs.translatePath("special://userdata")),
        ("Addons", xbmcvfs.translatePath("special://home/addons")),
        ("Thumbnails", xbmcvfs.translatePath("special://thumbnails")),
        ("Temp", xbmcvfs.translatePath("special://temp")),
        ("Profile", xbmcvfs.translatePath("special://profile")),
        ("Database", xbmcvfs.translatePath("special://database")),
    ]
    for name, path in dirs:
        sz = dir_size(path)
        lines.append("  %s: %s" % (name, fmt_size(sz)))

    # Database sizes
    lines.append("")
    lines.append("  --- DATABASES ---")
    db_path = xbmcvfs.translatePath("special://database")
    if os.path.exists(db_path):
        for f in sorted(os.listdir(db_path)):
            if f.endswith(".db"):
                fpath = os.path.join(db_path, f)
                sz = os.path.getsize(fpath)
                lines.append("  %s (%s)" % (f, fmt_size(sz)))

    text = "\n".join(lines)
    xbmcgui.Dialog().textviewer("Kodi Dashboard", text)

# ============================================================
#  DISK CLEANER
# ============================================================
def cleaner_scan():
    items = []
    thumb_path = xbmcvfs.translatePath("special://thumbnails")
    temp_path = xbmcvfs.translatePath("special://temp")
    cache_path = os.path.join(xbmcvfs.translatePath("special://profile"), "cache")
    packages_path = xbmcvfs.translatePath("special://home/addons/packages")
    db_path = xbmcvfs.translatePath("special://database")

    # Thumbnails
    tsize = dir_size(thumb_path)
    items.append(("Thumbnails cache", thumb_path, tsize,
                   "Cached artwork images"))

    # Temp
    t2 = dir_size(temp_path)
    items.append(("Temp files", temp_path, t2,
                   "Temporary Kodi files"))

    # Cache
    if os.path.exists(cache_path):
        t3 = dir_size(cache_path)
        items.append(("Common cache", cache_path, t3,
                       "Addon cache files"))

    # Packages
    if os.path.exists(packages_path):
        t4 = dir_size(packages_path)
        items.append(("Addon packages", packages_path, t4,
                       "Downloaded addon packages"))

    # Texture DB
    tex_db = os.path.join(db_path, "Textures13.db")
    if os.path.exists(tex_db):
        t5 = os.path.getsize(tex_db)
        items.append(("Textures database", tex_db, t5,
                       "Texture cache database (will be recreated)"))

    return items

def cleaner():
    items = cleaner_scan()
    total = sum(i[2] for i in items)

    labels = []
    for name, path, sz, desc in items:
        labels.append("%s - %s" % (name, fmt_size(sz)))

    labels.append("[B]CLEAN ALL - %s[/B]" % fmt_size(total))
    labels.append("[B]Advanced: Custom Folder Clean[/B]")

    idx = xbmcgui.Dialog().select(
        "Disk Cleaner - %s total" % fmt_size(total), labels)

    if idx < 0:
        return

    if idx == len(items):
        # Clean all
        if xbmcgui.Dialog().yesno("Confirm", "Clean all items (%s)?" % fmt_size(total)):
            progress = xbmcgui.DialogProgress()
            progress.create("Kodi Toolbox", "Cleaning...")
            cleaned = 0
            for i, (name, path, sz, _) in enumerate(items):
                if progress.iscanceled():
                    break
                progress.update(int((i+1)*100/len(items)), "Cleaning %s..." % name)
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                        cleaned += sz
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        os.makedirs(path, exist_ok=True)
                        cleaned += sz
                except Exception as e:
                    xbmc.log("[Toolbox] Clean error %s: %s" % (name, str(e)), xbmc.LOGERROR)
            progress.close()
            xbmcgui.Dialog().notification("Kodi Toolbox", "Cleaned %s" % fmt_size(cleaned),
                                         xbmcgui.NOTIFICATION_INFO, 5000)

    elif idx == len(items) + 1:
        # Custom folder
        folder = xbmcgui.Dialog().browse(0, "Select folder to clean", "files", "", False, True, KODI_PATH)
        if folder and xbmcgui.Dialog().yesno("Confirm", "Delete all contents of:\n%s ?" % folder):
            try:
                shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)
                xbmcgui.Dialog().notification("Kodi Toolbox", "Folder cleaned", xbmcgui.NOTIFICATION_INFO, 3000)
            except Exception as e:
                xbmcgui.Dialog().ok("Error", str(e))

    else:
        # Single item
        name, path, sz, _ = items[idx]
        if xbmcgui.Dialog().yesno("Confirm", "Delete %s (%s)?" % (name, fmt_size(sz))):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    os.makedirs(path, exist_ok=True)
                xbmcgui.Dialog().notification("Kodi Toolbox", "%s cleaned" % name,
                                             xbmcgui.NOTIFICATION_INFO, 3000)
            except Exception as e:
                xbmcgui.Dialog().ok("Error", str(e))

# ============================================================
#  LOG VIEWER
# ============================================================
LOG_COLORS = {
    "FATAL": COLORS["red"] + "[B]",
    "ERROR": COLORS["red"],
    "WARNING": COLORS["orange"],
    "INFO": COLORS["white"],
    "DEBUG": COLORS["white"],
}

def log_viewer(search=None, tail=500):
    try:
        with open(KODI_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except:
        xbmcgui.Dialog().ok("Error", "Cannot read kodi.log")
        return

    if search:
        search_lower = search.lower()
        lines = [l for l in lines if search_lower in l.lower()]

    lines = lines[-tail:]

    tail_lines = []
    try:
        with open(KODI_LOG, "r", encoding="utf-8", errors="replace") as f:
            tail_lines = f.readlines()[-tail:]
    except:
        pass
    output = []
    for line in tail_lines:
        output.append(line.rstrip())

    text = "\n".join(output)
    menu = [
        "View last 200 lines",
        "View last 500 lines",
        "View last 1000 lines",
        "Search log...",
        "Export full log to desktop",
    ]

    while True:
        idx = xbmcgui.Dialog().select(
            "Log Viewer - %d lines" % len(lines), menu)
        if idx < 0:
            break
        elif idx == 0:
            xbmcgui.Dialog().textviewer("Kodi Log",
                "\n".join([l.rstrip() for l in lines[-200:]]))
        elif idx == 1:
            xbmcgui.Dialog().textviewer("Kodi Log", text)
        elif idx == 2:
            out = "\n".join([l.rstrip() for l in tail_lines[-1000:]])
            xbmcgui.Dialog().textviewer("Kodi Log", out)
        elif idx == 3:
            kb = xbmcgui.Dialog().input("Search kodi.log:")
            if kb:
                log_viewer(search=kb)
                break
        elif idx == 4:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop", "kodi_export.log")
            try:
                shutil.copy2(KODI_LOG, desktop)
                xbmcgui.Dialog().notification("Kodi Toolbox", "Exported to Desktop\\kodi_export.log",
                                             xbmcgui.NOTIFICATION_INFO, 5000)
            except Exception as e:
                xbmcgui.Dialog().ok("Error", str(e))
        break

# ============================================================
#  BACKUP & RESTORE
# ============================================================
def backup_restore():
    menu = [
        "Backup Kodi configuration",
        "Restore from backup",
        "View backups",
    ]
    backup_dir = os.path.join(PROFILE_PATH, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    idx = xbmcgui.Dialog().select("Backup & Restore", menu)
    if idx < 0:
        return

    if idx == 0:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = xbmcgui.Dialog().input("Backup name:", defaultt=ts)
        if not name:
            return
        dest = os.path.join(backup_dir, name)
        os.makedirs(dest, exist_ok=True)

        sources = [
            ("userdata", xbmcvfs.translatePath("special://userdata")),
            ("addons", xbmcvfs.translatePath("special://home/addons")),
            ("addon_data", xbmcvfs.translatePath("special://profile")),
        ]

        # Exclude these from addons
        exclude = {"packages", "__pycache__", "backups"}

        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Toolbox", "Creating backup...")
        total_items = 0
        copied = 0

        for sname, spath in sources:
            if progress.iscanceled():
                break
            dest_sub = os.path.join(dest, sname)
            os.makedirs(dest_sub, exist_ok=True)
            try:
                for item in os.listdir(spath):
                    if item in exclude:
                        continue
                    src_item = os.path.join(spath, item)
                    dst_item = os.path.join(dest_sub, item)
                    try:
                        if os.path.isdir(src_item):
                            shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
                        else:
                            shutil.copy2(src_item, dst_item)
                        copied += 1
                    except:
                        pass
                progress.update(int(copied * 100 / max(total_items or 100, 1)),
                               "Backing up %s..." % sname)
            except:
                pass

        progress.close()

        # Save metadata
        meta = {"date": ts, "name": name, "kodi_version": xbmc.getInfoLabel("System.BuildVersion")}
        with open(os.path.join(dest, "backup.json"), "w") as f:
            json.dump(meta, f)

        total_sz = dir_size(dest)
        xbmcgui.Dialog().notification("Kodi Toolbox",
                                     "Backup created: %s (%s)" % (name, fmt_size(total_sz)),
                                     xbmcgui.NOTIFICATION_INFO, 6000)

    elif idx == 1:
        backups = sorted(os.listdir(backup_dir), reverse=True)
        if not backups:
            xbmcgui.Dialog().ok("Backup", "No backups found")
            return
        pick = xbmcgui.Dialog().select("Restore from backup", backups)
        if pick < 0:
            return
        if not xbmcgui.Dialog().yesno("Confirm Restore",
                                       "Restore '%s'?\nThis will overwrite current config!\nKodi should be restarted after restore." % backups[pick]):
            return
        src = os.path.join(backup_dir, backups[pick])
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Toolbox", "Restoring...")
        for sname in ["userdata", "addons", "addon_data"]:
            ssrc = os.path.join(src, sname)
            if os.path.exists(ssrc):
                if sname == "userdata":
                    target = xbmcvfs.translatePath("special://userdata")
                elif sname == "addons":
                    target = xbmcvfs.translatePath("special://home/addons")
                else:
                    target = xbmcvfs.translatePath("special://profile")
                try:
                    if os.path.isdir(target):
                        shutil.rmtree(target)
                    shutil.copytree(ssrc, target, dirs_exist_ok=True)
                except Exception as e:
                    xbmcgui.Dialog().ok("Restore Error", "%s: %s" % (sname, str(e)))
                progress.update(50, "Restored %s" % sname)
        progress.close()
        xbmcgui.Dialog().ok("Restore Complete",
                           "Configuration restored.\nPlease restart Kodi for changes to take effect.")

    elif idx == 2:
        backups = sorted(os.listdir(backup_dir), reverse=True)
        if not backups:
            xbmcgui.Dialog().ok("Backup", "No backups found")
            return
        lines = []
        for b in backups:
            bpath = os.path.join(backup_dir, b)
            sz = dir_size(bpath)
            meta_file = os.path.join(bpath, "backup.json")
            meta = {}
            if os.path.exists(meta_file):
                try:
                    with open(meta_file) as f:
                        meta = json.load(f)
                except:
                    pass
            date = meta.get("date", "?")
            lines.append("%s - %s (%s)" % (date, b, fmt_size(sz)))
        xbmcgui.Dialog().textviewer("Backups", "\n".join(lines))

# ============================================================
#  ADDON MANAGER
# ============================================================
def addon_manager():
    addons_path = xbmcvfs.translatePath("special://home/addons")
    db_path = xbmcvfs.translatePath("special://database")
    addon_db = os.path.join(db_path, "Addons33.db")

    menu = [
        "View all addons with sizes",
        "View orphan addon data",
        "View addon database info",
    ]
    idx = xbmcgui.Dialog().select("Addon Manager", menu)
    if idx < 0:
        return

    if idx == 0:
        # List addons with sizes
        items = []
        for adir in sorted(os.listdir(addons_path)):
            apath = os.path.join(addons_path, adir)
            if os.path.isdir(apath):
                sz = dir_size(apath)
                items.append((adir, sz))
        items.sort(key=lambda x: -x[1])
        lines = []
        lines.append(COLORS["cyan"] + "[B]Addons by size:[/B]" + COLORS["end"])
        lines.append("")
        total = 0
        for name, sz in items[:100]:
            size_str = fmt_size(sz)
            lines.append("  %s - %s" % (size_str, name))
            total += sz
        lines.append("")
        lines.append("Total: %s across %d addons" % (fmt_size(total), len(items)))
        xbmcgui.Dialog().textviewer("Addon Sizes", "\n".join(lines))

    elif idx == 1:
        # Orphan addon data
        addon_data = xbmcvfs.translatePath("special://profile")
        orphans = []
        for ad in sorted(os.listdir(addon_data)):
            adpath = os.path.join(addon_data, ad)
            if not os.path.isdir(adpath):
                continue
            addon_dir = os.path.join(addons_path, ad)
            if not os.path.exists(addon_dir):
                sz = dir_size(adpath)
                orphans.append((ad, sz))

        if not orphans:
            xbmcgui.Dialog().ok("Addon Data", "No orphan data found.")
            return

        labels = []
        for name, sz in orphans:
            labels.append("%s - %s" % (name, fmt_size(sz)))
        labels.append("[B]DELETE ALL ORPHAN DATA[/B]")

        pick = xbmcgui.Dialog().select("Orphan Addon Data (%d items)" % len(orphans), labels)
        if pick < 0:
            return
        if pick == len(orphans):
            if xbmcgui.Dialog().yesno("Confirm", "Delete all orphan addon data?"):
                for name, _ in orphans:
                    try:
                        shutil.rmtree(os.path.join(addon_data, name))
                    except:
                        pass
                xbmcgui.Dialog().notification("Kodi Toolbox", "Orphan data cleaned",
                                             xbmcgui.NOTIFICATION_INFO, 3000)
        else:
            name, _ = orphans[pick]
            if xbmcgui.Dialog().yesno("Confirm", "Delete data for %s?" % name):
                try:
                    shutil.rmtree(os.path.join(addon_data, name))
                    xbmcgui.Dialog().notification("Kodi Toolbox", "%s data deleted" % name,
                                                 xbmcgui.NOTIFICATION_INFO, 3000)
                except Exception as e:
                    xbmcgui.Dialog().ok("Error", str(e))

    elif idx == 2:
        if os.path.exists(addon_db):
            try:
                conn = sqlite3.connect(addon_db)
                c = conn.cursor()
                c.execute("SELECT addonID, enabled FROM installed ORDER BY addonID")
                rows = c.fetchall()
                enabled = sum(1 for r in rows if r[1])
                disabled = len(rows) - enabled
                conn.close()
                lines = [
                    "Addons Database: Addons33.db",
                    "Size: %s" % fmt_size(os.path.getsize(addon_db)),
                    "Total installed: %d" % len(rows),
                    "Enabled: %d" % enabled,
                    "Disabled: %d" % disabled,
                ]
                xbmcgui.Dialog().textviewer("Addon Database", "\n".join(lines))
            except Exception as e:
                xbmcgui.Dialog().ok("Error", str(e))
        else:
            xbmcgui.Dialog().ok("Error", "Addons33.db not found")

# ============================================================
#  NETWORK TOOLS
# ============================================================
def network_tools():
    menu = [
        "Internet connectivity test",
        "Resolve hostnames",
        "View network interfaces",
    ]
    idx = xbmcgui.Dialog().select("Network Tools", menu)
    if idx < 0:
        return

    if idx == 0:
        # Connectivity test
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Toolbox", "Testing connectivity...")
        results = []
        test_urls = [
            ("Google DNS", "http://8.8.8.8"),
            ("Cloudflare DNS", "http://1.1.1.1"),
            ("google.com", "https://www.google.com"),
            ("github.com", "https://github.com"),
            ("TMDB API", "https://api.themoviedb.org"),
            ("IMDB", "https://www.imdb.com"),
            ("Torrent (apibay)", "https://apibay.org"),
            ("Torrest (local)", "http://127.0.0.1:61235"),
        ]
        for i, (name, url) in enumerate(test_urls):
            if progress.iscanceled():
                break
            progress.update(int((i+1)*100/len(test_urls)), "Testing %s..." % name)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Kodi-Toolbox"})
                start = time.time()
                with urllib.request.urlopen(req, timeout=5) as r:
                    elapsed = (time.time() - start) * 1000
                    results.append(("  OK   %s (%dms)" % (name, elapsed), True))
            except Exception as e:
                results.append(("  FAIL %s (%s)" % (name, str(e)[:50]), False))
        progress.close()
        passed = sum(1 for r in results if r[1])
        lines = ["Connectivity Test: %d/%d passed\n" % (passed, len(results))]
        lines.extend([r[0] for r in results])
        xbmcgui.Dialog().textviewer("Network Test", "\n".join(lines))

    elif idx == 1:
        hosts = xbmcgui.Dialog().input("Enter hostnames (comma-separated):",
                                       defaultt="google.com,youtube.com,github.com,reddit.com")
        if not hosts:
            return
        results = []
        for host in hosts.split(","):
            host = host.strip()
            if not host:
                continue
            try:
                import socket
                ips = socket.getaddrinfo(host, 80)
                ip = ips[0][4][0] if ips else "?"
                results.append("  %s -> %s" % (host, ip))
            except Exception as e:
                results.append("  %s (FAILED: %s)" % (host, str(e)[:40]))
        xbmcgui.Dialog().textviewer("DNS Resolve", "\n".join(results))

    elif idx == 2:
        try:
            import socket
            hostname = socket.gethostname()
            ips = socket.gethostbyname_ex(hostname)
            lines = [
                "Hostname: %s" % hostname,
                "IP: %s" % ips[2][0] if ips[2] else "?",
                "",
                "All IPs: %s" % ", ".join(ips[2]),
            ]
            xbmcgui.Dialog().textviewer("Network Info", "\n".join(lines))
        except Exception as e:
            xbmcgui.Dialog().ok("Error", str(e))

# ============================================================
#  DATABASE TOOLS
# ============================================================
def database_tools():
    db_path = xbmcvfs.translatePath("special://database")
    dbs = sorted([f for f in os.listdir(db_path) if f.endswith(".db")],
                 key=lambda f: os.path.getsize(os.path.join(db_path, f)), reverse=True)

    labels = []
    for db in dbs:
        fp = os.path.join(db_path, db)
        labels.append("%s (%s)" % (db, fmt_size(os.path.getsize(fp))))
    labels.append("[B]VACUUM ALL DATABASES[/B]")

    idx = xbmcgui.Dialog().select("Database Tools - %d databases" % len(dbs), labels)
    if idx < 0:
        return

    if idx == len(dbs):
        if not xbmcgui.Dialog().yesno("Confirm", "VACUUM all databases?\nThis optimizes storage but may take time."):
            return
        progress = xbmcgui.DialogProgress()
        progress.create("Kodi Toolbox", "Vacuuming databases...")
        for i, db in enumerate(dbs):
            if progress.iscanceled():
                break
            progress.update(int((i+1)*100/len(dbs)), "Vacuuming %s..." % db)
            fp = os.path.join(db_path, db)
            try:
                before = os.path.getsize(fp)
                conn = sqlite3.connect(fp)
                conn.execute("VACUUM")
                conn.close()
                after = os.path.getsize(fp)
                xbmc.log("[Toolbox] Vacuumed %s: %s -> %s" % (db, fmt_size(before), fmt_size(after)), xbmc.LOGINFO)
            except Exception as e:
                xbmc.log("[Toolbox] Vacuum error %s: %s" % (db, str(e)), xbmc.LOGERROR)
        progress.close()
        xbmcgui.Dialog().notification("Kodi Toolbox", "Database vacuum complete",
                                     xbmcgui.NOTIFICATION_INFO, 4000)

    else:
        db = dbs[idx]
        fp = os.path.join(db_path, db)
        actions = [
            "View tables",
            "VACUUM database",
            "Delete database",
        ]
        a = xbmcgui.Dialog().select(db, actions)
        if a < 0:
            return

        if a == 0:
            try:
                conn = sqlite3.connect(fp)
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = c.fetchall()
                lines = ["%s (%s)" % (db, fmt_size(os.path.getsize(fp))), "",
                         "Tables:"]
                for t in tables:
                    try:
                        c2 = conn.cursor()
                        c2.execute("SELECT COUNT(*) FROM [%s]" % t[0])
                        count = c2.fetchone()[0]
                        lines.append("  %s: %d rows" % (t[0], count))
                    except:
                        lines.append("  %s" % t[0])
                conn.close()
                xbmcgui.Dialog().textviewer("Database: %s" % db, "\n".join(lines))
            except Exception as e:
                xbmcgui.Dialog().ok("Error", str(e))

        elif a == 1:
            if not xbmcgui.Dialog().yesno("Confirm", "VACUUM %s?" % db):
                return
            try:
                before = os.path.getsize(fp)
                conn = sqlite3.connect(fp)
                conn.execute("VACUUM")
                conn.close()
                after = os.path.getsize(fp)
                xbmcgui.Dialog().notification("Kodi Toolbox",
                                             "Vacuumed: %s -> %s" % (fmt_size(before), fmt_size(after)),
                                             xbmcgui.NOTIFICATION_INFO, 5000)
            except Exception as e:
                xbmcgui.Dialog().ok("Error", str(e))

        elif a == 2:
            if xbmcgui.Dialog().yesno("WARNING", "Delete %s?\nThis cannot be undone!" % db):
                try:
                    os.remove(fp)
                    xbmcgui.Dialog().notification("Kodi Toolbox", "%s deleted" % db,
                                                 xbmcgui.NOTIFICATION_WARNING, 5000)
                except Exception as e:
                    xbmcgui.Dialog().ok("Error", str(e))

# ============================================================
#  MAIN
# ============================================================
def main():
    p = parse_params(PARAMS)
    action = p.get("action", "")

    if action == "dashboard":
        dashboard()
    elif action == "cleaner":
        cleaner()
    elif action == "logs":
        log_viewer()
    elif action == "backup":
        backup_restore()
    elif action == "addons":
        addon_manager()
    elif action == "network":
        network_tools()
    elif action == "database":
        database_tools()
    else:
        show_menu()

if __name__ == "__main__":
    main()

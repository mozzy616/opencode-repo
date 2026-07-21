import sys
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from resources.lib.constants import ADDON_ID, ADDON_NAME, LOG_PREFIX

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def addon():
    return xbmcaddon.Addon(ADDON_ID)


def get_setting(key, default=""):
    val = addon().getSetting(key)
    if val is None or val == "":
        return default
    return val


def set_setting(key, value):
    addon().setSetting(key, str(value))


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("%s %s" % (LOG_PREFIX, msg), level)


def notify(title, message, icon=xbmcgui.NOTIFICATION_INFO, duration=3000):
    xbmcgui.Dialog().notification(title, message, icon, duration)


def dialog_ok(heading, message):
    xbmcgui.Dialog().ok(heading, message)


def dialog_yesno(heading, message):
    return xbmcgui.Dialog().yesno(heading, message)


def dialog_select(heading, options):
    return xbmcgui.Dialog().select(heading, options)


def dialog_progress():
    return xbmcgui.DialogProgress()


def keyboard_input(heading="", default=""):
    kb = xbmc.Keyboard(default, heading)
    kb.doModal()
    if kb.isConfirmed() and kb.getText():
        return kb.getText().strip()
    return ""


def build_url(**kwargs):
    return "%s?%s" % (BASE_URL, urllib.parse.urlencode(kwargs))


def parse_params(param_string):
    params = {}
    if param_string:
        if param_string.startswith("?"):
            param_string = param_string[1:]
        for part in param_string.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = urllib.parse.unquote(v)
    return params


def add_list_item(url, li, is_folder=True):
    xbmcplugin.addDirectoryItem(HANDLE, url, li, is_folder)


def end_directory(cache_to_disc=True, update_listing=False):
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache_to_disc, updateListing=update_listing)


def set_content(content_type):
    xbmcplugin.setContent(HANDLE, content_type)


def set_plugin_fanart(url):
    if url:
        xbmcplugin.setPluginFanart(HANDLE, url)


def set_resolved_url(succeeded, li):
    xbmcplugin.setResolvedUrl(HANDLE, succeeded, li)


def translate_path(path):
    return xbmcvfs.translatePath(path)


def get_addon_info(key):
    return addon().getAddonInfo(key)


def get_localized_string(string_id):
    return addon().getLocalizedString(string_id)

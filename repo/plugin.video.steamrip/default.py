import sys
import os
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

PLUGIN_URL = sys.argv[0]
PLUGIN_HANDLE = int(sys.argv[1])
PLUGIN_ARGS = dict(parse_qsl(sys.argv[2].lstrip("?")))

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))

RESOURCES_PATH = os.path.join(ADDON_PATH, "resources")
LIB_PATH = os.path.join(RESOURCES_PATH, "lib")
sys.path.insert(0, LIB_PATH)

import scraper
import scraper as steamrip

_pluginhandle = PLUGIN_HANDLE
_baseurl = PLUGIN_URL


def _addon_url(**kwargs):
    return "{}?{}".format(_baseurl, urlencode(kwargs))


def _add_dir(name, url, mode, icon="", fanart="", info=None, isfolder=True):
    li = xbmcgui.ListItem(name)
    li.setArt({
        "icon": icon or "DefaultVideo.png",
        "thumb": icon or "DefaultVideo.png",
        "poster": icon or "DefaultVideo.png",
        "fanart": fanart or os.path.join(ADDON_PATH, "fanart.jpg"),
    })
    if info:
        li.setInfo("video", info)
    u = _addon_url(mode=mode, url=url)
    xbmcplugin.addDirectoryItem(
        handle=_pluginhandle, url=u, listitem=li, isFolder=isfolder
    )


def _add_game_entry(title, url, thumb, fanart, size, year, genre, plot):
    li = xbmcgui.ListItem(title)
    li.setArt({
        "icon": thumb,
        "thumb": thumb,
        "poster": thumb,
        "fanart": fanart,
    })
    li.setInfo("video", {
        "title": title,
        "plot": plot or "",
        "year": int(year) if year else 0,
        "genre": genre or "",
        "size": size,
        "mediatype": "video",
    })
    li.setProperty("IsPlayable", "false")
    u = _addon_url(mode="game_details", url=url)
    xbmcplugin.addDirectoryItem(
        handle=_pluginhandle, url=u, listitem=li, isFolder=True
    )


def _add_download_entry(label, url, thumb=""):
    li = xbmcgui.ListItem(label)
    li.setArt({"icon": "DefaultVideo.png", "thumb": thumb or "DefaultVideo.png"})
    li.setInfo("video", {"title": label, "mediatype": "video"})
    li.setProperty("IsPlayable", "false")
    u = _addon_url(mode="open_browser", url=url)
    xbmcplugin.addDirectoryItem(
        handle=_pluginhandle, url=u, listitem=li, isFolder=False
    )


def _add_pagination(mode, url="", page=1):
    if page > 1:
        prev_url = _addon_url(mode=mode, url=url, page=page - 1)
        li = xbmcgui.ListItem("<< Previous Page")
        li.setArt({"icon": "DefaultVideo.png"})
        xbmcplugin.addDirectoryItem(
            handle=_pluginhandle, url=prev_url, listitem=li, isFolder=True
        )
    next_url = _addon_url(mode=mode, url=url, page=page + 1)
    li = xbmcgui.ListItem("Next Page >>")
    li.setArt({"icon": "DefaultVideo.png"})
    xbmcplugin.addDirectoryItem(
        handle=_pluginhandle, url=next_url, listitem=li, isFolder=True
    )


def _build_game_plot(details):
    parts = []
    if details.get("genre"):
        parts.append("[B]Genre:[/B] {}".format(details["genre"]))
    if details.get("developer"):
        parts.append("[B]Developer:[/B] {}".format(details["developer"]))
    if details.get("size"):
        parts.append("[B]Size:[/B] {}".format(details["size"]))
    if details.get("version"):
        parts.append("[B]Version:[/B] {}".format(details["version"]))
    if details.get("platform"):
        parts.append("[B]Platform:[/B] {}".format(details["platform"]))
    if details.get("system_requirements"):
        parts.append("\n[B]System Requirements:[/B]\n{}".format(details["system_requirements"]))
    if details.get("description"):
        parts.append("\n{}".format(details["description"][:500]))
    return "\n".join(parts)


def list_main_menu():
    fanart = os.path.join(ADDON_PATH, "fanart.jpg")

    _add_dir("Popular Games", "", "popular", fanart=fanart)
    _add_dir("Top Games", "", "top", fanart=fanart)
    _add_dir("Recently Added", "", "recent", fanart=fanart)
    _add_dir("All Games (A-Z)", "", "all_games", fanart=fanart)
    _add_dir("Categories", "", "categories", fanart=fanart)
    _add_dir("Search", "", "search_prompt", fanart=fanart)

    xbmcplugin.endOfDirectory(_pluginhandle)


def list_categories():
    for name, slug in steamrip.CATEGORIES:
        _add_dir(
            name,
            slug,
            "category",
            info={"genre": name},
        )
    xbmcplugin.endOfDirectory(_pluginhandle)


def list_games(mode, url="", page=1):
    page = int(page)

    if mode == "popular":
        games, has_next = steamrip.get_popular_games(page)
    elif mode == "top":
        games, has_next = steamrip.get_top_games(page)
    elif mode == "recent":
        games, has_next = steamrip.get_recent_updates(page)
    elif mode == "category":
        games, has_next = steamrip.get_category_games(url, page)
    elif mode == "search":
        games, has_next = steamrip.search_games(url)
    elif mode == "all_games":
        games, has_next = steamrip.get_all_games(page)
    else:
        games, has_next = [], False

    for g in games:
        size_str = "[{}] ".format(g["size"]) if g["size"] else ""
        title = "{}{} ({})".format(size_str, g["title"], g["year"]) if g["year"] else "{}{}".format(size_str, g["title"])

        cats = g.get("categories", [])
        genre = cats[0] if cats else ""

        _add_game_entry(
            title=title,
            url=g["url"],
            thumb=g["thumb"],
            fanart=os.path.join(ADDON_PATH, "fanart.jpg"),
            size=g.get("size", ""),
            year=g.get("year", ""),
            genre=genre,
            plot=" ".join(cats),
        )

    _add_pagination(mode, url, page)
    xbmcplugin.endOfDirectory(_pluginhandle)


def show_game_details(url):
    xbmc.log("SteamRIP: Loading details for {}".format(url), xbmc.LOGINFO)
    details = steamrip.get_game_details(url)

    if not details:
        xbmcgui.Dialog().notification(ADDON_NAME, "Failed to load game details")
        xbmcplugin.endOfDirectory(_pluginhandle)
        return

    title = details.get("title", "Unknown")
    fanart = details.get("fanart", "")
    poster = details.get("poster", fanart)
    plot = _build_game_plot(details)

    download_links = details.get("download_links", [])

    if not download_links:
        xbmcgui.Dialog().notification(ADDON_NAME, "No download links found", "")
        xbmcplugin.endOfDirectory(_pluginhandle)
        return

    for dl in download_links:
        li = xbmcgui.ListItem(dl.get("label", "Download"))
        li.setArt({
            "icon": poster or "DefaultVideo.png",
            "thumb": poster or "DefaultVideo.png",
            "fanart": fanart,
        })
        li.setInfo("video", {
            "title": dl.get("label", "Download"),
            "plot": plot,
            "genre": details.get("genre", ""),
            "mediatype": "video",
        })
        li.setProperty("IsPlayable", "false")
        u = _addon_url(mode="open_browser", url=dl["url"])
        xbmcplugin.addDirectoryItem(handle=_pluginhandle, url=u, listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(_pluginhandle)


def show_downloads(url):
    show_game_details(url)


def show_screenshots(url):
    details = steamrip.get_game_details(url)
    fanart = details.get("fanart", "")

    screenshots = details.get("screenshots", [])
    for i, ss in enumerate(screenshots):
        li = xbmcgui.ListItem("Screenshot {}".format(i + 1))
        li.setArt({"icon": ss, "thumb": ss, "fanart": fanart})
        li.setInfo("video", {"title": "Screenshot {}".format(i + 1)})
        li.setProperty("IsPlayable", "false")
        xbmcplugin.addDirectoryItem(
            handle=_pluginhandle, url=ss, listitem=li, isFolder=False
        )

    xbmcplugin.endOfDirectory(_pluginhandle)


def show_sysreq(url):
    details = steamrip.get_game_details(url)
    sys_req = details.get("system_requirements", "")

    text_viewer = xbmcgui.Dialog()
    text_viewer.textviewer("System Requirements - {}".format(details.get("title", "")), sys_req)
    xbmcplugin.endOfDirectory(_pluginhandle)
    return


def search():
    kb = xbmc.Keyboard("", "Search SteamRIP")
    kb.doModal()
    if kb.isConfirmed():
        query = kb.getText()
        if query:
            list_games("search", query, 1)
        else:
            list_main_menu()
    else:
        list_main_menu()


def router():
    mode = PLUGIN_ARGS.get("mode", "main")
    url = PLUGIN_ARGS.get("url", "")
    page = PLUGIN_ARGS.get("page", "1")
    xbmc.log("SteamRIP: Router mode={} url={} page={}".format(mode, url[:80] if url else "", page), xbmc.LOGINFO)

    if mode == "main":
        list_main_menu()
    elif mode == "categories":
        list_categories()
    elif mode in ("popular", "top", "recent", "category", "all_games"):
        list_games(mode, url, page)
    elif mode == "search":
        list_games("search", url, page)
    elif mode == "search_prompt":
        search()
    elif mode == "game_details":
        show_game_details(url)
    elif mode == "show_downloads":
        show_downloads(url)
    elif mode == "show_screenshots":
        show_screenshots(url)
    elif mode == "show_sysreq":
        show_sysreq(url)
    elif mode == "open_browser":
        import webbrowser
        webbrowser.open(url)
    else:
        list_main_menu()


if __name__ == "__main__":
    router()

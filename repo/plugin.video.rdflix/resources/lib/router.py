import sys

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import parse_params, log, dialog_ok, set_setting, notify, end_directory, set_resolved_url
from resources.lib.menus import (
    main_menu, movies_menu, tvshows_menu, movies_genres, tv_genres,
    movies_list, tv_list, movie_detail_view, tv_detail_view,
    season_episodes_view, search_view, account_view, rd_torrents_view,
    continue_watching_view, analytics_view, surprise_me_view, watch_stats_view,
    for_you_view, speed_test_view, trakt_watchlist_view, person_detail_view,
    sports_search_view, livetv_menu, livetv_channels_view, livetv_play,
)
from resources.lib.player import play_movie, play_episode
from resources.lib.rd_api import get_device_code, poll_device_auth, get_user


def device_auth():
    device_code, user_code, verify_url = get_device_code()
    if not device_code:
        dialog_ok("RDFlix", "Failed to get device code. Check connection.")
        return

    dialog_ok("RDFlix", "Go to this URL and enter code:\n\n%s\n\nCode: %s" % (verify_url, user_code))
    notify("RDFlix", "Authorizing device...")

    client_id, client_secret = poll_device_auth(device_code)
    if client_id and client_secret:
        set_setting("rd_token", client_id)
        notify("RDFlix", "Device authorized successfully!")
        user = get_user()
        if user:
            notify("RDFlix", "Logged in as: %s" % user.get("username", "Unknown"))
    else:
        dialog_ok("RDFlix", "Device authorization failed or timed out.")


def router(param_string):
    params = parse_params(param_string)
    action = params.get("action", "")

    log("Action: %s Params: %s" % (action, str(params)))

    if not action:
        main_menu()

    elif action == "movies_menu":
        movies_menu()

    elif action == "tvshows_menu":
        tvshows_menu()

    elif action == "movies_genres":
        movies_genres()

    elif action == "tv_genres":
        tv_genres()

    elif action == "movies_list":
        movies_list(
            category=params.get("category", "trending"),
            genre_id=params.get("genre_id", ""),
            page=params.get("page", "1"),
        )

    elif action == "tv_list":
        tv_list(
            category=params.get("category", "trending"),
            genre_id=params.get("genre_id", ""),
            page=params.get("page", "1"),
        )

    elif action == "movie_detail":
        movie_detail_view(
            tmdb_id=params.get("tmdb_id", ""),
            title=params.get("title", ""),
        )

    elif action == "tv_detail":
        tv_detail_view(
            tmdb_id=params.get("tmdb_id", ""),
            title=params.get("title", ""),
        )

    elif action == "season_episodes":
        season_episodes_view(
            tmdb_id=params.get("tmdb_id", ""),
            season=params.get("season", "1"),
            show_title=params.get("show_title", ""),
            imdb_id=params.get("imdb_id", ""),
        )

    elif action == "search":
        search_view(query=params.get("query", ""))

    elif action == "account":
        account_view()

    elif action == "rd_torrents":
        rd_torrents_view()

    elif action == "continue_watching":
        continue_watching_view()

    elif action == "surprise_me":
        surprise_me_view()

    elif action == "watch_stats":
        watch_stats_view()

    elif action == "for_you":
        for_you_view()

    elif action == "speed_test":
        speed_test_view()

    elif action == "trakt_watchlist":
        trakt_watchlist_view()

    elif action == "person_detail":
        person_detail_view(params.get("person_id", ""), params.get("person_name", ""))

    elif action == "sports_search":
        sports_search_view(params.get("query", ""))

    elif action == "livetv":
        livetv_menu()

    elif action == "livetv_channels":
        livetv_channels_view(params.get("group", "__all__"))

    elif action == "livetv_play":
        livetv_play(params.get("url", ""), params.get("title", ""))

    elif action == "open_magnet":
        from resources.lib.kodi_utils import keyboard_input, dialog_select, dialog_ok, set_resolved_url, end_directory, translate_path, notify, get_setting
        from resources.lib.rd_api import resolve_magnet
        import re, xbmcgui
        magnet = keyboard_input("Paste a magnet link or info hash...")
        if not magnet:
            end_directory()
        else:
            magnet = magnet.strip()
            if not magnet.startswith("magnet:") and len(magnet) == 40 and re.match(r'^[a-fA-F0-9]{40}$', magnet):
                magnet = "magnet:?xt=urn:btih:%s" % magnet
            choice = dialog_select("Open Magnet", ["Play", "Download"])
            if choice == 0:
                result = resolve_magnet(magnet, "Direct Magnet")
                if result and result.get("url"):
                    li = xbmcgui.ListItem(path=result["url"], label=result.get("filename", "video"))
                    li.setProperty("IsPlayable", "true")
                    set_resolved_url(True, li)
                else:
                    dialog_ok("RDFlix", "Could not resolve magnet through RD")
                    set_resolved_url(False, xbmcgui.ListItem(label="Magnet"))
            elif choice == 1:
                result = resolve_magnet(magnet, "Direct Magnet")
                if result and result.get("url"):
                    dest = translate_path(get_setting("download_path", "special://home/userdata/downloads/"))
                    import os
                    os.makedirs(dest, exist_ok=True)
                    fname = result.get("filename", "download.mp4")
                    from resources.lib.player import _do_download
                    _do_download(result["url"], dest, fname, "Direct Magnet")
                end_directory()

    elif action == "export_settings":
        from resources.lib.kodi_utils import translate_path, end_directory, dialog_ok, notify
        import shutil, os, xbmcgui
        src = translate_path("special://profile/addon_data/plugin.video.rdflix/settings.xml")
        dest = xbmcgui.Dialog().browse(0, "Choose export folder", "files", "", False, True, translate_path("special://home/"))
        if dest and os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, "rdflix_settings_backup.xml"))
            notify("RDFlix", "Settings exported to rdfix_settings_backup.xml")
        end_directory()

    elif action == "import_settings":
        from resources.lib.kodi_utils import translate_path, end_directory, dialog_ok, notify
        import shutil, os, xbmcgui
        dest = translate_path("special://profile/addon_data/plugin.video.rdflix/settings.xml")
        src = xbmcgui.Dialog().browse(1, "Select backup file", "files", ".xml", False, False, translate_path("special://home/"))
        if src and os.path.exists(src):
            shutil.copy2(src, dest)
            notify("RDFlix", "Settings imported. Restart Kodi for changes.")
        end_directory()

    elif action == "analytics":
        analytics_view()

    elif action == "rd_torrent_action":
        from resources.lib.rd_api import torrent_info, delete_torrent, unrestrict_link
        from resources.lib.kodi_utils import dialog_yesno, dialog_ok, add_list_item, build_url, notify
        tid = params.get("tid", "")
        tname = params.get("name", "Unknown")
        if not tid:
            dialog_ok("RDFlix", "Invalid torrent ID")
            end_directory()
        else:
            info = torrent_info(tid)
            status = info.get("status", "?") if info else "?"
            links = (info or {}).get("links", [])
            if links and status == "downloaded":
                ul = unrestrict_link(links[0])
                if ul and ul.get("download"):
                    import xbmcplugin
                    li = xbmcgui.ListItem(path=ul["download"], label=tname)
                    li.setProperty("IsPlayable", "true")
                    xbmcplugin.setResolvedUrl(HANDLE, True, li)
                    return
            li = xbmcgui.ListItem("[B]Delete Torrent[/B]")
            li.setArt({"icon": "DefaultAddon.png"})
            add_list_item(build_url(action="rd_torrent_delete", tid=tid), li, True)
            li = xbmcgui.ListItem("[B].. Back[/B]")
            li.setArt({"icon": "DefaultFolderBack.png"})
            add_list_item(build_url(action="rd_torrents"), li, True)
            end_directory()

    elif action == "rd_torrent_delete":
        from resources.lib.rd_api import delete_torrent
        from resources.lib.kodi_utils import dialog_yesno, notify
        tid = params.get("tid", "")
        if tid and dialog_yesno("RDFlix", "Delete this torrent from Real-Debrid?"):
            delete_torrent(tid)
            notify("RDFlix", "Torrent deleted")
        end_directory()

    elif action == "library_add_movie":
        from resources.lib.library import add_movie_to_library
        add_movie_to_library(
            params.get("tmdb_id", ""),
            params.get("title", ""),
            params.get("year", ""),
            params.get("imdb_id", ""),
        )
        movie_detail_view(params.get("tmdb_id", ""), params.get("title", ""))

    elif action == "library_add_show":
        from resources.lib.library import add_show_to_library
        add_show_to_library(
            params.get("tmdb_id", ""),
            params.get("title", ""),
            params.get("imdb_id", ""),
        )
        tv_detail_view(params.get("tmdb_id", ""), params.get("title", ""))

    elif action == "library_setup":
        from resources.lib.library import set_library_source
        set_library_source()
        dialog_ok("RDFlix", "Library sources registered.\nGo to Kodi Settings > Media > Library > Videos to add the RDFlix folders.")

    elif action == "play_from_library":
        lib_type = params.get("type", "")
        if lib_type == "movie":
            play_movie(
                imdb_id=params.get("imdb_id", ""),
                tmdb_id=params.get("tmdb_id", ""),
                title=params.get("title", ""),
                year="",
            )
        elif lib_type == "episode":
            play_episode(
                imdb_id=params.get("imdb_id", ""),
                tmdb_id=params.get("tmdb_id", ""),
                show_title=params.get("show_title", ""),
                season=params.get("season", "1"),
                episode=params.get("episode", "1"),
                episode_title="",
            )

    elif action == "device_auth":
        device_auth()

    elif action == "trakt_auth":
        from resources.lib.trakt_api import get_device_code, poll_token
        from resources.lib.kodi_utils import dialog_ok, set_setting, notify
        dc, uc, vu = get_device_code()
        if not dc:
            dialog_ok("RDFlix", "Failed to get Trakt device code")
        else:
            dialog_ok("RDFlix", "Go to %s and enter code:\n\n%s" % (vu, uc))
            at, rt = poll_token(dc)
            if at:
                set_setting("trakt_token", at)
                notify("RDFlix", "Trakt authorized successfully!")
            else:
                dialog_ok("RDFlix", "Trakt authorization timed out")

    elif action == "settings":
        from resources.lib.kodi_utils import addon
        addon().openSettings()

    elif action == "play_movie":
        play_movie(
            imdb_id=params.get("imdb_id", ""),
            tmdb_id=params.get("tmdb_id", ""),
            title=params.get("title", ""),
            year=params.get("year", ""),
            resume_pct=float(params.get("resume_pct", "0")),
        )

    elif action == "play_episode":
        play_episode(
            imdb_id=params.get("imdb_id", ""),
            tmdb_id=params.get("tmdb_id", ""),
            show_title=params.get("show_title", ""),
            season=params.get("season", "1"),
            episode=params.get("episode", "1"),
            episode_title=params.get("episode_title", ""),
            resume_pct=float(params.get("resume_pct", "0")),
        )

    elif action == "noop":
        end_directory()

    else:
        log("Unknown action: %s" % action, xbmc.LOGWARNING)
        main_menu()

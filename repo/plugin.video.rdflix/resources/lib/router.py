import sys

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import parse_params, log, dialog_ok, set_setting, notify, end_directory, set_resolved_url
from resources.lib.menus import (
    main_menu, movies_menu, tvshows_menu, movies_genres, tv_genres,
    movies_list, tv_list, movie_detail_view, tv_detail_view,
    season_episodes_view, search_view, account_view,
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

    elif action == "device_auth":
        device_auth()

    elif action == "play_movie":
        play_movie(
            imdb_id=params.get("imdb_id", ""),
            tmdb_id=params.get("tmdb_id", ""),
            title=params.get("title", ""),
            year=params.get("year", ""),
        )

    elif action == "play_episode":
        play_episode(
            imdb_id=params.get("imdb_id", ""),
            tmdb_id=params.get("tmdb_id", ""),
            show_title=params.get("show_title", ""),
            season=params.get("season", "1"),
            episode=params.get("episode", "1"),
            episode_title=params.get("episode_title", ""),
        )

    elif action == "noop":
        end_directory()

    else:
        log("Unknown action: %s" % action, xbmc.LOGWARNING)
        main_menu()

import sys
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import build_url, add_list_item, end_directory, set_content, set_plugin_fanart, get_setting, dialog_ok, keyboard_input
from resources.lib.constants import GENRES_MOVIE, GENRES_TV
from resources.lib.tmdb_api import (
    trending_movies, trending_tv, popular_movies, popular_tv,
    top_rated_movies, top_rated_tv, movies_by_genre, tv_by_genre,
    movie_detail, tv_detail, season_detail, search, image_url,
)
from resources.lib.rd_api import get_user, traffic


def _make_li(label, info=None, art=None):
    li = xbmcgui.ListItem(label=label)
    if info:
        li.setInfo("video", info)
    if art:
        li.setArt(art)
    return li


def _movie_to_info(m, extra=None):
    if not extra:
        extra = {}
    title = m.get("title") or m.get("name", "Unknown")
    return {
        "title": title,
        "originaltitle": m.get("original_title", title),
        "year": (m.get("release_date") or "")[:4],
        "plot": m.get("overview", ""),
        "rating": m.get("vote_average", 0),
        "votes": str(m.get("vote_count", "")),
        "genre": extra.get("genres", ""),
        "duration": extra.get("runtime", 0),
        "mpaa": extra.get("certification", ""),
    }


def _tv_to_info(m):
    title = m.get("name") or m.get("title", "Unknown")
    return {
        "title": title,
        "originaltitle": m.get("original_name", title),
        "tvshowtitle": title,
        "year": (m.get("first_air_date") or "")[:4],
        "plot": m.get("overview", ""),
        "rating": m.get("vote_average", 0),
        "votes": str(m.get("vote_count", "")),
        "genre": m.get("genre_str", ""),
    }


def _art_from_item(item, media_type="movie"):
    poster_key = "poster_path"
    backdrop_key = "backdrop_path"
    if media_type == "tv":
        poster_key = "poster_path"
        backdrop_key = "backdrop_path"
    art = {
        "icon": "DefaultVideo.png" if media_type == "movie" else "DefaultTVShows.png",
    }
    poster = item.get(poster_key, "")
    if poster:
        art["thumb"] = image_url(poster)
        art["poster"] = image_url(poster)
    backdrop = item.get(backdrop_key, "")
    if backdrop:
        art["fanart"] = image_url(backdrop, "original")
    return art


def main_menu():
    items = [
        ("[B]Movies[/B]", build_url(action="movies_menu"), "DefaultVideo.png", {"plot": "Browse movies by category"}),
        ("[B]TV Shows[/B]", build_url(action="tvshows_menu"), "DefaultTVShows.png", {"plot": "Browse TV shows by category"}),
        ("[B]Search[/B]", build_url(action="search"), "DefaultAddonsSearch.png", {"plot": "Search for movies and TV shows"}),
        ("[B]My Account[/B]", build_url(action="account"), "DefaultUser.png", {"plot": "Real-Debrid account information"}),
        ("[B]LordPlayer[/B]", build_url(action="lordplayer"), "DefaultVideoPlay.png", {"plot": "Open LordPlayer for torrent streaming"}),
        ("[B]Settings[/B]", build_url(action="settings"), "DefaultAddonSettings.png", {"plot": "Configure RDFlix settings"}),
    ]
    import xbmc
    for label, url, icon, info in items:
        li = _make_li(label, info, {"icon": icon})
        if build_url(action="lordplayer") == url:
            lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
            import xbmcplugin
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), "plugin://%s/" % lid, li, True)
        elif build_url(action="settings") == url:
            import xbmcplugin
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), build_url(action="settings"), li, True)
        else:
            add_list_item(url, li, True)
    end_directory()


def movies_menu():
    items = [
        ("[B]Trending[/B]", build_url(action="movies_list", category="trending"), "DefaultVideo.png"),
        ("[B]Popular[/B]", build_url(action="movies_list", category="popular"), "DefaultVideo.png"),
        ("[B]Top Rated[/B]", build_url(action="movies_list", category="top_rated"), "DefaultVideo.png"),
        ("[B]Genres[/B]", build_url(action="movies_genres"), "DefaultVideo.png"),
    ]
    for label, url, icon in items:
        li = _make_li(label, {"plot": "Browse movies" if "Genre" not in label else "Browse by genre"}, {"icon": icon})
        add_list_item(url, li, True)
    end_directory()


def tvshows_menu():
    items = [
        ("[B]Trending[/B]", build_url(action="tv_list", category="trending"), "DefaultTVShows.png"),
        ("[B]Popular[/B]", build_url(action="tv_list", category="popular"), "DefaultTVShows.png"),
        ("[B]Top Rated[/B]", build_url(action="tv_list", category="top_rated"), "DefaultTVShows.png"),
        ("[B]Genres[/B]", build_url(action="tv_genres"), "DefaultTVShows.png"),
    ]
    for label, url, icon in items:
        li = _make_li(label, {"plot": "Browse TV shows"}, {"icon": icon})
        add_list_item(url, li, True)
    end_directory()


def movies_genres():
    for name, gid in GENRES_MOVIE:
        li = _make_li(name, {"genre": name, "plot": "Browse %s movies" % name}, {"icon": "DefaultVideo.png"})
        add_list_item(build_url(action="movies_list", category="genre", genre_id=str(gid)), li, True)
    end_directory()


def tv_genres():
    for name, gid in GENRES_TV:
        li = _make_li(name, {"genre": name, "plot": "Browse %s TV shows" % name}, {"icon": "DefaultTVShows.png"})
        add_list_item(build_url(action="tv_list", category="genre", genre_id=str(gid)), li, True)
    end_directory()


def movies_list(category="trending", genre_id="", page=1):
    page = int(page)
    set_content("movies")

    if category == "genre":
        results, total_pages = movies_by_genre(genre_id, page)
    elif category == "popular":
        results, total_pages = popular_movies(page)
    elif category == "top_rated":
        results, total_pages = top_rated_movies(page)
    else:
        results, total_pages = trending_movies(page)

    _display_content_list(results, "movie", "movie_detail", page, total_pages, action="movies_list", category=category, genre_id=genre_id)
    end_directory()


def tv_list(category="trending", genre_id="", page=1):
    page = int(page)
    set_content("tvshows")

    if category == "genre":
        results, total_pages = tv_by_genre(genre_id, page)
    elif category == "popular":
        results, total_pages = popular_tv(page)
    elif category == "top_rated":
        results, total_pages = top_rated_tv(page)
    else:
        results, total_pages = trending_tv(page)

    _display_content_list(results, "tv", "tv_detail", page, total_pages, action="tv_list", category=category, genre_id=genre_id)
    end_directory()


def _display_content_list(results, media_type, detail_action, page, total_pages, **route_params):
    fanart_url = ""
    for item in results:
        backdrop = item.get("backdrop_path", "")
        if backdrop and not fanart_url:
            fanart_url = image_url(backdrop, "original")
        if fanart_url:
            break
    if fanart_url:
        set_plugin_fanart(fanart_url)

    for item in results:
        if media_type == "movie":
            title = item.get("title") or item.get("name", "Unknown")
            label = title
            year = (item.get("release_date") or "")[:4]
            if year:
                label += " [%s]" % year
            rating = item.get("vote_average", 0)
            if rating:
                label += "  [COLOR gold]%.1f[/COLOR]" % rating
            info = _movie_to_info(item)
            art = _art_from_item(item, "movie")
            li = _make_li(label, info, art)
            tmdb_id = item.get("id")
            add_list_item(build_url(action=detail_action, tmdb_id=str(tmdb_id), title=title), li, True)
        else:
            title = item.get("name") or item.get("title", "Unknown")
            label = title
            year = (item.get("first_air_date") or "")[:4]
            if year:
                label += " [%s]" % year
            rating = item.get("vote_average", 0)
            if rating:
                label += "  [COLOR gold]%.1f[/COLOR]" % rating
            info = _tv_to_info(item)
            art = _art_from_item(item, "tv")
            li = _make_li(label, info, art)
            tmdb_id = item.get("id")
            add_list_item(build_url(action=detail_action, tmdb_id=str(tmdb_id), title=title), li, True)

    if page < total_pages and page < 50:
        route_params["page"] = str(page + 1)
        li = _make_li("[B]Next Page >>[/B]", {}, {"icon": "DefaultFolder.png"})
        add_list_item(build_url(**route_params), li, True)


def movie_detail_view(tmdb_id, title=""):
    detail = movie_detail(tmdb_id)
    if not detail:
        dialog_ok("RDFlix", "Failed to load movie details")
        end_directory()
        return

    imdb_id = detail.get("imdb_id") or ""
    tmdb_title = detail.get("title", title)
    year = (detail.get("release_date") or "")[:4]
    backdrop = detail.get("backdrop_path", "")
    fanart = image_url(backdrop, "original") if backdrop else ""
    if fanart:
        set_plugin_fanart(fanart)

    genres = ", ".join([g.get("name", "") for g in detail.get("genres", [])[:5]])
    runtime = detail.get("runtime", 0)
    tagline = detail.get("tagline", "")
    overview = detail.get("overview", "")

    label = "[B]%s[/B] [I](%s)[/I]" % (tmdb_title, year)
    rating = detail.get("vote_average", 0)
    if rating:
        label += "  [COLOR gold]%.1f[/COLOR]" % rating

    info = {
        "title": tmdb_title,
        "originaltitle": detail.get("original_title", tmdb_title),
        "year": year,
        "plot": overview,
        "tagline": tagline,
        "rating": rating,
        "votes": str(detail.get("vote_count", "")),
        "genre": genres,
        "duration": runtime * 60,
        "imdbnumber": imdb_id,
    }

    art = {
        "thumb": image_url(detail.get("poster_path", "")),
        "poster": image_url(detail.get("poster_path", "")),
        "fanart": fanart,
        "icon": "DefaultVideo.png",
    }

    li = _make_li(label, info, art)

    cast_list = []
    for c in (detail.get("credits", {}) or {}).get("cast", [])[:8]:
        cast_list.append(c.get("name", ""))
    if cast_list:
        info["cast"] = cast_list

    directors = []
    for c in (detail.get("credits", {}) or {}).get("crew", []):
        if c.get("job") == "Director":
            directors.append(c.get("name", ""))
    if directors:
        info["director"] = ", ".join(directors)

    li.setInfo("video", info)
    li.setArt(art)
    li.setProperty("IsPlayable", "true")
    add_list_item(build_url(action="play_movie", imdb_id=imdb_id, tmdb_id=tmdb_id, title=tmdb_title, year=year), li, False)

    recommendations = detail.get("recommendations", {}).get("results", []) if isinstance(detail.get("recommendations"), dict) else []
    if recommendations:
        rec_label = _make_li("[B]--- Recommendations ---[/B]", {}, {"icon": "DefaultVideo.png"})
        add_list_item(build_url(action="noop"), rec_label, True)
        for r in recommendations[:10]:
            r_title = r.get("title", "Unknown")
            r_li = _make_li(r_title, _movie_to_info(r), _art_from_item(r, "movie"))
            add_list_item(build_url(action="movie_detail", tmdb_id=str(r.get("id")), title=r_title), r_li, True)

    end_directory()


def tv_detail_view(tmdb_id, title=""):
    detail = tv_detail(tmdb_id)
    if not detail:
        dialog_ok("RDFlix", "Failed to load TV show details")
        end_directory()
        return

    imdb_id = ""
    ext = detail.get("external_ids", {}) or {}
    if ext:
        imdb_id = ext.get("imdb_id", "")

    tmdb_title = detail.get("name", title)
    backdrop = detail.get("backdrop_path", "")
    fanart = image_url(backdrop, "original") if backdrop else ""
    if fanart:
        set_plugin_fanart(fanart)

    genres = ", ".join([g.get("name", "") for g in detail.get("genres", [])[:5]])
    overview = detail.get("overview", "")
    year = (detail.get("first_air_date") or "")[:4]
    rating = detail.get("vote_average", 0)
    seasons_count = detail.get("number_of_seasons", 0)

    label = "[B]%s[/B] [I](%s)[/I]" % (tmdb_title, year)
    if rating:
        label += "  [COLOR gold]%.1f[/COLOR]" % rating

    seasons = detail.get("seasons", [])
    for s in seasons:
        snum = s.get("season_number", 0)
        if snum == 0:
            continue
        ep_count = s.get("episode_count", 0)
        s_name = s.get("name", "Season %d" % snum)

        info = {
            "title": s_name,
            "tvshowtitle": tmdb_title,
            "season": snum,
            "episode": ep_count,
            "plot": s.get("overview", overview),
            "rating": rating,
            "genre": genres,
        }
        art = {
            "thumb": image_url(s.get("poster_path", "") or detail.get("poster_path", "")),
            "fanart": fanart,
            "icon": "DefaultTVShows.png",
        }
        s_label = "[B]%s[/B] [I](%d episodes)[/I]" % (s_name, ep_count)
        s_li = _make_li(s_label, info, art)
        add_list_item(build_url(action="season_episodes", tmdb_id=tmdb_id, season=str(snum), show_title=tmdb_title, imdb_id=imdb_id), s_li, True)

    end_directory()


def season_episodes_view(tmdb_id, season, show_title, imdb_id=""):
    season_num = int(season)
    detail = season_detail(tmdb_id, season_num)
    if not detail:
        dialog_ok("RDFlix", "Failed to load season details")
        end_directory()
        return

    show_detail = tv_detail(tmdb_id)
    backdrop = ""
    if show_detail:
        backdrop = show_detail.get("backdrop_path", "")
    fanart = image_url(backdrop, "original") if backdrop else ""
    if fanart:
        set_plugin_fanart(fanart)

    if not imdb_id and show_detail:
        ext = show_detail.get("external_ids", {}) or {}
        imdb_id = ext.get("imdb_id", "")

    episodes = detail.get("episodes", [])
    for ep in episodes:
        epnum = ep.get("episode_number", 0)
        epname = ep.get("name", "Episode %d" % epnum)
        overview = ep.get("overview", "")
        still = ep.get("still_path", "")

        info = {
            "title": epname,
            "tvshowtitle": show_title,
            "season": season_num,
            "episode": epnum,
            "plot": overview,
            "rating": ep.get("vote_average", 0),
            "aired": ep.get("air_date", ""),
        }

        art = {
            "thumb": image_url(still) or image_url(show_detail.get("poster_path", "")) if show_detail else "",
            "fanart": fanart,
            "icon": "DefaultTVShows.png",
        }

        label = "S%02dE%02d - %s" % (season_num, epnum, epname)
        li = _make_li(label, info, art)
        li.setProperty("IsPlayable", "true")
        add_list_item(build_url(action="play_episode", imdb_id=imdb_id, tmdb_id=tmdb_id, show_title=show_title,
                                season=str(season_num), episode=str(epnum), episode_title=epname), li, False)

    end_directory()


def search_view(query=""):
    if not query:
        query = keyboard_input("Search movies and TV shows...")
    if not query:
        end_directory()
        return

    results, total_pages = search(query)

    if not results:
        dialog_ok("RDFlix", "No results found for\n%s" % query)
        end_directory()
        return

    fanart_url = ""
    for item in results:
        backdrop = item.get("backdrop_path", "")
        if backdrop:
            fanart_url = image_url(backdrop, "original")
            break
    if fanart_url:
        set_plugin_fanart(fanart_url)

    for item in results:
        mtype = item.get("media_type", "movie")
        if mtype == "movie":
            title = item.get("title") or item.get("name", "Unknown")
            year = (item.get("release_date") or "")[:4]
            label = "%s [%s]" % (title, year) if year else title
            label += "  [COLOR yellow][Movie][/COLOR]"
            info = _movie_to_info(item)
            art = _art_from_item(item, "movie")
            li = _make_li(label, info, art)
            add_list_item(build_url(action="movie_detail", tmdb_id=str(item.get("id")), title=title), li, True)
        else:
            title = item.get("name") or item.get("title", "Unknown")
            year = (item.get("first_air_date") or "")[:4]
            label = "%s [%s]" % (title, year) if year else title
            label += "  [COLOR yellow][TV][/COLOR]"
            info = _tv_to_info(item)
            art = _art_from_item(item, "tv")
            li = _make_li(label, info, art)
            add_list_item(build_url(action="tv_detail", tmdb_id=str(item.get("id")), title=title), li, True)

    li = _make_li("[B]New Search[/B]", {}, {"icon": "DefaultSearch.png"})
    add_list_item(build_url(action="search"), li, True)
    end_directory()


def account_view():
    token = get_setting("rd_token", "")
    if not token:
        li = _make_li("[B]No Real-Debrid token configured[/B]", {"plot": "Go to Settings to add your Real-Debrid API token."}, {"icon": "DefaultUser.png"})
        add_list_item(build_url(action="noop"), li, False)

        li = _make_li("[B]Get API Token[/B]", {"plot": "Visit real-debrid.com/apitoken to get your token."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    user_info = get_user()
    if not user_info:
        li = _make_li("[B]Authentication Failed[/B]", {"plot": "Your RD token appears invalid. Check settings."}, {"icon": "DefaultUser.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    username = user_info.get("username", "Unknown")
    email = user_info.get("email", "Unknown")
    premium = user_info.get("premium", 0)
    points = user_info.get("points", 0)
    type_name = user_info.get("type", "free")

    li = _make_li("[B]Username:[/B] %s" % username, {"plot": "Real-Debrid account"}, {"icon": "DefaultUser.png"})
    add_list_item(build_url(action="noop"), li, False)

    li = _make_li("[B]Email:[/B] %s" % email, {"plot": ""}, {"icon": "DefaultInfo.png"})
    add_list_item(build_url(action="noop"), li, False)

    status = "[COLOR green]Premium[/COLOR]" if premium > 0 else "[COLOR red]Free[/COLOR]"
    li = _make_li("[B]Status:[/B] %s" % status, {"plot": "Account type: %s" % type_name}, {"icon": "DefaultInfo.png"})
    add_list_item(build_url(action="noop"), li, False)

    if premium > 0:
        days_left = premium / 86400 if premium > 0 else 0
        li = _make_li("[B]Premium Days Left:[/B] %.1f" % days_left, {"plot": ""}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)

    li = _make_li("[B]Fidelity Points:[/B] %d" % points, {"plot": ""}, {"icon": "DefaultInfo.png"})
    add_list_item(build_url(action="noop"), li, False)

    traffic_info = traffic()
    if traffic_info:
        left = traffic_info.get("left", 0)
        left_gb = left / (1024 * 1024 * 1024) if left else 0
        li = _make_li("[B]Traffic Left:[/B] %.2f GB" % left_gb, {"plot": ""}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)

    end_directory()

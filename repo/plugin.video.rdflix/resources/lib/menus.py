import sys
import xbmcgui
import xbmcplugin

from resources.lib.kodi_utils import build_url, add_list_item, end_directory, set_content, set_plugin_fanart, get_setting, dialog_ok, dialog_select, dialog_yesno, keyboard_input, set_resolved_url
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
        ("[B]Live TV[/B]", build_url(action="livetv"), "DefaultAddon.png", {"plot": "Watch live TV channels from your playlists"}),
        ("[B]Movies[/B]", build_url(action="movies_menu"), "DefaultVideo.png", {"plot": "Browse movies by category"}),
        ("[B]TV Shows[/B]", build_url(action="tvshows_menu"), "DefaultTVShows.png", {"plot": "Browse TV shows by category"}),
    ]
    if get_setting("show_continue", "true") == "true":
        items.append(("[B]Continue Watching[/B]", build_url(action="continue_watching"), "DefaultRecentlyAddedEpisodes.png", {"plot": "Resume partially watched content"}))
    if get_setting("show_for_you", "true") == "true":
        items.append(("[B]For You[/B]", build_url(action="for_you"), "DefaultAddon.png", {"plot": "Personalized recommendations"}))
    if get_setting("show_surprise", "true") == "true":
        items.append(("[B]Surprise Me[/B]", build_url(action="surprise_me"), "DefaultAddon.png", {"plot": "Play something random"}))
    if get_setting("show_trakt_watchlist", "true") == "true":
        items.append(("[B]Trakt Watchlist[/B]", build_url(action="trakt_watchlist"), "DefaultAddon.png", {"plot": "Your Trakt watchlist"}))
    items.append(("[B]Sports[/B]", build_url(action="sports_search"), "DefaultAddon.png", {"plot": "Search for sporting events - WWE, UFC, Football and more"}))
    items.append(("[B]Search[/B]", build_url(action="search"), "DefaultAddonsSearch.png", {"plot": "Search for movies and TV shows"}))
    items.append(("[B]My Account[/B]", build_url(action="account"), "DefaultUser.png", {"plot": "Real-Debrid account information"}))
    items.append(("[B]LordPlayer[/B]", build_url(action="lordplayer"), "DefaultAddon.png", {"plot": "Open LordPlayer for torrent streaming"}))
    if get_setting("show_open_magnet", "true") == "true":
        items.append(("[B]Open Magnet[/B]", build_url(action="open_magnet"), "DefaultAddon.png", {"plot": "Paste any magnet link and play through RD"}))
    items.append(("[B]Settings[/B]", build_url(action="settings"), "DefaultAddon.png", {"plot": "Configure RDFlix settings"}))
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

    for c in (detail.get("credits", {}) or {}).get("cast", [])[:6]:
        cname = c.get("name", "")
        pid = c.get("id", "")
        if cname and pid:
            cast_label = "[B]Cast:[/B] %s" % cname if c == (detail.get("credits", {}) or {}).get("cast", [])[0] else cname
            cast_li = _make_li(cast_label, {"title": cname, "plot": c.get("character", "")}, {"icon": "DefaultUser.png"})
            add_list_item(build_url(action="person_detail", person_id=str(pid), person_name=cname), cast_li, True)

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
    from resources.lib.analytics import get_continue_watching
    cw = get_continue_watching(500)
    watched_eps = len([e for e in cw if e["show_title"] == tmdb_title and e["progress"] >= 100])

    if watched_eps > 0:
        label = "[B]%s[/B] [I](%s)[/I]" % (tmdb_title, year)
        label += "  [COLOR lime]%d eps watched[/COLOR]" % watched_eps
        if rating:
            label += "  [COLOR gold]%.1f[/COLOR]" % rating
        info_label = _make_li(label, {"title": tmdb_title, "plot": overview}, {"icon": "DefaultTVShows.png"})
        add_list_item(build_url(action="noop"), info_label, False)

    li = _make_li("[B]Add Show to Library[/B]", {"plot": "Create library folder for %s" % tmdb_title}, {"icon": "DefaultAddon.png"})
    add_list_item(build_url(action="library_add_show", tmdb_id=tmdb_id, title=tmdb_title, imdb_id=imdb_id), li, True)

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

        if overview:
            syn_label = "[I][COLOR gray]%s[/COLOR][/I]" % overview[:200]
            syn_li = _make_li(syn_label, {"plot": overview, "title": epname}, {"icon": "DefaultInfo.png"})
            add_list_item(build_url(action="noop"), syn_li, True)

        art = {
            "thumb": image_url(still) or image_url(show_detail.get("poster_path", "")) if show_detail else "",
            "fanart": fanart,
            "icon": "DefaultTVShows.png",
        }

        label = "S%02dE%02d - %s" % (season_num, epnum, epname)
        if overview:
            label += "\n[I][COLOR gray]%s[/COLOR][/I]" % overview[:120]
        li = _make_li(label, info, art)
        li.setProperty("IsPlayable", "true")
        try:
            tag = li.getVideoInfoTag()
            tag.setTitle(epname)
            tag.setTvShowTitle(show_title)
            tag.setSeason(season_num)
            tag.setEpisode(epnum)
            tag.setPlot(overview or "")
            tag.setRating(ep.get("vote_average", 0) or 0, 0)
            tag.setFirstAired(ep.get("air_date", "") or "")
        except:
            pass
        add_list_item(build_url(action="play_episode", imdb_id=imdb_id, tmdb_id=tmdb_id, show_title=show_title,
                                season=str(season_num), episode=str(epnum), episode_title=epname), li, False)

    li = _make_li("[B].. Back to Seasons[/B]", {}, {"icon": "DefaultFolderBack.png"})
    add_list_item(build_url(action="tv_detail", tmdb_id=tmdb_id, title=show_title), li, True)
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

    li = _make_li("[B]Manage RD Torrents[/B]", {"plot": "View and manage your Real-Debrid torrents"}, {"icon": "DefaultAddon.png"})
    add_list_item(build_url(action="rd_torrents"), li, True)

    li = _make_li("[B]Source Analytics[/B]", {"plot": "Scraper performance and success rates"}, {"icon": "DefaultAddon.png"})
    add_list_item(build_url(action="analytics"), li, True)

    li = _make_li("[B]Debrid Speed Test[/B]", {"plot": "Test response times for each debrid service"}, {"icon": "DefaultAddon.png"})
    add_list_item(build_url(action="speed_test"), li, True)

    li = _make_li("[B]Export Settings[/B]", {"plot": "Backup RDFlix settings to a file"}, {"icon": "DefaultAddon.png"})
    add_list_item(build_url(action="export_settings"), li, True)

    li = _make_li("[B]Import Settings[/B]", {"plot": "Restore RDFlix settings from a backup"}, {"icon": "DefaultAddon.png"})
    add_list_item(build_url(action="import_settings"), li, True)
    end_directory()


def rd_torrents_view():
    from resources.lib.rd_api import torrents, delete_torrent
    items = torrents()
    if not items:
        li = _make_li("[B]No torrents found in RD account[/B]", {"plot": "Your RD torrent list is empty."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    for t in items:
        name = t.get("filename", "Unknown")
        status = t.get("status", "?")
        size_val = t.get("bytes", 0) or 0
        size_str = ""
        if size_val >= 1073741824:
            size_str = "%.1f GB" % (size_val / 1073741824)
        elif size_val >= 1048576:
            size_str = "%.0f MB" % (size_val / 1048576)

        if status == "downloaded":
            status_label = "[COLOR green]%s[/COLOR]" % status
        elif status in ("downloading", "waiting_files_selection", "magnet_conversion"):
            status_label = "[COLOR yellow]%s[/COLOR]" % status
        else:
            status_label = "[COLOR gray]%s[/COLOR]" % status

        label = "%s %s %s" % (status_label, size_str, name[:50])
        li = _make_li(label, {"title": name, "plot": "Status: %s\nSize: %s\nID: %s" % (status, size_str, t.get("id", ""))}, {"icon": "DefaultVideo.png"})
        tid = t.get("id", "")
        add_list_item(build_url(action="rd_torrent_action", tid=tid, name=name), li, True)

    end_directory()


def continue_watching_view():
    from resources.lib.analytics import get_continue_watching
    items = get_continue_watching()
    if not items:
        li = _make_li("[B]No content in progress[/B]", {"plot": "Start watching something and it will appear here."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    for item in items:
        if item["season"] and item["episode"]:
            label = "%s S%02dE%02d (%.0f%%)" % (
                item["show_title"] or item["title"],
                item["season"], item["episode"],
                item["progress"])
            url = build_url(
                action="play_episode",
                imdb_id=item["imdb_id"] or "",
                tmdb_id=item["tmdb_id"] or "",
                show_title=item["show_title"] or item["title"],
                season=str(item["season"]),
                episode=str(item["episode"]),
                episode_title="",
                resume_pct=str(item["progress"]))
            icon = "DefaultTVShows.png"
        else:
            label = "%s (%.0f%%)" % (item["title"], item["progress"])
            url = build_url(
                action="play_movie",
                imdb_id=item["imdb_id"] or "",
                tmdb_id=item["tmdb_id"] or "",
                title=item["title"], year="",
                resume_pct=str(item["progress"]))
            icon = "DefaultVideo.png"

        li = _make_li(label, {"title": item["title"], "plot": "Progress: %.0f%%" % item["progress"]}, {"icon": icon})
        li.setProperty("IsPlayable", "true")
        add_list_item(url, li, False)

    end_directory()


def analytics_view():
    from resources.lib.analytics import get_scraper_ranking
    ranking = get_scraper_ranking()
    if not ranking:
        li = _make_li("[B]No analytics data yet[/B]", {"plot": "Data appears after you search for sources."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    total_success = sum(r["success_count"] for r in ranking)
    total_fail = sum(r["fail_count"] for r in ranking)
    total_runs = total_success + total_fail
    overall_rate = (total_success / total_runs * 100) if total_runs > 0 else 0

    label = "[B]Overall: %d runs, %.0f%% success[/B]" % (total_runs, overall_rate)
    li = _make_li(label, {"plot": "Source scraper performance analytics"}, {"icon": "DefaultInfo.png"})
    add_list_item(build_url(action="noop"), li, False)

    for r in ranking[:10]:
        label = "%s: %d found, %.0f%% rate, %dms avg" % (
            r["name"], r["success_count"], r["success_rate"], r["avg_time_ms"])
        li = _make_li(label, {"plot": "Success: %d, Fail: %d" % (r["success_count"], r["fail_count"])}, {"icon": "DefaultAddon.png"})
        add_list_item(build_url(action="noop"), li, False)

    end_directory()


def surprise_me_view():
    import random, xbmc
    from resources.lib.tmdb_api import trending_movies, trending_tv, movie_detail, tv_detail

    choice = dialog_select("Surprise Me!", ["Random Movie", "Random TV Episode", "Random Anything"])
    if choice < 0:
        end_directory()
        return

    if choice == 0:
        movies, _ = trending_movies(1)
        if not movies:
            dialog_ok("RDFlix", "Failed to load movies")
            end_directory()
            return
        pick = random.choice(movies[:20])
        title = pick.get("title", "Unknown")
        tmdb_id = pick.get("id")
        detail = movie_detail(tmdb_id) if tmdb_id else None
        imdb_id = detail.get("imdb_id", "") if detail else ""
        year = (pick.get("release_date") or "")[:4]
        label = "[B]%s[/B] (%s)" % (title, year)
        rating = pick.get("vote_average", 0)
        if rating: label += " [COLOR gold]%.1f[/COLOR]" % rating
        overview = (detail or {}).get("overview", "")[:200]
        if not dialog_yesno("RDFlix", "Play this?\n\n%s\n\n%s" % (label, overview)):
            end_directory()
            return
        url = build_url(action="play_movie", imdb_id=imdb_id, tmdb_id=str(tmdb_id), title=title, year=year)
        xbmc.Player().play(url, xbmcgui.ListItem(label=title))
        end_directory()

    elif choice == 1:
        shows, _ = trending_tv(1)
        if not shows:
            dialog_ok("RDFlix", "Failed to load TV shows")
            end_directory()
            return
        pick = random.choice(shows[:20])
        title = pick.get("name", "Unknown")
        tmdb_id = pick.get("id")
        detail = tv_detail(tmdb_id) if tmdb_id else None
        imdb_id = ""
        ext = (detail or {}).get("external_ids", {}) or {}
        imdb_id = ext.get("imdb_id", "")
        seasons = (detail or {}).get("seasons", [])
        valid = [s for s in seasons if s.get("season_number", 0) > 0 and s.get("episode_count", 0) > 0]
        if not valid:
            dialog_ok("RDFlix", "No episodes found")
            end_directory()
            return
        season = random.choice(valid)
        snum = season.get("season_number", 1)
        epnum = random.randint(1, min(season.get("episode_count", 1), 25))
        label = "%s S%02dE%02d" % (title, snum, epnum)
        if not dialog_yesno("RDFlix", "Play this?\n\n%s" % label):
            end_directory()
            return
        url = build_url(action="play_episode", imdb_id=imdb_id, tmdb_id=str(tmdb_id), show_title=title, season=str(snum), episode=str(epnum), episode_title="")
        xbmc.Player().play(url, xbmcgui.ListItem(label=label))
        end_directory()

    else:
        coin = random.choice(["movie", "episode"])
        if coin == "movie":
            movies, _ = trending_movies(1)
            if movies:
                pick = random.choice(movies[:20])
                title = pick.get("title", "Unknown")
                tmdb_id = pick.get("id")
                detail = movie_detail(tmdb_id) if tmdb_id else None
                imdb_id = detail.get("imdb_id", "") if detail else ""
                year = (pick.get("release_date") or "")[:4]
                label = "[B]%s[/B] (%s)" % (title, year)
                if not dialog_yesno("RDFlix", "Play this?\n\n%s" % label):
                    end_directory()
                    return
                url = build_url(action="play_movie", imdb_id=imdb_id, tmdb_id=str(tmdb_id), title=title, year=year)
                xbmc.Player().play(url, xbmcgui.ListItem(label=title))
            end_directory()
        else:
            shows, _ = trending_tv(1)
            if shows:
                pick = random.choice(shows[:20])
                title = pick.get("name", "Unknown")
                tmdb_id = pick.get("id")
                detail = tv_detail(tmdb_id) if tmdb_id else None
                imdb_id = ""
                ext = (detail or {}).get("external_ids", {}) or {}
                imdb_id = ext.get("imdb_id", "")
                seasons = (detail or {}).get("seasons", [])
                valid = [s for s in seasons if s.get("season_number", 0) > 0 and s.get("episode_count", 0) > 0]
                if valid:
                    season = random.choice(valid)
                    snum = season.get("season_number", 1)
                    epnum = random.randint(1, min(season.get("episode_count", 1), 25))
                    label = "%s S%02dE%02d" % (title, snum, epnum)
                    if not dialog_yesno("RDFlix", "Play this?\n\n%s" % label):
                        end_directory()
                        return
                    url = build_url(action="play_episode", imdb_id=imdb_id, tmdb_id=str(tmdb_id), show_title=title, season=str(snum), episode=str(epnum), episode_title="")
                    xbmc.Player().play(url, xbmcgui.ListItem(label=label))
                    end_directory()
                    return
                else:
                    end_directory()
                    return
            else:
                end_directory()
                return



def for_you_view():
    from resources.lib.analytics import get_continue_watching
    from resources.lib.tmdb_api import trending_movies, trending_tv, movies_by_genre, tv_by_genre, image_url

    cw = get_continue_watching(100)
    episodes = [e for e in cw if e["season"] and e["progress"] >= 50]

    if not episodes:
        li = _make_li("[B]Watch more to get recommendations[/B]", {"plot": "Your personalized picks appear after you watch a few shows."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    show_counts = {}
    for e in episodes:
        name = e["show_title"] or e["title"]
        show_counts[name] = show_counts.get(name, 0) + 1
    top_show = max(show_counts, key=show_counts.get)

    li = _make_li("[B]Because you watch %s[/B]" % top_show, {"plot": "Trending shows similar to your favorites"}, {"icon": "DefaultTVShows.png"})
    add_list_item(build_url(action="noop"), li, False)

    shows, _ = trending_tv(1)
    for s in shows[:5]:
        title = s.get("name", "Unknown")
        year = (s.get("first_air_date") or "")[:4]
        rating = s.get("vote_average", 0)
        label = title
        if year: label += " [%s]" % year
        if rating: label += " [COLOR gold]%.1f[/COLOR]" % rating
        art = {"thumb": image_url(s.get("poster_path", "")), "icon": "DefaultTVShows.png"}
        li = _make_li(label, _tv_to_info(s), art)
        add_list_item(build_url(action="tv_detail", tmdb_id=str(s.get("id")), title=title), li, True)

    movies, _ = trending_movies(1)
    li = _make_li("[B]Trending Movies[/B]", {"plot": "Popular right now"}, {"icon": "DefaultVideo.png"})
    add_list_item(build_url(action="noop"), li, False)
    for m in movies[:5]:
        title = m.get("title", "Unknown")
        year = (m.get("release_date") or "")[:4]
        rating = m.get("vote_average", 0)
        label = title
        if year: label += " [%s]" % year
        if rating: label += " [COLOR gold]%.1f[/COLOR]" % rating
        art = {"thumb": image_url(m.get("poster_path", "")), "icon": "DefaultVideo.png"}
        li = _make_li(label, _movie_to_info(m), art)
        add_list_item(build_url(action="movie_detail", tmdb_id=str(m.get("id")), title=title), li, True)

    end_directory()


def trakt_watchlist_view():
    from resources.lib.trakt_api import get_watchlist, is_authenticated
    if not is_authenticated():
        li = _make_li("[B]Trakt not authorized[/B]", {"plot": "Go to Settings > Trakt > Authorize Trakt."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    items = get_watchlist()
    if not items:
        li = _make_li("[B]Watchlist is empty[/B]", {"plot": "Add movies and shows to your Trakt watchlist."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    for item in items:
        if item["type"] == "movie":
            title = item["title"]
            year = str(item.get("year", ""))
            label = title
            if year: label += " [%s]" % year
            if item.get("rating"): label += " [COLOR gold]%.0f%%[/COLOR]" % (item["rating"])
            label += " [COLOR yellow][Movie][/COLOR]"
            li = _make_li(label, {"title": title, "year": year, "plot": item.get("overview", "")}, {"icon": "DefaultVideo.png"})
            add_list_item(build_url(action="movie_detail", tmdb_id=str(item.get("tmdb_id", "")), title=title), li, True)
        else:
            title = item["title"]
            year = str(item.get("year", ""))
            label = title
            if year: label += " [%s]" % year
            if item.get("rating"): label += " [COLOR gold]%.0f%%[/COLOR]" % (item["rating"])
            label += " [COLOR yellow][TV][/COLOR]"
            li = _make_li(label, {"title": title, "year": year, "plot": item.get("overview", "")}, {"icon": "DefaultTVShows.png"})
            add_list_item(build_url(action="tv_detail", tmdb_id=str(item.get("tmdb_id", "")), title=title), li, True)

    end_directory()


def sports_search_view(query=""):
    from resources.lib.scrapers import search_sports
    from resources.lib.player import _build_source_label, _merge_sources, _check_rd_cache

    if not query:
        query = keyboard_input("Search sports events...\n(e.g. WWE Raw, UFC 300, NFL)")
    if not query:
        end_directory()
        return

    scr_sources = search_sports(query)
    if not scr_sources:
        dialog_ok("RDFlix", "No results for\n%s" % query)
        end_directory()
        return

    sources = _merge_sources([], scr_sources)
    sources = _check_rd_cache(sources)

    if not sources:
        dialog_ok("RDFlix", "No sources for\n%s" % query)
        end_directory()
        return

    labels = [_build_source_label(s) for s in sources]
    labels.append("[B]New Search[/B]")
    idx = dialog_select("Sports: %s (%d sources)" % (query[:35], len(sources)), labels)
    if idx < 0:
        end_directory()
        return
    if idx >= len(sources):
        sports_search_view()
        return

    chosen = sources[idx]
    choice = dialog_select("Sports: %s" % query[:30], ["Play", "Download"])
    if choice == 0:
        import xbmc, urllib.parse
        from resources.lib.rd_api import resolve_magnet
        magnet = chosen.get("magnet", "")
        info_hash = chosen.get("infoHash", "")
        if not magnet and info_hash and len(info_hash) >= 40:
            magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(query))
        if magnet:
            result = resolve_magnet(magnet, query)
            if result and result.get("url"):
                li = xbmcgui.ListItem(path=result["url"], label=query)
                xbmc.Player().play(result["url"], li)
            else:
                lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
                plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (lid, urllib.parse.quote(magnet, safe=""))
                li = xbmcgui.ListItem(path=plugin_url, label=query)
                xbmc.Player().play(plugin_url, li)
        else:
            dialog_ok("RDFlix", "No playable magnet found")
        end_directory()
    elif choice == 1:
        from resources.lib.player import _download_source
        _download_source(chosen, query)
        end_directory()


def livetv_menu():
    from resources.lib.livetv import load_channels, get_groups
    channels = load_channels()
    if not channels:
        li = _make_li("[B]No playlists configured[/B]", {"plot": "Add M3U playlist URLs in Settings > Live TV."}, {"icon": "DefaultAddon.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    li = _make_li("[B]All Channels[/B] (%d)" % len(channels), {"plot": "Browse all channels"}, {"icon": "DefaultTVShows.png"})
    add_list_item(build_url(action="livetv_channels", group="__all__"), li, True)

    groups = get_groups(channels)
    for group in groups:
        count = len([c for c in channels if c.get("tvg-group", c.get("group-title", "Other")) == group])
        li = _make_li("[B]%s[/B] (%d)" % (group, count), {"plot": "Browse %s channels" % group}, {"icon": "DefaultAddon.png"})
        add_list_item(build_url(action="livetv_channels", group=group), li, True)

    end_directory()


def livetv_channels_view(group="__all__"):
    from resources.lib.livetv import load_channels, get_channels_by_group
    channels = load_channels()
    if not channels:
        end_directory()
        return

    if group != "__all__":
        channels = get_channels_by_group(channels, group)

    for c in channels:
        name = c.get("name", "Unknown")
        logo = c.get("tvg-logo", "")
        info = {"title": name, "plot": "Group: %s" % c.get("tvg-group", c.get("group-title", ""))}
        art = {"icon": "DefaultTVShows.png"}
        if logo and logo.startswith("http"):
            art["thumb"] = logo
        li = _make_li(name, info, art)
        li.setProperty("IsPlayable", "true")
        url = c.get("url", "")
        if url:
            li.setPath(url)
            if url.endswith(".m3u8") or "m3u8" in url:
                li.setProperty("inputstream", "inputstream.adaptive")
                li.setProperty("inputstream.adaptive.manifest_type", "hls")
            add_list_item(build_url(action="livetv_play", url=url, title=name), li, False)
        else:
            add_list_item(build_url(action="noop"), li, False)

    end_directory()


def livetv_play(url, title=""):
    import xbmc
    li = xbmcgui.ListItem(path=url, label=title)
    li.setProperty("IsPlayable", "true")
    if ".m3u8" in url:
        li.setProperty("inputstream", "inputstream.adaptive")
        li.setProperty("inputstream.adaptive.manifest_type", "hls")
    li.setProperty("inputstream.adaptive.stream_headers", "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36&Referer=https://iptv-org.github.io/")
    set_resolved_url(True, li)


def person_detail_view(person_id, person_name=""):
    from resources.lib.tmdb_api import person_detail, person_movie_credits, person_tv_credits, image_url
    p = person_detail(person_id)

    profile = ""
    if p:
        profile = image_url(p.get("profile_path", ""), "w342")
        set_plugin_fanart(profile or "")
        bio = (p.get("biography") or "")[:300]
        label = "[B]%s[/B]" % person_name
        li = _make_li(label, {"title": person_name, "plot": bio}, {"thumb": profile, "icon": "DefaultUser.png"})
        add_list_item(build_url(action="noop"), li, False)

    movie_credits = person_movie_credits(person_id)
    if movie_credits:
        cast_movies = (movie_credits.get("cast") or [])[:10]
        if cast_movies:
            li = _make_li("[B]--- Movies ---[/B]", {}, {"icon": "DefaultVideo.png"})
            add_list_item(build_url(action="noop"), li, False)
            for m in cast_movies:
                title = m.get("title", "Unknown")
                year = (m.get("release_date") or "")[:4]
                label = title
                if year: label += " [%s]" % year
                li = _make_li(label, {"title": title, "year": year}, {"thumb": image_url(m.get("poster_path", "")), "icon": "DefaultVideo.png"})
                add_list_item(build_url(action="movie_detail", tmdb_id=str(m.get("id", "")), title=title), li, True)

    tv_credits = person_tv_credits(person_id)
    if tv_credits:
        cast_tv = (tv_credits.get("cast") or [])[:10]
        if cast_tv:
            li = _make_li("[B]--- TV Shows ---[/B]", {}, {"icon": "DefaultTVShows.png"})
            add_list_item(build_url(action="noop"), li, False)
            for s in cast_tv:
                title = s.get("name", "Unknown")
                year = (s.get("first_air_date") or "")[:4]
                label = title
                if year: label += " [%s]" % year
                li = _make_li(label, {"title": title, "year": year}, {"thumb": image_url(s.get("poster_path", "")), "icon": "DefaultTVShows.png"})
                add_list_item(build_url(action="tv_detail", tmdb_id=str(s.get("id", "")), title=title), li, True)

    end_directory()


def sports_search_view(query=""):
    from resources.lib.scrapers import search_sports
    from resources.lib.player import _build_source_label, _merge_sources, _check_rd_cache

    if not query:
        query = keyboard_input("Search sports events...\n(e.g. WWE Raw, UFC 300, NFL)")
    if not query:
        end_directory()
        return

    scr_sources = search_sports(query)
    if not scr_sources:
        dialog_ok("RDFlix", "No results for\n%s" % query)
        end_directory()
        return

    sources = _merge_sources([], scr_sources)
    sources = _check_rd_cache(sources)

    if not sources:
        dialog_ok("RDFlix", "No sources for\n%s" % query)
        end_directory()
        return

    labels = [_build_source_label(s) for s in sources]
    labels.append("[B]New Search[/B]")
    idx = dialog_select("Sports: %s (%d sources)" % (query[:35], len(sources)), labels)
    if idx < 0:
        end_directory()
        return
    if idx >= len(sources):
        sports_search_view()
        return

    chosen = sources[idx]
    choice = dialog_select("Sports: %s" % query[:30], ["Play", "Download"])
    if choice == 0:
        import xbmc, urllib.parse
        from resources.lib.rd_api import resolve_magnet
        magnet = chosen.get("magnet", "")
        info_hash = chosen.get("infoHash", "")
        if not magnet and info_hash and len(info_hash) >= 40:
            magnet = "magnet:?xt=urn:btih:%s&dn=%s" % (info_hash[:40], urllib.parse.quote(query))
        if magnet:
            result = resolve_magnet(magnet, query)
            if result and result.get("url"):
                li = xbmcgui.ListItem(path=result["url"], label=query)
                xbmc.Player().play(result["url"], li)
            else:
                lid = "plugin.video.lordplayer.droid" if xbmc.getCondVisibility("System.HasAddon(plugin.video.lordplayer.droid)") else "plugin.video.lordplayer"
                plugin_url = "plugin://%s/play_magnet?magnet=%s&buffer=true" % (lid, urllib.parse.quote(magnet, safe=""))
                li = xbmcgui.ListItem(path=plugin_url, label=query)
                xbmc.Player().play(plugin_url, li)
        else:
            dialog_ok("RDFlix", "No playable magnet found")
        end_directory()
    elif choice == 1:
        from resources.lib.player import _download_source
        _download_source(chosen, query)
        end_directory()


def speed_test_view():
    from resources.lib.speedtest import run_speed_test
    results = run_speed_test()

    if not results:
        li = _make_li("[B]No debrid services configured[/B]", {"plot": "Add a debrid token in Settings to test."}, {"icon": "DefaultInfo.png"})
        add_list_item(build_url(action="noop"), li, False)
        end_directory()
        return

    for r in results:
        status_icon = "[COLOR green]ONLINE[/COLOR]" if r["active"] else "[COLOR red]OFFLINE[/COLOR]"
        p_icon = "[COLOR green]Premium[/COLOR]" if r["premium"] else "[COLOR orange]Free[/COLOR]"
        label = "[B]%s[/B] %s %s %dms" % (r["name"], status_icon, p_icon, r["latency_ms"])
        plot = "Latency: %dms\nUser: %s\nPremium: %s" % (r["latency_ms"], r.get("username", "?"), r["premium"])
        li = _make_li(label, {"plot": plot}, {"icon": "DefaultAddon.png"})
        add_list_item(build_url(action="noop"), li, False)

    end_directory()


def watch_stats_view():
    from resources.lib.analytics import get_continue_watching, get_scraper_ranking

    cw = get_continue_watching(100)
    ranking = get_scraper_ranking()

    completed = [e for e in cw if e["progress"] >= 100]
    in_progress = [e for e in cw if e["progress"] < 100]
    movies = [e for e in completed if not e["season"]]
    episodes = [e for e in completed if e["season"]]

    show_counts = {}
    for e in episodes:
        name = e["show_title"] or e["title"]
        show_counts[name] = show_counts.get(name, 0) + 1
    top_shows = sorted(show_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_scraper = ranking[0]["name"] if ranking else "Unknown"

    li = _make_li("[B]Your Watch Stats[/B]", {"plot": "Movies: %d | Episodes: %d | In progress: %d | Best scraper: %s" % (
        len(movies), len(episodes), len(in_progress), top_scraper)}, {"icon": "DefaultInfo.png"})
    add_list_item(build_url(action="noop"), li, False)

    for name, count in top_shows:
        li = _make_li("Top Show: %s (%d eps)" % (name, count), {}, {"icon": "DefaultTVShows.png"})
        add_list_item(build_url(action="noop"), li, False)

    end_directory()

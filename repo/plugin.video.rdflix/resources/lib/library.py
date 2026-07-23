import os
import re

import xbmcvfs

from resources.lib.kodi_utils import log, translate_path, get_setting, notify


def _get_library_base():
    path = get_setting("library_path", "")
    if not path:
        path = "special://profile/addon_data/plugin.video.rdflix/library/"
    return translate_path(path)


def _get_movie_path():
    return os.path.join(_get_library_base(), "Movies")


def _get_tv_path():
    return os.path.join(_get_library_base(), "TV Shows")


def _sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', '', name)


def add_movie_to_library(tmdb_id, title, year, imdb_id):
    movie_dir = _get_movie_path()
    os.makedirs(movie_dir, exist_ok=True)

    url = "plugin://plugin.video.rdflix/?action=play_from_library&type=movie&tmdb_id=%s&imdb_id=%s&title=%s" % (
        tmdb_id, imdb_id or "", title.replace(" ", "+"))

    fname = _sanitize_filename("%s (%s)" % (title, year)) if year else _sanitize_filename(title)
    fpath = os.path.join(movie_dir, fname + ".strm")

    with open(fpath, "w") as f:
        f.write(url)

    log("Added to library: %s" % fpath)
    notify("RDFlix", "Added to Library: %s" % title)


def remove_movie_from_library(tmdb_id, title, year):
    movie_dir = _get_movie_path()
    fname = _sanitize_filename("%s (%s)" % (title, year)) if year else _sanitize_filename(title)
    fpath = os.path.join(movie_dir, fname + ".strm")
    if os.path.exists(fpath):
        os.remove(fpath)
        notify("RDFlix", "Removed from Library: %s" % title)


def add_episode_to_library(tmdb_id, show_title, season, episode, episode_title, imdb_id):
    tv_dir = _get_tv_path()
    show_dir = os.path.join(tv_dir, _sanitize_filename(show_title))
    season_dir = os.path.join(show_dir, "Season %02d" % int(season))
    os.makedirs(season_dir, exist_ok=True)

    url = "plugin://plugin.video.rdflix/?action=play_from_library&type=episode&tmdb_id=%s&imdb_id=%s&show_title=%s&season=%s&episode=%s" % (
        tmdb_id, imdb_id or "", show_title.replace(" ", "+"), season, episode)

    label = "S%02dE%02d" % (int(season), int(episode))
    if episode_title:
        label += " - " + _sanitize_filename(episode_title)
    fpath = os.path.join(season_dir, label + ".strm")

    with open(fpath, "w") as f:
        f.write(url)

    log("Added episode to library: %s" % fpath)
    notify("RDFlix", "Added: %s S%02dE%02d" % (show_title, int(season), int(episode)))


def add_show_to_library(tmdb_id, show_title, imdb_id):
    tv_dir = _get_tv_path()
    show_dir = os.path.join(tv_dir, _sanitize_filename(show_title))
    os.makedirs(show_dir, exist_ok=True)
    notify("RDFlix", "TV Show folder created: %s\nScrape to add episodes." % show_title)


def set_library_source():
    """Register library folders with Kodi as video sources."""
    import json, xbmc
    movie_path = _get_movie_path()
    tv_path = _get_tv_path()
    os.makedirs(movie_path, exist_ok=True)
    os.makedirs(tv_path, exist_ok=True)

    sources = {
        "video": [
            {"name": "RDFlix Movies", "path": movie_path, "content": "movies"},
            {"name": "RDFlix TV Shows", "path": tv_path, "content": "tvshows"},
        ]
    }

    sources_path = translate_path("special://profile/sources.xml")
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(sources_path) if os.path.exists(sources_path) else None
        if tree is None:
            root = ET.Element("sources")
            tree = ET.ElementTree(root)
        else:
            root = tree.getroot()

        for source in sources["video"]:
            exists = False
            for elem in root.findall(".//path"):
                if elem.text and source["path"] in elem.text:
                    exists = True
                    break
            if not exists:
                video_el = ET.SubElement(root, "source")
                name_el = ET.SubElement(video_el, "name")
                name_el.text = source["name"]
                path_el = ET.SubElement(video_el, "path")
                path_el.text = source["path"] + "/"
                path_el.set("pathversion", "1")
                allowsharing_el = ET.SubElement(video_el, "allowsharing")
                allowsharing_el.text = "true"

        tree.write(sources_path, encoding="utf-8", xml_declaration=True)
        log("Library sources registered")
    except Exception as e:
        log("Library source registration error: %s" % str(e))

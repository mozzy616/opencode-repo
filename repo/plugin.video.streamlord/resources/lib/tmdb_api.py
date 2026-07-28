import json
import urllib.request
import urllib.error
import urllib.parse

import xbmc

from resources.lib.constants import TMDB_KEY, TMDB_API, TMDB_IMG, USER_AGENT, GENRES_MOVIE, GENRES_TV, LOG_PREFIX
from resources.lib.kodi_utils import log


def _tmdb_fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log("TMDB fetch error: %s" % str(e), xbmc.LOGERROR)
        return None


def _tmdb_url(path, params=None):
    if not params:
        params = {}
    params_str = urllib.parse.urlencode(params)
    return "%s/%s?api_key=%s&language=en-US&%s" % (TMDB_API, path, TMDB_KEY, params_str)


def image_url(path, size="w500"):
    if not path:
        return ""
    return "%s/%s%s" % (TMDB_IMG, size, path)


def trending_movies(page=1):
    url = _tmdb_url("trending/movie/week", {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def trending_tv(page=1):
    url = _tmdb_url("trending/tv/week", {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def popular_movies(page=1):
    url = _tmdb_url("movie/popular", {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def popular_tv(page=1):
    url = _tmdb_url("tv/popular", {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def top_rated_movies(page=1):
    url = _tmdb_url("movie/top_rated", {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def top_rated_tv(page=1):
    url = _tmdb_url("tv/top_rated", {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def movies_by_genre(genre_id, page=1):
    url = _tmdb_url("discover/movie", {"with_genres": str(genre_id), "sort_by": "popularity.desc", "page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def tv_by_genre(genre_id, page=1):
    url = _tmdb_url("discover/tv", {"with_genres": str(genre_id), "sort_by": "popularity.desc", "page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def movie_detail(tmdb_id):
    url = _tmdb_url("movie/%s" % tmdb_id, {"append_to_response": "credits,videos,external_ids,recommendations,similar"})
    return _tmdb_fetch(url)


def tv_detail(tmdb_id):
    url = _tmdb_url("tv/%s" % tmdb_id, {"append_to_response": "credits,videos,external_ids,recommendations,similar"})
    return _tmdb_fetch(url)


def season_detail(tmdb_id, season_num):
    url = _tmdb_url("tv/%s/season/%s" % (tmdb_id, season_num))
    return _tmdb_fetch(url)


def episode_detail(tmdb_id, season_num, episode_num):
    url = _tmdb_url("tv/%s/season/%s/episode/%s" % (tmdb_id, season_num, episode_num),
                    {"append_to_response": "credits"})
    return _tmdb_fetch(url)


def search(query, page=1):
    url = _tmdb_url("search/multi", {"query": query, "page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        results = [r for r in resp.get("results", []) if r.get("media_type") in ("movie", "tv")]
        return results, resp.get("total_pages", 1)
    return [], 1


def get_external_ids(tmdb_id, media_type="movie"):
    url = _tmdb_url("%s/%s/external_ids" % (media_type, tmdb_id))
    return _tmdb_fetch(url)


def get_recommendations(tmdb_id, media_type="movie", page=1):
    url = _tmdb_url("%s/%s/recommendations" % (media_type, tmdb_id), {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def get_similar(tmdb_id, media_type="movie", page=1):
    url = _tmdb_url("%s/%s/similar" % (media_type, tmdb_id), {"page": str(page)})
    resp = _tmdb_fetch(url)
    if resp:
        return resp.get("results", []), resp.get("total_pages", 1)
    return [], 1


def person_detail(person_id):
    url = _tmdb_url("person/%s" % person_id)
    return _tmdb_fetch(url)


def person_movie_credits(person_id):
    url = _tmdb_url("person/%s/movie_credits" % person_id)
    return _tmdb_fetch(url)


def person_tv_credits(person_id):
    url = _tmdb_url("person/%s/tv_credits" % person_id)
    return _tmdb_fetch(url)

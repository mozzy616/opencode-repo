import sqlite3
import time
import os

import xbmcvfs

from resources.lib.kodi_utils import log, translate_path

DB_PATH = translate_path("special://profile/addon_data/plugin.video.rdflix/rd_cache.db")


def _get_db():
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS rd_cache ("
                 "info_hash TEXT PRIMARY KEY, cached INTEGER NOT NULL DEFAULT 1, "
                 "last_checked INTEGER NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_last_checked ON rd_cache(last_checked)")
    conn.execute("CREATE TABLE IF NOT EXISTS scraper_analytics ("
                 "scraper_name TEXT PRIMARY KEY, "
                 "success_count INTEGER DEFAULT 0, "
                 "fail_count INTEGER DEFAULT 0, "
                 "total_time_ms INTEGER DEFAULT 0, "
                 "last_used INTEGER DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS continue_watching ("
                 "imdb_id TEXT, tmdb_id TEXT, title TEXT, "
                 "season INTEGER, episode INTEGER, show_title TEXT, "
                 "progress_pct REAL, last_updated INTEGER, "
                 "PRIMARY KEY (imdb_id, season, episode))")
    conn.commit()
    return conn


def record_scraper_result(scraper_name, success, elapsed_ms):
    conn = None
    try:
        conn = _get_db()
        now = int(time.time())
        if success:
            conn.execute(
                "INSERT INTO scraper_analytics (scraper_name, success_count, fail_count, total_time_ms, last_used) "
                "VALUES (?, 1, 0, ?, ?) ON CONFLICT(scraper_name) DO UPDATE SET "
                "success_count = success_count + 1, total_time_ms = total_time_ms + ?, last_used = ?",
                (scraper_name, elapsed_ms, now, elapsed_ms, now))
        else:
            conn.execute(
                "INSERT INTO scraper_analytics (scraper_name, success_count, fail_count, total_time_ms, last_used) "
                "VALUES (?, 0, 1, 0, ?) ON CONFLICT(scraper_name) DO UPDATE SET "
                "fail_count = fail_count + 1, last_used = ?",
                (scraper_name, now, now))
        conn.commit()
    except Exception as e:
        log("Analytics record error: %s" % str(e))
    finally:
        if conn:
            conn.close()


def get_scraper_ranking():
    conn = None
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT scraper_name, success_count, fail_count, total_time_ms FROM scraper_analytics "
            "ORDER BY success_count DESC").fetchall()
        ranking = []
        for name, sc, fc, tt in rows:
            total_runs = sc + fc
            success_rate = (sc / total_runs * 100) if total_runs > 0 else 0
            avg_time = (tt / sc) if sc > 0 else 0
            ranking.append({
                "name": name,
                "success_count": sc,
                "fail_count": fc,
                "success_rate": success_rate,
                "avg_time_ms": avg_time,
            })
        return ranking
    except:
        return []
    finally:
        if conn:
            conn.close()


def update_continue_watching(imdb_id, tmdb_id, title, season, episode, show_title, progress_pct):
    conn = None
    try:
        conn = _get_db()
        now = int(time.time())
        conn.execute(
            "INSERT OR REPLACE INTO continue_watching (imdb_id, tmdb_id, title, season, episode, show_title, progress_pct, last_updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (imdb_id or "", tmdb_id or "", title, season, episode, show_title or "", progress_pct, now))
        conn.commit()
    except Exception as e:
        log("Continue watching update error: %s" % str(e))
    finally:
        if conn:
            conn.close()


def get_continue_watching(limit=20):
    conn = None
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT imdb_id, tmdb_id, title, season, episode, show_title, progress_pct FROM continue_watching "
            "ORDER BY last_updated DESC LIMIT ?", (limit,)).fetchall()
        results = []
        for imdb, tmdb, title, season, episode, show_title, pct in rows:
            results.append({
                "imdb_id": imdb,
                "tmdb_id": tmdb,
                "title": title,
                "season": season,
                "episode": episode,
                "show_title": show_title,
                "progress": pct,
            })
        return results
    except:
        return []
    finally:
        if conn:
            conn.close()

import sqlite3
import time
import os

import xbmcvfs

from resources.lib.kodi_utils import log, translate_path, get_addon_info

DB_PATH = translate_path("special://profile/addon_data/plugin.video.rdflix/rd_cache.db")
CACHE_TTL = 7 * 24 * 3600  # 7 days


def _ensure_dir():
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


def _get_db():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS rd_cache ("
                 "info_hash TEXT PRIMARY KEY, "
                 "cached INTEGER NOT NULL DEFAULT 1, "
                 "last_checked INTEGER NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_last_checked ON rd_cache(last_checked)")
    conn.commit()
    return conn


def get_cached_hashes(hashes):
    """Check which hashes are cached in the local SQLite database.
    Returns tuple: (cached_set, unknown_hashes_list)."""
    if not hashes:
        return set(), []

    hashes_lower = [h.lower()[:40] for h in hashes]
    conn = None

    try:
        conn = _get_db()
        now = int(time.time())
        cutoff = now - CACHE_TTL

        cursor = conn.execute(
            "SELECT info_hash FROM rd_cache WHERE info_hash IN (%s) AND cached=1 AND last_checked > ?"
            % ",".join("?" * len(hashes_lower)),
            hashes_lower + [cutoff]
        )
        cached = set(row[0] for row in cursor.fetchall())

        expired = set()
        cursor = conn.execute(
            "SELECT info_hash FROM rd_cache WHERE info_hash IN (%s) AND last_checked <= ?"
            % ",".join("?" * len(hashes_lower)),
            hashes_lower + [cutoff]
        )
        expired = set(row[0] for row in cursor.fetchall())

        if expired:
            conn.execute(
                "DELETE FROM rd_cache WHERE info_hash IN (%s)"
                % ",".join("?" * len(expired)),
                list(expired)
            )
            conn.commit()

        unknown = [h for i, h in enumerate(hashes) if hashes_lower[i] not in cached and hashes_lower[i] not in expired]

        log("RD cache DB: %d cached, %d unknown, %d expired"
            % (len(cached), len(unknown), len(expired)))
        return cached, unknown

    except Exception as e:
        log("RD cache DB read error: %s" % str(e))
        return set(), hashes
    finally:
        if conn:
            conn.close()


def set_cached_hashes(hashes, is_cached=True):
    """Save cache status for a list of hashes."""
    if not hashes:
        return

    conn = None
    try:
        conn = _get_db()
        now = int(time.time())
        rows = [(h.lower()[:40], 1 if is_cached else 0, now) for h in hashes]
        conn.executemany(
            "INSERT OR REPLACE INTO rd_cache (info_hash, cached, last_checked) VALUES (?, ?, ?)",
            rows
        )
        conn.commit()
        log("RD cache DB: saved %d hashes (cached=%s)" % (len(rows), is_cached))
    except Exception as e:
        log("RD cache DB write error: %s" % str(e))
    finally:
        if conn:
            conn.close()


def clear_cache():
    """Clear all cached entries."""
    conn = None
    try:
        conn = _get_db()
        conn.execute("DELETE FROM rd_cache")
        conn.commit()
        log("RD cache DB: cleared all entries")
    except Exception as e:
        log("RD cache DB clear error: %s" % str(e))
    finally:
        if conn:
            conn.close()

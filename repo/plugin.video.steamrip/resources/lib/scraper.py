import re
import hashlib
import subprocess
import os
import tempfile
import shutil
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus

try:
    import xbmc
    import xbmcvfs
except ImportError:
    class xbmc:
        LOGINFO = "info"
        LOGERROR = "error"
        @staticmethod
        def log(msg, level=None):
            print(msg)

BASE_URL = "https://steamrip.com"

CURL_EXE = None
for _path in [
    os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "System32\\curl.exe"),
    "curl.exe",
    "curl",
]:
    if shutil.which(_path):
        CURL_EXE = _path
        break

CACHE = {}

CATEGORIES = [
    ("Action", "action"),
    ("Adventure", "adventure"),
    ("Anime", "anime"),
    ("Building", "building"),
    ("First-person Shooter", "fps"),
    ("Horror", "horror"),
    ("Indie", "indie"),
    ("Multiplayer", "multiplayer"),
    ("Open World", "open-world"),
    ("Racing", "racing"),
    ("Role-Playing Game", "rpg"),
    ("Sci-fi", "sci-fi"),
    ("Shooting", "shooting"),
    ("Simulation", "simulation"),
    ("Sports", "sports"),
    ("Strategy", "strategy"),
    ("Survival", "survival"),
    ("Virtual Reality", "vr"),
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _get_url(url, params=None):
    cache_key = hashlib.md5((url + str(params)).encode("utf-8")).hexdigest()
    if cache_key in CACHE:
        return CACHE[cache_key]

    if params:
        from urllib.parse import urlencode
        full_url = "{}?{}".format(url, urlencode(params))
    else:
        full_url = url

    if not CURL_EXE:
        xbmc.log("SteamRIP: curl not found on system", xbmc.LOGERROR)
        return None

    try:
        tmpdir = tempfile.gettempdir()
        tmpfile = os.path.join(tmpdir, "steamrip_{}.html".format(cache_key))

        cmd = [
            CURL_EXE,
            "-sL",
            "--compressed",
            "-A", UA,
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "-H", "Accept-Language: en-US,en;q=0.9",
            "-H", "Referer: {}".format(BASE_URL + "/"),
            "-o", tmpfile,
            "-w", "%{http_code}",
            "--connect-timeout", "10",
            "--max-time", "30",
            full_url,
        ]

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            encoding="utf-8",
            errors="replace",
        )

        http_code = result.stdout.strip()

        if not http_code.isdigit() or http_code == "000":
            xbmc.log("SteamRIP: curl failed for {}: code={}".format(full_url, http_code), xbmc.LOGERROR)
            _cleanup_tmp(tmpfile)
            return None

        if http_code not in ("200", "301", "302"):
            xbmc.log("SteamRIP: HTTP {} for {}".format(http_code, full_url), xbmc.LOGERROR)
            _cleanup_tmp(tmpfile)
            return None

        content = ""
        if os.path.exists(tmpfile):
            with open(tmpfile, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            _cleanup_tmp(tmpfile)

        if not content:
            return None

        CACHE[cache_key] = content
        return content

    except Exception as e:
        xbmc.log("SteamRIP: curl error for {}: {}".format(full_url, str(e)), xbmc.LOGERROR)
        _cleanup_tmp(tmpfile)
        return None


def _cleanup_tmp(tmpfile):
    try:
        if os.path.exists(tmpfile):
            os.remove(tmpfile)
    except Exception:
        pass


def _make_soup(html):
    if html is None:
        return None
    return BeautifulSoup(html, "html.parser")


def _text(el, default=""):
    if el:
        return el.get_text(strip=True)
    return default


def _clean_title(raw_title):
    title = re.sub(r"\s*\([^)]*\)\s*$", "", raw_title)
    title = title.replace("&#038;", "&").replace("&amp;", "&").replace("&trade;", "")
    title = title.replace("&#8211;", "-").replace("&#8217;", "'").replace("&#8220;", '"')
    title = title.replace("&#8221;", '"')
    return title.strip()


def _extract_size(text):
    m = re.search(r"(\d+(?:\.\d+)?\s*(?:GB|MB|TB))", text, re.IGNORECASE)
    return m.group(1) if m else ""


def get_popular_games(page=1):
    url = BASE_URL if page == 1 else "{}/page/{}/".format(BASE_URL, page)
    return _parse_game_listing(url)


def get_top_games(page=1):
    url = "{}/top-games/".format(BASE_URL) if page == 1 else "{}/top-games/page/{}/".format(BASE_URL, page)
    return _parse_game_listing(url)


def get_recent_updates(page=1):
    url = "{}/updated-games/".format(BASE_URL) if page == 1 else "{}/updated-games/page/{}/".format(BASE_URL, page)
    return _parse_game_listing(url)


def get_category_games(category_slug, page=1):
    if page == 1:
        url = "{}/category/{}/".format(BASE_URL, category_slug)
    else:
        url = "{}/category/{}/page/{}/".format(BASE_URL, category_slug, page)
    return _parse_game_listing(url)


def get_all_games(page=1):
    if page == 1:
        url = "{}/games-list/".format(BASE_URL)
    else:
        url = "{}/games-list/page/{}/".format(BASE_URL, page)
    return _parse_game_listing(url)


def search_games(query, page=1):
    url = BASE_URL
    params = {"s": query}
    if page > 1:
        params["paged"] = page
    html = _get_url(url, params)
    return _parse_search_results(html)


def _parse_game_listing(url):
    html = _get_url(url)
    soup = _make_soup(html)
    if soup is None:
        return [], False

    games = []

    # Layout 1: Homepage / Top Games - uses article.post-item with img tags
    posts = soup.select(".post-item, article.tie_standard, .mag-box .post-item, li.post-item, .posts-items > li")
    if not posts:
        posts = soup.select("article")

    for post in posts:
        try:
            title_el = post.select_one("h2.post-title a, h3.post-title a, .post-title a, h2 a, h3 a")
            if not title_el:
                continue
            raw_title = _text(title_el)
            href = title_el.get("href", "")
            if "/free-download/" not in href and "-free-download/" not in href:
                continue
            game_url = urljoin(BASE_URL, href)
            title = _clean_title(raw_title)
            thumb_el = post.select_one("img")
            thumb = thumb_el.get("src", thumb_el.get("data-src", "")) if thumb_el else ""
            if thumb and not thumb.startswith("http"):
                thumb = urljoin(BASE_URL, thumb)
            meta_el = post.select_one(".post-meta, .entry-meta, .tie-alignleft")
            meta_text = _text(meta_el) if meta_el else ""
            year_match = re.search(r"(19|20)\d{2}", meta_text)
            year = year_match.group(0) if year_match else ""
            size = _extract_size(_text(post))
            cat_els = post.select(".post-cat, .entry-category a, .post-cats a")
            categories = [_text(c) for c in cat_els if _text(c)]
            games.append({
                "title": title, "url": game_url, "thumb": thumb,
                "year": year, "size": size, "categories": categories,
            })
        except Exception:
            continue

    # Layout 2: Category pages - uses .post-element with data-back images
    if not games:
        posts = soup.select(".post-element, .container-wrapper.post-element")
        for post in posts:
            try:
                link_el = post.select_one("a.all-over-thumb-link")
                if not link_el:
                    continue
                href = link_el.get("href", "")
                if "/free-download/" not in href and "-free-download/" not in href:
                    continue
                game_url = urljoin(BASE_URL, href)

                title_el = post.select_one("h2.thumb-title a")
                if not title_el:
                    title_el = link_el.select_one(".screen-reader-text")
                    if not title_el:
                        continue
                title = _clean_title(_text(title_el))

                thumb = ""
                slide_el = post.select_one(".slide")
                if slide_el:
                    thumb = slide_el.get("data-back", "")
                    if thumb and not thumb.startswith("http"):
                        thumb = urljoin(BASE_URL, thumb)

                meta_el = post.select_one("span.game-meta-line")
                meta_text = _text(meta_el)
                year = ""
                size = ""
                if meta_text:
                    parts = meta_text.split("|")
                    if len(parts) >= 1:
                        year = parts[0].strip()
                    if len(parts) >= 2:
                        size = parts[1].strip()
                    if year and not re.match(r"^(19|20)\d{2}$", year):
                        size = year
                        year = ""

                games.append({
                    "title": title, "url": game_url, "thumb": thumb,
                    "year": year, "size": size, "categories": [],
                })
            except Exception:
                continue

    # Layout 2b: Container-wrapper posts on homepage/top-games fallback
    if not games:
        container_posts = soup.select(".container-wrapper .post-item, .posts-items li, .mag-box-container li")
        for post in container_posts:
            try:
                title_el = post.select_one("h2.post-title a, h3.post-title a, .post-title a, h2 a, h3 a")
                if not title_el:
                    continue
                raw_title = _text(title_el)
                href = title_el.get("href", "")
                if "/free-download/" not in href and "-free-download/" not in href:
                    continue
                game_url = urljoin(BASE_URL, href)
                title = _clean_title(raw_title)
                thumb_el = post.select_one("img")
                thumb = thumb_el.get("src", thumb_el.get("data-src", "")) if thumb_el else ""
                if thumb and not thumb.startswith("http"):
                    thumb = urljoin(BASE_URL, thumb)
                meta_el = post.select_one(".post-meta, .entry-meta")
                meta_text = _text(meta_el) if meta_el else ""
                year_match = re.search(r"(19|20)\d{2}", meta_text)
                year = year_match.group(0) if year_match else ""
                size = _extract_size(_text(post))
                cat_els = post.select(".post-cat, .entry-category a")
                categories = [_text(c) for c in cat_els if _text(c)]
                games.append({
                    "title": title, "url": game_url, "thumb": thumb,
                    "year": year, "size": size, "categories": categories,
                })
            except Exception:
                continue

    # Layout 3: Updated Games - uses .updated-list-item a.updated-card
    if not games:
        posts = soup.select(".updated-list-item")
        for post in posts:
            try:
                link_el = post.select_one("a.updated-card")
                if not link_el:
                    continue
                href = link_el.get("href", "")
                if "/free-download/" not in href and "-free-download/" not in href:
                    continue
                game_url = urljoin(BASE_URL, href)

                title_el = post.select_one(".updated-card-title")
                title = _clean_title(_text(title_el))

                version_el = post.select_one(".updated-list-build")
                version = _text(version_el)

                games.append({
                    "title": title, "url": game_url, "thumb": "",
                    "year": "", "size": version or "",
                    "categories": [],
                })
            except Exception:
                continue

    # Layout 4: Games List A-Z - uses .az-list-item a
    if not games:
        posts = soup.select(".az-list-item")
        for post in posts:
            try:
                link_el = post.select_one("a")
                if not link_el:
                    continue
                href = link_el.get("href", "")
                if "/free-download/" not in href and "-free-download/" not in href:
                    continue
                game_url = urljoin(BASE_URL, href)
                title = _clean_title(_text(link_el))

                games.append({
                    "title": title, "url": game_url, "thumb": "",
                    "year": "", "size": "",
                    "categories": [],
                })
            except Exception:
                continue

    next_el = soup.select_one("a.next.page-numbers, .pages-nav .next, a.nextpostslink")
    has_next = bool(next_el)

    return games, has_next


def _parse_search_results(html):
    soup = _make_soup(html)
    if soup is None:
        return [], False

    games = []

    # Try Layout 1: Search blocks (similar to homepage articles)
    posts = soup.select(".search-block .post-item, .search-in-results .post-item, article.tie_standard")
    if not posts:
        posts = soup.select(".post-listing .post-item, .posts-container .post-item")
    if not posts:
        posts = soup.select("article.post-element")
    if not posts:
        posts = soup.select(".post-element")

    for post in posts:
        try:
            # Homepage article layout
            title_el = post.select_one("h2 a, h3 a, .post-title a, h2.post-title a, h2.thumb-title a")
            if not title_el:
                continue
            raw_title = _text(title_el)
            href = title_el.get("href", "")
            if "/free-download/" not in href and "-free-download/" not in href:
                continue
            game_url = urljoin(BASE_URL, href)
            title = _clean_title(raw_title)
            thumb_el = post.select_one("img")
            thumb = thumb_el.get("src", thumb_el.get("data-src", "")) if thumb_el else ""
            if not thumb:
                slide_el = post.select_one(".slide")
                if slide_el:
                    thumb = slide_el.get("data-back", "")
            if thumb and not thumb.startswith("http"):
                thumb = urljoin(BASE_URL, thumb)
            meta_text = _text(post)
            year_match = re.search(r"(19|20)\d{2}", meta_text)
            year = year_match.group(0) if year_match else ""
            size = _extract_size(meta_text)
            games.append({
                "title": title, "url": game_url, "thumb": thumb,
                "year": year, "size": size, "categories": [],
            })
        except Exception:
            continue

    next_el = soup.select_one("a.next.page-numbers, .pages-nav .next, .pagination .next")
    has_next = bool(next_el)

    return games, has_next


def get_game_details(game_url):
    html = _get_url(game_url)
    soup = _make_soup(html)
    if soup is None:
        return {}

    try:
        main_title_el = soup.select_one("h1.entry-title, h1.post-title, .post-title, h1.name")
        main_title = _text(main_title_el)

        entry = soup.select_one(".entry-content, .post-content, .post-entry, article")

        screenshots = []
        if entry:
            screenshot_imgs = entry.select(".screenshot img, .ss img, .wp-caption img, .aligncenter img, .alignnone img, p img")
            for img in screenshot_imgs:
                src = img.get("src", img.get("data-src", ""))
                if src and not src.startswith("http"):
                    src = urljoin(BASE_URL, src)
                if src and ("steamrip" in src or "wp-content" in src or "steam" in src.lower()):
                    screenshots.append(src)
            if not screenshots:
                all_imgs = entry.select("img")
                for img in all_imgs:
                    src = img.get("src", img.get("data-src", ""))
                    if src and not src.startswith("http"):
                        src = urljoin(BASE_URL, src)
                    if src and "icon" not in src.lower() and "avatar" not in src.lower() and "logo" not in src.lower():
                        screenshots.append(src)

        info_divs = soup.select(".game-info, .post-info, .entry-info, .game-meta, .su-list li, .su-row .su-column-size-1-2, .game-details")
        game_info_text = ""
        for div in info_divs:
            game_info_text += _text(div) + "\n"

        description = ""
        if entry:
            desc_ps = entry.select("p")
            for p in desc_ps:
                ptext = _text(p)
                if ptext and len(ptext) > 100:
                    description += ptext + "\n\n"
            if not description:
                description = _text(entry)[:1000]

        genre, developer, platform, game_size, version, released_by = "", "", "", "", "", ""

        for div in info_divs:
            dtext = _text(div)
            m = re.search(r"Genre:\s*(.+)", dtext, re.IGNORECASE)
            if m: genre = m.group(1).strip()
            m = re.search(r"Developer:\s*(.+)", dtext, re.IGNORECASE)
            if m: developer = m.group(1).strip()
            m = re.search(r"Platform:\s*(.+)", dtext, re.IGNORECASE)
            if m: platform = m.group(1).strip()
            m = re.search(r"Size:\s*(.+)", dtext, re.IGNORECASE)
            if m: game_size = m.group(1).strip()
            m = re.search(r"Version:\s*(.+)", dtext, re.IGNORECASE)
            if m: version = m.group(1).strip()
            m = re.search(r"Released By:\s*(.+)", dtext, re.IGNORECASE)
            if m: released_by = m.group(1).strip()

        if not game_size:
            game_size = _extract_size(game_info_text)

        download_links = []
        if entry:
            all_links = entry.select("a")
            dl_keywords = ["download", "bzzhr", "gofile", "1fichier", "mediafire", "mega", "qiwi", "pixeldrain", "buzzheavier", "buzz", "upload", "zip", "rar"]
            for a in all_links:
                href = a.get("href", "")
                text = _text(a).lower()
                if any(kw in text for kw in dl_keywords) or any(kw in href.lower() for kw in dl_keywords):
                    download_links.append({
                        "label": _text(a) or "Download",
                        "url": urljoin(BASE_URL, href) if href.startswith("/") else href,
                    })
            if not download_links:
                for a in all_links:
                    href = a.get("href", "")
                    if href and "steamrip.com" not in href and not href.startswith("#"):
                        txt = _text(a)
                        if txt and len(txt) > 2:
                            download_links.append({
                                "label": txt,
                                "url": urljoin(BASE_URL, href) if href.startswith("/") else href,
                            })

        cat_els = soup.select(".post-cat a, .entry-categories a, .post-categories a, .entry-category a")
        categories = [_text(c) for c in cat_els if _text(c)]

        fanart = ""
        if screenshots:
            fanart = screenshots[0]
        else:
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img:
                fanart = og_img.get("content", "")

        poster_el = soup.select_one(".featured-area img, .post-thumbnail img, .wp-post-image")
        poster = poster_el.get("src", poster_el.get("data-src", "")) if poster_el else fanart

        sys_req = ""
        sys_req_el = soup.select_one(".system-requirements, .su-spoiler-content, .requirements, .system-info")
        if sys_req_el:
            sys_req = _text(sys_req_el)

        if not sys_req and entry:
            sys_req_match = re.search(
                r"(OS[:\s].+?)(?=GAME\s*INFO|SCREENSHOTS|Download|$)",
                _text(entry), re.DOTALL | re.IGNORECASE,
            )
            if sys_req_match:
                sys_req = sys_req_match.group(1).strip()

        return {
            "title": _clean_title(main_title),
            "description": description.strip(),
            "screenshots": screenshots,
            "fanart": fanart,
            "poster": poster,
            "genre": genre,
            "developer": developer,
            "platform": platform or "PC",
            "size": game_size,
            "version": version,
            "released_by": released_by,
            "categories": categories,
            "download_links": download_links,
            "system_requirements": sys_req,
            "url": game_url,
        }

    except Exception as e:
        xbmc.log("SteamRIP: Error parsing game details: {}".format(str(e)), xbmc.LOGERROR)
        return {}

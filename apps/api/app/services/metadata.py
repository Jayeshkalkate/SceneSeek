"""Optional, free public metadata adapters. These never identify a title from a frame."""
from __future__ import annotations
import logging
import re
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(8.0, connect=3.0)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def search_anilist(title: str) -> dict | None:
    query = "query ($search: String) { Media(search: $search, type: ANIME) { id title { romaji english native } description(asHtml: false) startDate { year } genres siteUrl coverImage { large } averageScore } }"
    try:
        response = httpx.post("https://graphql.anilist.co", json={"query": query, "variables": {"search": _clean(title)}}, timeout=TIMEOUT)
        response.raise_for_status()
        media = (response.json().get("data") or {}).get("Media")
        if not media:
            return None
        names = media.get("title") or {}
        synopsis = re.sub(r"<[^>]+>", "", media.get("description") or "")[:1500]
        return {"title": names.get("english") or names.get("romaji") or title,
                "original_title": names.get("native"), "year": (media.get("startDate") or {}).get("year"),
                "synopsis": synopsis, "genres": media.get("genres") or [],
                "poster_url": (media.get("coverImage") or {}).get("large"),
                "rating": {"value": media.get("averageScore"), "source": "AniList (/100)"},
                "external_url": media.get("siteUrl"), "provider": "AniList"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        logger.info("AniList metadata unavailable for title %s", title)
        return None


def search_jikan(title: str) -> dict | None:
    try:
        response = httpx.get("https://api.jikan.moe/v4/anime", params={"q": _clean(title), "limit": 1}, timeout=TIMEOUT)
        response.raise_for_status()
        items = response.json().get("data") or []
        if not items:
            return None
        item = items[0]
        images = item.get("images") or {}
        poster = ((images.get("jpg") or {}).get("large_image_url") or (images.get("jpg") or {}).get("image_url"))
        return {"title": item.get("title_english") or item.get("title") or title,
                "original_title": item.get("title_japanese"), "year": item.get("year"),
                "synopsis": (item.get("synopsis") or "")[:1500],
                "genres": [g.get("name") for g in item.get("genres", []) if g.get("name")],
                "poster_url": poster, "rating": {"value": item.get("score"), "source": "MyAnimeList"},
                "external_url": item.get("url"), "provider": "Jikan / MyAnimeList"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        logger.info("Jikan metadata unavailable for title %s", title)
        return None


def search_tvmaze(title: str) -> dict | None:
    try:
        response = httpx.get("https://api.tvmaze.com/search/shows", params={"q": _clean(title)}, timeout=TIMEOUT)
        response.raise_for_status()
        items = response.json()
        if not items:
            return None
        item = items[0].get("show") or {}
        image = item.get("image") or {}
        premiered = item.get("premiered") or ""
        return {"title": item.get("name") or title, "year": int(premiered[:4]) if premiered[:4].isdigit() else None,
                "synopsis": re.sub(r"<[^>]+>", "", item.get("summary") or "")[:1500],
                "genres": item.get("genres") or [], "poster_url": image.get("medium") or image.get("original"),
                "rating": {"value": (item.get("rating") or {}).get("average"), "source": "TVmaze"},
                "external_url": item.get("officialSite") or item.get("url"), "provider": "TVmaze"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        logger.info("TVmaze metadata unavailable for title %s", title)
        return None


def search_omdb(title: str) -> dict | None:
    api_key = get_settings().omdb_api_key.strip()
    if not api_key:
        return None
    try:
        response = httpx.get("https://www.omdbapi.com/", params={"apikey": api_key, "t": _clean(title)}, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("Response") != "True":
            return None
        year = (data.get("Year") or "")[:4]
        rating = next((r.get("Value") for r in data.get("Ratings", []) if r.get("Source") == "Internet Movie Database"), None)
        return {"title": data.get("Title") or title, "year": int(year) if year.isdigit() else None,
                "synopsis": (data.get("Plot") or "")[:1500],
                "genres": [x.strip() for x in (data.get("Genre") or "").split(",") if x.strip()],
                "poster_url": data.get("Poster") if data.get("Poster") != "N/A" else None,
                "rating": {"value": rating, "source": "IMDb via OMDb"},
                "external_url": f"https://www.imdb.com/title/{data.get('imdbID')}/" if data.get("imdbID") else None,
                "provider": "OMDb"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        logger.info("OMDb metadata unavailable for title %s", title)
        return None


def enrich_metadata(title: dict) -> dict:
    """Stale-safe optional enrichment; never fails an identification job."""
    if title.get("synopsis") and (title.get("poster_url") or title.get("external_url")):
        return title
    kind = title.get("kind", "unknown")
    providers = [search_anilist, search_jikan] if kind == "anime" else [search_tvmaze] if kind == "series" else [search_omdb]
    for provider in providers:
        found = provider(title.get("title", ""))
        if found:
            merged = dict(found)
            for key, value in title.items():
                if key == "rating" and isinstance(value, dict):
                    if value.get("value") is not None:
                        merged[key] = value
                elif value not in (None, "", []):
                    merged[key] = value
            # Provider metadata and local overrides are returned together, but retain the stable index ID.
            merged["title_id"] = title.get("title_id", title.get("id"))
            return merged
    return title


def _anilist_search_many(query: str, limit: int = 5) -> list[dict]:
    gql = ("query ($s: String, $n: Int) { Page(perPage: $n) { media(search: $s, type: ANIME, isAdult: false, sort: SEARCH_MATCH) "
           "{ id title { romaji english native } description(asHtml: false) startDate { year } genres siteUrl coverImage { large } averageScore } } }")
    try:
        r = httpx.post("https://graphql.anilist.co", json={"query": gql, "variables": {"s": query, "n": limit}}, timeout=TIMEOUT)
        r.raise_for_status()
        items = ((r.json().get("data") or {}).get("Page") or {}).get("media") or []
    except (httpx.HTTPError, ValueError, TypeError):
        return []
    out = []
    for m in items:
        names = m.get("title") or {}
        out.append({"title_id": f"anilist-{m['id']}", "title": names.get("english") or names.get("romaji") or "Untitled",
                    "original_title": names.get("native"), "kind": "anime", "year": (m.get("startDate") or {}).get("year"),
                    "synopsis": re.sub(r"<[^>]+>", "", m.get("description") or "")[:600], "genres": m.get("genres") or [],
                    "poster_url": (m.get("coverImage") or {}).get("large"),
                    "rating": {"value": m.get("averageScore"), "source": "AniList (/100)"},
                    "external_url": m.get("siteUrl"), "provider": "AniList"})
    return out


def _tvmaze_search_many(query: str, limit: int = 5) -> list[dict]:
    try:
        r = httpx.get("https://api.tvmaze.com/search/shows", params={"q": _clean(query)}, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json()[:limit]
    except (httpx.HTTPError, ValueError, TypeError):
        return []
    out = []
    for row in items:
        show = row.get("show") or {}
        prem = show.get("premiered") or ""
        out.append({"title_id": f"tvmaze-{show.get('id')}", "title": show.get("name") or "Untitled", "kind": "series",
                    "year": int(prem[:4]) if prem[:4].isdigit() else None,
                    "synopsis": re.sub(r"<[^>]+>", "", show.get("summary") or "")[:600], "genres": show.get("genres") or [],
                    "poster_url": (show.get("image") or {}).get("medium"),
                    "rating": {"value": (show.get("rating") or {}).get("average"), "source": "TVmaze"},
                    "external_url": show.get("url"), "provider": "TVmaze"})
    return out


def _itunes_movies(query: str, limit: int = 5) -> list[dict]:
    """Free, key-less movie search (Apple iTunes Search API)."""
    try:
        r = httpx.get("https://itunes.apple.com/search", params={"term": _clean(query), "media": "movie", "entity": "movie", "limit": limit}, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json().get("results") or []
    except (httpx.HTTPError, ValueError, TypeError):
        return []
    out = []
    for m in items:
        rel = (m.get("releaseDate") or "")[:4]
        art = m.get("artworkUrl100")
        out.append({"title_id": f"itunes-{m.get('trackId')}", "title": m.get("trackName") or "Untitled", "kind": "movie",
                    "year": int(rel) if rel.isdigit() else None, "synopsis": (m.get("longDescription") or m.get("shortDescription") or "")[:600],
                    "genres": [m["primaryGenreName"]] if m.get("primaryGenreName") else [],
                    "poster_url": art.replace("100x100", "400x600") if art else None,
                    "rating": {"value": m.get("contentAdvisoryRating"), "source": "Content rating"},
                    "external_url": m.get("trackViewUrl"), "provider": "Apple iTunes Search"})
    return out


def search_titles(query: str) -> list[dict]:
    """Text search across free public sources. This is title lookup, not scene recognition."""
    query = _clean(query)[:120]
    if len(query) < 2:
        return []
    results = _itunes_movies(query) + _tvmaze_search_many(query) + _anilist_search_many(query)
    omdb = search_omdb(query)
    if omdb:
        omdb.setdefault("title_id", f"omdb-{_clean(omdb['title']).lower().replace(' ', '-')}")
        omdb["kind"] = "movie"
        results.append(omdb)
    seen, unique = set(), []
    for item in results:
        key = (re.sub(r"[^a-z0-9]", "", item["title"].lower()), item.get("year"))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:12]


def anilist_by_id(anilist_id: int) -> dict | None:
    gql = ("query ($id: Int) { Media(id: $id, type: ANIME) { id title { romaji english native } description(asHtml: false) "
           "startDate { year } genres siteUrl coverImage { large } averageScore } }")
    try:
        r = httpx.post("https://graphql.anilist.co", json={"query": gql, "variables": {"id": anilist_id}}, timeout=TIMEOUT)
        r.raise_for_status()
        m = (r.json().get("data") or {}).get("Media")
    except (httpx.HTTPError, ValueError, TypeError):
        return None
    if not m:
        return None
    names = m.get("title") or {}
    return {"title": names.get("english") or names.get("romaji") or "Untitled", "original_title": names.get("native"),
            "year": (m.get("startDate") or {}).get("year"), "synopsis": re.sub(r"<[^>]+>", "", m.get("description") or "")[:1500],
            "genres": m.get("genres") or [], "poster_url": (m.get("coverImage") or {}).get("large"),
            "rating": {"value": m.get("averageScore"), "source": "AniList (/100)"}, "external_url": m.get("siteUrl"),
            "provider": "AniList"}

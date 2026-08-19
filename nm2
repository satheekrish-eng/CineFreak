"""
MegaSource - Netmirror Scraper
================================
Scraper para o addon MegaSource.
"""

import base64
import requests
import urllib.parse
import urllib3

# SSL Warnings ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "Netmirror Scraper"
VERSION = "1.0.0"
DESCRIPTION = "Netmirror (NewTV) API Scraper for Netflix, Prime, Hotstar & Disney"

TMDB_API_KEY = "307b7b8ef035c6aa336900aef4e203bd"

PLATFORM_MAP = {
    "netflix": {"ott": "nf"},
    "primevideo": {"ott": "pv"},
    "hotstar": {"ott": "hs"},
    "disney": {"ott": "hs"},
}

NEW_TV_BASE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Requested-With": "NetmirrorNewTV v1.0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0 /OS.GatuNewTV v1.0",
    "Accept": "application/json, text/plain, */*",
}

NEW_TV_DOMAINS = [
    "aHR0cHM6Ly9tb2JpbGVkZXRlY3RzLmNvbQ==", "aHR0cHM6Ly9tb2JpbGVkZXR0LmFwcA==",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0LmFydA==", "aHR0cHM6Ly9tb2JpZGV0ZWN0LmNj",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0LmNsaWNr", "aHR0cHM6Ly9tb2JpZGV0ZWN0Lmluaw==",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0LmxpdmU=", "aHR0cHM6Ly9tb2JpZGV0ZWN0LnBybw==",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0LnNob3A=", "aHR0cHM6Ly9tb2JpZGV0ZWN0LnNpdGU=",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0LnNwYWNl", "aHR0cHM6Ly9tb2JpZGV0ZWN0LnN0b3Jl",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0LnZpcA==", "aHR0cHM6Ly9tb2JpZGV0ZWN0Lndpa2k=",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0Lnh5eg==", "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5hcnQ=",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5jYw==", "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5pbmZv",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5pbks=", "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5saXZl",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5wcm8=", "aHR0cHM6Ly9tb2JpZGV0ZWN0cy5zdG9yZQ==",
    "aHR0cHM6Ly9tb2JpZGV0ZWN0cy50b3A=", "aHR0cHM6Ly9tb2JpZGV0ZWN0cy54eXo=",
]

resolved_api_url = ""

def build_new_tv_headers(ott, extra=None):
    headers = NEW_TV_BASE_HEADERS.copy()
    headers["Ott"] = ott
    if extra:
        headers.update(extra)
    return headers

def meets_quality_filter(quality):
    if quality == "Auto":
        return True
    try:
        num = int(str(quality).replace('p', ''))
        return num >= 720
    except ValueError:
        return False

def resolve_api_url():
    global resolved_api_url
    if resolved_api_url:
        return resolved_api_url
        
    for encoded in NEW_TV_DOMAINS:
        base = base64.b64decode(encoded).decode('utf-8').rstrip('/')
        try:
            headers = NEW_TV_BASE_HEADERS.copy()
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            response = requests.get(f"{base}/checknewtv.php", headers=headers, verify=False, timeout=5)
            if response.status_code == 200:
                data = response.json()
                token_hash = data.get("token_hash")
                if token_hash:
                    resolved_api_url = base64.b64decode(token_hash).decode('utf-8').rstrip('/')
                    return resolved_api_url
        except Exception:
            continue
    return None

def fetch_from_netflix_direct(tmdb_id, media_type, season, episode, title):
    try:
        if media_type == "series":
            api_url = f"https://net77.cc/api/embed-tmdb/{tmdb_id}?type=tv&s={season}&e={episode}"
        else:
            api_url = f"https://net77.cc/api/embed-tmdb/{tmdb_id}"

        response = requests.get(api_url, headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://net77.cc/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        }, verify=False, timeout=10)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        if data.get("ok") is not True:
            return None

        playback_headers = {
            "Referer": "https://videodownloader.site/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        }

        streams = []
        if data.get("streams") and len(data["streams"]) > 0:
            for stream in data["streams"]:
                quality = f"{stream.get('resolution')}p"
                if meets_quality_filter(quality):
                    streams.append({
                        "name": f"Netmirror - {quality}",
                        "title": title,
                        "url": stream.get("url"),
                        "behaviorHints": {
                            "notWebReady": True,
                            "proxyHeaders": {"request": playback_headers}
                        }
                    })
        elif data.get("mp4"):
            streams.append({
                "name": "Netmirror - Auto",
                "title": title,
                "url": data.get("mp4"),
                "behaviorHints": {
                    "notWebReady": True,
                    "proxyHeaders": {"request": playback_headers}
                }
            })
        return streams
    except Exception:
        return None

def fetch_episodes_page(content_id, season_id, page, season_number, platform, api_base):
    episodes = []
    pg = page
    headers = build_new_tv_headers(platform["ott"])
    
    while True:
        url = f"{api_base}/newtv/episodes.php?id={season_id}&page={pg}"
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=10)
            data = resp.json()
            
            if data.get("episodes"):
                for ep in data["episodes"]:
                    if ep is None: continue
                    ep_num = int(ep["ep"]) if ep.get("ep") else (int(ep["epNum"].replace("E", "")) if ep.get("epNum") else None)
                    s_num = season_number if season_number else (int(ep["sNum"].replace("S", "")) if ep.get("sNum") else None)
                    episodes.append({"id": ep.get("id"), "s": s_num, "ep": ep_num})
                    
            if data.get("nextPageShow") != 1:
                break
            pg += 1
        except Exception:
            break
    return episodes

def get_all_episodes(content_id, post_data, platform, api_base):
    episodes = []
    
    seasons = post_data.get("season", [])
    selected_season_idx = -1
    for idx, s in enumerate(seasons):
        if s.get("selected") is True:
            selected_season_idx = idx
            break
            
    selected_season_id = seasons[selected_season_idx].get("id") if selected_season_idx >= 0 else post_data.get("nextPageSeason")
    selected_season_number = selected_season_idx + 1 if selected_season_idx >= 0 else None

    if post_data.get("episodes"):
        for ep in post_data["episodes"]:
            if ep is None: continue
            ep_num = int(ep["ep"]) if ep.get("ep") else (int(ep["epNum"].replace("E", "")) if ep.get("epNum") else None)
            s_num = selected_season_number if selected_season_number else (int(ep["sNum"].replace("S", "")) if ep.get("sNum") else None)
            episodes.append({"id": ep.get("id"), "s": s_num, "ep": ep_num})

    if post_data.get("nextPageShow") == 1 and selected_season_id:
        more = fetch_episodes_page(content_id, selected_season_id, 2, selected_season_number, platform, api_base)
        episodes.extend(more)

    for index, season in enumerate(seasons):
        if season.get("id") != selected_season_id and season.get("id"):
            more = fetch_episodes_page(content_id, season["id"], 1, index + 1, platform, api_base)
            episodes.extend(more)

    return episodes

def fetch_from_platform(platform_key, title, media_type, season, episode):
    platform = PLATFORM_MAP.get(platform_key)
    api_base = resolve_api_url()
    
    if not api_base or not platform:
        return None

    try:
        search_url = f"{api_base}/newtv/search.php?s={urllib.parse.quote(title)}"
        search_resp = requests.get(search_url, headers=build_new_tv_headers(platform["ott"]), verify=False, timeout=10)
        search_data = search_resp.json()
        
        if not search_data.get("searchResult"):
            return None

        content_id = search_data["searchResult"][0].get("id")

        post_url = f"{api_base}/newtv/post.php?id={content_id}"
        post_headers = build_new_tv_headers(platform["ott"], {"Lastep": "", "Usertoken": ""})
        post_resp = requests.get(post_url, headers=post_headers, verify=False, timeout=10)
        post_data = post_resp.json()

        target_id = content_id
        if media_type == "series":
            episodes = get_all_episodes(content_id, post_data, platform, api_base)
            target_ep = next((ep for ep in episodes if ep and ep.get("s") == season and ep.get("ep") == episode), None)
            if target_ep:
                target_id = target_ep["id"]
            else:
                return None
        else:
            is_series = post_data.get("type") == "t" or len([e for e in post_data.get("episodes", []) if e is not None]) > 0
            if is_series: return None
            target_id = post_data.get("main_id") or content_id

        player_url = f"{api_base}/newtv/player.php?id={target_id}"
        player_headers = build_new_tv_headers(platform["ott"], {"Usertoken": ""})
        player_resp = requests.get(player_url, headers=player_headers, verify=False, timeout=10)
        response = player_resp.json()

        if response.get("status") == "ok" and response.get("video_link"):
            return [{
                "name": f"Netmirror - {platform_key.capitalize()}",
                "title": title,
                "url": response["video_link"],
                "behaviorHints": {
                    "notWebReady": True,
                    "proxyHeaders": {"request": {"Referer": response.get("referer") or api_base}}
                }
            }]
    except Exception:
        pass
    
    return None

def get_tmdb_id(imdb_id, media_type):
    try:
        url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
        r = requests.get(url, timeout=10).json()
        if media_type == 'movie' and r.get('movie_results'):
            return r['movie_results'][0]['id']
        if media_type == 'series' and r.get('tv_results'):
            return r['tv_results'][0]['id']
    except Exception:
        pass
    return None

def get_streams(media_type, media_id, config=None):
    if ":" in media_id:
        parts = media_id.split(":")
        imdb_id = parts[0]
        season = int(parts[1]) if len(parts) > 1 else None
        episode = int(parts[2]) if len(parts) > 2 else None
        mt = "series"
    else:
        imdb_id = media_id
        season = None
        episode = None
        mt = "movie"

    if mt == "series" and (season is None or episode is None):
        return []

    tmdb_id = get_tmdb_id(imdb_id, mt)
    if not tmdb_id:
        return []

    try:
        tmdb_type = "tv" if mt == "series" else "movie"
        tmdb_req = requests.get(f"https://api.themoviedb.org/3/{tmdb_type}/{tmdb_id}?api_key={TMDB_API_KEY}", timeout=10)
        tmdb_data = tmdb_req.json()
        title = tmdb_data.get("name") if mt == "series" else tmdb_data.get("title")
        
        if not title: 
            return []

        platforms = ["netflix", "primevideo", "hotstar", "disney"]
        for p in platforms:
            try:
                streams = []
                if p == "netflix":
                    streams = fetch_from_netflix_direct(tmdb_id, mt, season, episode, title)
                if not streams or len(streams) == 0:
                    streams = fetch_from_platform(p, title, mt, season, episode)
                
                if streams and len(streams) > 0:
                    return streams
            except Exception:
                continue
                
    except Exception:
        pass

    return []

"""
MegaSource - NetMirror Scraper
================================
Scraper para o addon MegaSource. (Converted from Nuvio Script)
"""

import requests
import urllib.parse
import urllib3
import time
import re

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "NetMirror Scraper"
VERSION = "1.0.0"
DESCRIPTION = "NetMirror API Streamer (Netflix, Prime, Disney)"

TMDB_API_KEY = "439c478a771f35c05022f9feabcca01c"

# ബ്രോ പറഞ്ഞതുപോലെ പുതിയ ഡൊമെയ്ൻ (net77.cc) സെറ്റ് ചെയ്തിരിക്കുന്നു
NETMIRROR_BASE = "https://net77.cc"

BASE_HEADERS = {
    'X-Requested-With': 'XMLHttpRequest',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive'
}

global_cookie = ""
cookie_timestamp = 0
COOKIE_EXPIRY = 54000  # 15 മണിക്കൂർ

def get_unix_time():
    return int(time.time())

def bypass(session):
    global global_cookie, cookie_timestamp
    now = get_unix_time()
    
    if global_cookie and cookie_timestamp and (now - cookie_timestamp) < COOKIE_EXPIRY:
        return global_cookie
        
    for _ in range(5):
        try:
            res = session.post(f"{NETMIRROR_BASE}/tv/p.php", headers=BASE_HEADERS, verify=False, timeout=10)
            if 't_hash_t' in session.cookies:
                extracted = session.cookies.get('t_hash_t')
                if '"r":"n"' in res.text:
                    global_cookie = extracted
                    cookie_timestamp = now
                    return global_cookie
        except Exception:
            pass
        time.sleep(1)
    return None

def calculate_similarity(str1, str2):
    s1 = str1.lower().strip()
    s2 = str2.lower().strip()
    if s1 == s2: return 1.0
    
    words1 = [w for w in re.split(r'\s+', s1) if w]
    words2 = [w for w in re.split(r'\s+', s2) if w]
    
    if len(words2) <= len(words1) and len(words1) > 0:
        exact_matches = sum(1 for w in words2 if w in words1)
        if exact_matches == len(words2):
            return 0.95 * (exact_matches / len(words1))
            
    if s1.startswith(s2): 
        return 0.9
    return 0

def search_content(session, query, platform):
    ott_map = {'netflix': 'nf', 'primevideo': 'pv', 'disney': 'hs'}
    ott = ott_map.get(platform, 'nf')
    
    cookie = bypass(session)
    if not cookie: 
        return []
    
    session.cookies.update({
        't_hash_t': cookie,
        'user_token': '233123f803cf02184bf6c67e149cdd50',
        'hd': 'on',
        'ott': ott
    })
    
    endpoints = {
        'netflix': f"{NETMIRROR_BASE}/search.php",
        'primevideo': f"{NETMIRROR_BASE}/pv/search.php",
        'disney': f"{NETMIRROR_BASE}/mobile/hs/search.php"
    }
    url = endpoints.get(platform, endpoints['netflix'])
    
    headers = BASE_HEADERS.copy()
    headers['Referer'] = f"{NETMIRROR_BASE}/tv/home"
    
    try:
        res = session.get(f"{url}?s={urllib.parse.quote(query)}&t={get_unix_time()}", headers=headers, verify=False, timeout=10)
        data = res.json()
        if data.get("searchResult"):
            return [{"id": item.get("id"), "title": item.get("t")} for item in data["searchResult"]]
    except Exception:
        pass
    return []

def get_target_episode_id(session, content_id, platform, requested_season, requested_episode):
    endpoints = {
        'netflix': f"{NETMIRROR_BASE}/post.php",
        'primevideo': f"{NETMIRROR_BASE}/pv/post.php",
        'disney': f"{NETMIRROR_BASE}/mobile/hs/post.php"
    }
    url = endpoints.get(platform, endpoints['netflix'])
    
    headers = BASE_HEADERS.copy()
    headers['Referer'] = f"{NETMIRROR_BASE}/tv/home"
    
    try:
        res = session.get(f"{url}?id={content_id}&t={get_unix_time()}", headers=headers, verify=False, timeout=10)
        data = res.json()
        
        seasons = data.get("season", [])
        target_season_id = None
        
        # ആവശ്യമുള്ള സീസൺ കണ്ടുപിടിക്കുന്നു
        if seasons and len(seasons) >= requested_season:
            target_season_id = seasons[requested_season - 1].get("id")
        elif data.get("nextPageSeason"):
            target_season_id = data.get("nextPageSeason")
            
        if not target_season_id:
            return None
            
        ep_endpoints = {
            'netflix': f"{NETMIRROR_BASE}/episodes.php",
            'primevideo': f"{NETMIRROR_BASE}/pv/episodes.php",
            'disney': f"{NETMIRROR_BASE}/mobile/hs/episodes.php"
        }
        ep_url = ep_endpoints.get(platform, ep_endpoints['netflix'])
        
        page = 1
        while True:
            ep_res = session.get(f"{ep_url}?s={target_season_id}&series={content_id}&t={get_unix_time()}&page={page}", headers=headers, verify=False, timeout=10)
            ep_data = ep_res.json()
            
            for ep in ep_data.get("episodes", []):
                if not ep: continue
                
                ep_s = int(ep.get("s", "S0").replace("S", "")) if "s" in ep else (int(ep.get("season", 0)) if "season" in ep else 0)
                if ep_s == 0: ep_s = requested_season
                
                ep_n = int(ep.get("ep", "E0").replace("E", "")) if "ep" in ep else (int(ep.get("episode", 0)) if "episode" in ep else 0)
                
                if ep_s == requested_season and ep_n == requested_episode:
                    return ep.get("id")
                    
            if ep_data.get("nextPageShow") == 0:
                break
            page += 1
            
    except Exception:
        pass
        
    return None

def get_streaming_links(session, content_id, title, platform):
    url = f"{NETMIRROR_BASE}/tv/playlist.php?id={content_id}&t={urllib.parse.quote(title)}&tm={get_unix_time()}"
    headers = BASE_HEADERS.copy()
    headers['Referer'] = f"{NETMIRROR_BASE}/tv/home"
    
    try:
        res = session.get(url, headers=headers, verify=False, timeout=10)
        playlist = res.json()
        if not playlist or not isinstance(playlist, list):
            return [], []
            
        sources = []
        subtitles = []
        
        for item in playlist:
            for src in item.get("sources", []):
                full_url = src.get("file", "").replace('/tv/', '/')
                if not full_url.startswith('/'): 
                    full_url = '/' + full_url
                full_url = NETMIRROR_BASE + full_url
                
                sources.append({
                    "url": full_url,
                    "quality": src.get("label", "HD"),
                    "type": src.get("type", "application/x-mpegURL")
                })
                
            for trk in item.get("tracks", []):
                if trk.get("kind") == "captions":
                    sub_url = trk.get("file", "")
                    if sub_url.startswith("/") and not sub_url.startswith("//"):
                        sub_url = NETMIRROR_BASE + sub_url
                    elif sub_url.startswith("//"):
                        sub_url = "https:" + sub_url
                    subtitles.append({
                        "url": sub_url,
                        "lang": trk.get("label", "Unknown")
                    })
                    
        return sources, subtitles
    except Exception:
        return [], []

def get_streams(media_type, media_id, config=None):
    if ":" in media_id:
        parts = media_id.split(":")
        imdb_id = parts[0]
        season = int(parts[1]) if len(parts) > 1 else 1
        episode = int(parts[2]) if len(parts) > 2 else 1
        mt = "tv"
    else:
        imdb_id = media_id
        season = None
        episode = None
        mt = "movie"
        
    # TMDB API വഴി സിനിമയുടെ പേര് കണ്ടെത്തുന്നു
    tmdb_url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    try:
        r = requests.get(tmdb_url, timeout=10).json()
        if mt == 'movie' and r.get('movie_results'):
            title = r['movie_results'][0]['title']
            year = r['movie_results'][0].get('release_date', '')[:4]
        elif mt == 'tv' and r.get('tv_results'):
            title = r['tv_results'][0]['name']
            year = r['tv_results'][0].get('first_air_date', '')[:4]
        else:
            return []
    except Exception:
        return []
        
    session = requests.Session()
    
    # "The Boys" പോലുള്ള സീരീസുകൾക്ക് Prime Video ആദ്യ പരിഗണന നൽകുന്നു
    platforms = ['netflix', 'primevideo', 'disney']
    if 'boys' in title.lower() or 'prime' in title.lower():
        platforms = ['primevideo', 'netflix', 'disney']
        
    for platform in platforms:
        # വർഷം ഇല്ലാതെ ആദ്യം സെർച്ച് ചെയ്യുന്നു
        results = search_content(session, title, platform)
        if not results and year:
            results = search_content(session, f"{title} {year}", platform)
            
        if not results:
            continue
            
        # റിസൾട്ടുകൾ ഫിൽറ്റർ ചെയ്യുന്നു (Similarity >= 0.7)
        relevant = []
        for r in results:
            sim = calculate_similarity(r['title'], title)
            if sim >= 0.7:
                relevant.append((sim, r))
        
        if not relevant and year:
            results = search_content(session, f"{title} {year}", platform)
            for r in results:
                sim = calculate_similarity(r['title'], title)
                if sim >= 0.7:
                    relevant.append((sim, r))
        
        if not relevant:
            continue
            
        relevant.sort(key=lambda x: x[0], reverse=True)
        target = relevant[0][1]
        content_id = target['id']
        
        if mt == "tv":
            content_id = get_target_episode_id(session, content_id, platform, season, episode)
            if not content_id:
                continue
                
        sources, subtitles = get_streaming_links(session, content_id, title, platform)
        
        if sources:
            streams = []
            for src in sources:
                quality = "HD"
                if "1080" in src['quality'] or "full hd" in src['quality'].lower(): 
                    quality = "1080p"
                elif "720" in src['quality'] or "hd" in src['quality'].lower(): 
                    quality = "720p"
                elif "480" in src['quality']: 
                    quality = "480p"
                
                is_nf_or_pv = platform in ['netflix', 'primevideo']
                stream_headers = {
                    "Accept": "application/vnd.apple.mpegurl, video/mp4, */*",
                    "Origin": NETMIRROR_BASE,
                    "Referer": f"{NETMIRROR_BASE}/" if is_nf_or_pv else f"{NETMIRROR_BASE}/tv/home",
                    "Cookie": "hd=on",
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/138.0.7204.156 Mobile/15E148 Safari/604.1"
                }
                
                streams.append({
                    "name": f"NetMirror ({platform.capitalize()})",
                    "title": f"Quality: {quality}\nTitle: {title}",
                    "url": src['url'],
                    "behaviorHints": {
                        "notWebReady": True,
                        "proxyHeaders": {"request": stream_headers}
                    },
                    "subtitles": subtitles
                })
                
            # മികച്ച ക്വാളിറ്റി ആദ്യം വരുന്ന രീതിയിൽ അടുക്കുന്നു
            streams.sort(key=lambda x: int(x['title'].split('Quality: ')[1].split('p')[0]) if 'p' in x['title'] else 0, reverse=True)
            return streams
            
    return []

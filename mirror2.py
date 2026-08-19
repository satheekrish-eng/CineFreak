"""
MegaSource - NetflixMirror Scraper
================================
Scraper para o addon MegaSource (Baseado no provedor CloudStream).
"""

import requests
import urllib3

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "NetflixMirror (Net27)"
VERSION = "1.0.0"
DESCRIPTION = "NetflixMirror fallback scraper via net27.cc API"

TMDB_API_KEY = "307b7b8ef035c6aa336900aef4e203bd"
NET27_URL = "https://net27.cc"
NET27_REFERER = "https://videodownloader.site/"

HEADERS = {
    "Accept": "application/json",
    "Referer": NET27_REFERER,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
}

def get_tmdb_id(imdb_id, media_type):
    # Stremio തരുന്ന IMDb ഐഡിയെ TMDB ഐഡിയാക്കി മാറ്റുന്നു
    try:
        find_url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
        find_res = requests.get(find_url, timeout=10)
        if find_res.status_code == 200:
            data = find_res.json()
            if media_type == 'movie' and data.get("movie_results"):
                return str(data["movie_results"][0]["id"])
            elif media_type == 'series' and data.get("tv_results"):
                return str(data["tv_results"][0]["id"])
    except Exception:
        pass

    # Cinemeta Fallback
    try:
        meta_url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
        meta_res = requests.get(meta_url, timeout=10)
        if meta_res.status_code == 200:
            data = meta_res.json()
            if data and data.get("meta") and data.get("meta").get("moviedb_id"):
                return str(data["meta"]["moviedb_id"])
    except Exception:
        pass
    
    return None

def get_streams(media_type, media_id, config=None):
    if ":" in media_id:
        parts = media_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else None
        episode = parts[2] if len(parts) > 2 else 1
        mt = "series"
    else:
        imdb_id = media_id
        season = None
        episode = None
        mt = "movie"

    # TMDB ID കണ്ടുപിടിക്കുന്നു
    tmdb_id = get_tmdb_id(imdb_id, mt)
    if not tmdb_id:
        return []

    # Kotlin കോഡിലെ Fallback API URL നിർമ്മിക്കുന്നു
    if mt == "movie":
        embed_url = f"{NET27_URL}/api/embed-tmdb/{tmdb_id}"
    else:
        embed_url = f"{NET27_URL}/api/embed-tmdb/{tmdb_id}?type=tv&s={season}&e={episode}"

    try:
        res = requests.get(embed_url, headers=HEADERS, verify=False, timeout=15)
        if res.status_code != 200:
            return []
            
        data = res.json()
        
        # API മറുപടി OK ആണോ എന്ന് നോക്കുന്നു
        if data.get("ok") is not True:
            return []

        # സബ്ടൈറ്റിലുകൾ എടുക്കുന്നു
        subtitles = []
        for caption in data.get("captions", []):
            url = caption.get("url")
            if url:
                if url.startswith("/"):
                    url = f"{NET27_URL}{url}"
                subtitles.append({
                    "url": url,
                    "language": caption.get("lang", "en"),
                    "name": caption.get("name", "Subtitle")
                })

        streams = []
        
        # പ്രധാന സ്ട്രീമുകൾ എടുക്കുന്നു
        if data.get("streams"):
            for stream in data["streams"]:
                resolution = stream.get("resolution", "Unknown")
                stream_url = stream.get("url")
                
                if stream_url:
                    streams.append({
                        "name": TITLE,
                        "title": f"Quality: {resolution}p\nServer: Net27 Embed",
                        "url": stream_url,
                        "behaviorHints": {
                            "notWebReady": True,
                            "proxyHeaders": {
                                "request": {
                                    "Referer": NET27_REFERER,
                                    "User-Agent": HEADERS["User-Agent"]
                                }
                            }
                        },
                        "subtitles": subtitles
                    })
                    
        # സ്ട്രീമുകൾ ഇല്ലെങ്കിൽ mp4 ഡയറക്റ്റ് ലിങ്ക് നോക്കുന്നു
        elif data.get("mp4"):
            mp4_url = data.get("mp4")
            if mp4_url:
                streams.append({
                    "name": TITLE,
                    "title": "Quality: Auto\nServer: Net27 MP4",
                    "url": mp4_url,
                    "behaviorHints": {
                        "notWebReady": True,
                        "proxyHeaders": {
                            "request": {
                                "Referer": NET27_REFERER,
                                "User-Agent": HEADERS["User-Agent"]
                            }
                        }
                    },
                    "subtitles": subtitles
                })

        return streams

    except Exception:
        return []

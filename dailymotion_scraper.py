"""
MegaSource - Dailymotion Scraper
================================
Scraper para o addon MegaSource (Nuvio Compatible - MP4 Version).
"""

import requests
import urllib.parse
import urllib3

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "Dailymotion Scraper"
VERSION = "1.0.1"
DESCRIPTION = "Dailymotion Direct MP4 Extractor for Nuvio"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.dailymotion.com/"
}

def get_streams(media_type, media_id, config=None):
    if ":" in media_id:
        parts = media_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else None
        episode = parts[2] if len(parts) > 2 else None
        mt = "series"
    else:
        imdb_id = media_id
        season = None
        episode = None
        mt = "movie"

    # 1. Cinemeta-യിൽ നിന്നും വിവരങ്ങൾ എടുക്കുന്നു
    try:
        meta_url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
        meta_res = requests.get(meta_url, timeout=10).json()
        meta = meta_res.get("meta", {})
        title = meta.get("name", "")
        year = meta.get("year", "")
    except Exception:
        return []

    if not title:
        return []

    # 2. സെർച്ച് ചെയ്യാനുള്ള വരികൾ തയ്യാറാക്കുന്നു
    if mt == "movie":
        search_query = f"{title} {year} full movie".strip()
    else:
        search_query = f"{title} season {season} episode {episode}".strip()

    encoded_query = urllib.parse.quote(search_query)

    # 3. Dailymotion API വഴി സെർച്ച് ചെയ്യുന്നു
    search_url = f"https://api.dailymotion.com/videos?fields=id,title,duration&limit=15&search={encoded_query}"
    
    try:
        res = requests.get(search_url, headers=HEADERS, verify=False, timeout=10)
        data = res.json()
        videos = data.get("list", [])
    except Exception:
        return []

    if not videos:
        return []

    streams = []
    
    # 4. റിസൾട്ടുകൾ പരിശോധിച്ച് ഡയറക്റ്റ് MP4 ലിങ്ക് എടുക്കുന്നു
    for vid in videos:
        vid_id = vid.get("id")
        vid_title = vid.get("title", "")
        duration = vid.get("duration", 0)

        if mt == "movie" and duration < 1200:
            continue
        if mt == "series" and duration < 600:
            continue

        try:
            metadata_url = f"https://www.dailymotion.com/player/metadata/video/{vid_id}"
            meta_res = requests.get(metadata_url, headers=HEADERS, verify=False, timeout=10)
            
            if meta_res.status_code == 200:
                meta_data = meta_res.json()
                qualities = meta_data.get("qualities", {})

                # വിവിധ റെസല്യൂഷനുകളിലുള്ള MP4 ലിങ്കുകൾ പരിശോധിക്കുന്നു
                available_resolutions = ['1080', '720', '480', '380']
                
                for res_key in available_resolutions:
                    if res_key in qualities and len(qualities[res_key]) > 0:
                        stream_url = qualities[res_key][0].get("url")
                        
                        if stream_url:
                            streams.append({
                                "name": "Dailymotion",
                                "title": f"▶️ {res_key}p (MP4)\n📺 {vid_title}",
                                "url": stream_url,
                                "behaviorHints": {
                                    "notWebReady": True,
                                    "proxyHeaders": {
                                        "request": {
                                            "Referer": "https://www.dailymotion.com/",
                                            "User-Agent": HEADERS["User-Agent"]
                                        }
                                    }
                                }
                            })
                            # ഒരു വീഡിയോയുടെ മികച്ച ക്വാളിറ്റി മാത്രം മതി, അതുകൊണ്ട് ബ്രേക്ക് ചെയ്യുന്നു
                            break
                            
                # പരമാവധി 5 റിസൾട്ടുകൾ
                if len(streams) >= 5:
                    break
        except Exception:
            continue

    return streams

"""
MegaSource - PlayIMDb Scraper
================================
Scraper para o addon MegaSource.
"""

import requests
import urllib3

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "PlayIMDb Fast Scraper"
VERSION = "1.0.2"
DESCRIPTION = "Direct API stream scraper using PlayIMDb & VAPlayer"

TMDB_API_KEY = "68e094699525b18a70bab2f86b1fa706"
BASE_API = "https://streamdata.vaplayer.ru/api.php"
HEADERS = {
    'Origin': 'https://nextgencloudfabric.com',
    'Referer': 'https://nextgencloudfabric.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'
}

def get_tmdb_id(imdb_id, media_type):
    """
    IMDb ഐഡി ഉപയോഗിച്ച് TMDB ഐഡി കണ്ടുപിടിക്കാനുള്ള ഫംഗ്ഷൻ.
    """
    # 1. TMDB API വഴി ശ്രമിക്കുന്നു
    try:
        find_url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
        find_res = requests.get(find_url, timeout=10)
        if find_res.status_code == 200:
            data = find_res.json()
            if media_type == 'movie' and data.get("movie_results"):
                return data["movie_results"][0]["id"]
            elif media_type == 'series' and data.get("tv_results"):
                return data["tv_results"][0]["id"]
    except Exception:
        pass

    # 2. TMDB പരാജയപ്പെട്ടാൽ Cinemeta വഴി ശ്രമിക്കുന്നു (Fallback)
    try:
        meta_url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
        meta_res = requests.get(meta_url, timeout=10)
        if meta_res.status_code == 200:
            data = meta_res.json()
            if data and data.get("meta") and data["meta"].get("moviedb_id"):
                return data["meta"]["moviedb_id"]
    except Exception:
        pass
    
    return None

def get_streams(media_type, media_id, config=None):
    """
    MegaSource ഫംഗ്ഷൻ: API വഴി ഡയറക്റ്റ് സ്ട്രീം ലിങ്കുകൾ കണ്ടെത്തുന്നു.
    """
    if ":" in media_id:
        parts = media_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else None
        episode = parts[2] if len(parts) > 2 else None
    else:
        imdb_id = media_id
        season = None
        episode = None

    tmdb_id = get_tmdb_id(imdb_id, media_type)
    
    if not tmdb_id:
        return []

    # API ലിങ്ക് നിർമ്മിക്കുന്നു
    api_url = f"{BASE_API}?tmdb={tmdb_id}&type={media_type}"
    if media_type == 'series' and season and episode:
        api_url += f"&season={season}&episode={episode}"

    try:
        api_res = requests.get(api_url, headers=HEADERS, timeout=15)
        if api_res.status_code != 200:
            return []
            
        data = api_res.json()
        status_code = str(data.get("status_code", ""))
        status = str(data.get("status", ""))
        
        # API റെസ്പോൺസ് വിജയമാണോ എന്ന് പരിശോധിക്കുന്നു
        if status_code == "200" or status == "success":
            resp_data = data.get("data", {})
            stream_urls = resp_data.get("stream_urls", [])
            file_name = str(resp_data.get("file_name", "")).lower()
            
            if not stream_urls:
                return []
            
            # ഫയലിന്റെ പേരിൽ നിന്ന് ക്വാളിറ്റിയും ഓഡിയോയും വേർതിരിച്ചെടുക്കുന്നു
            quality = "1080p FHD"
            if "2160p" in file_name or "4k" in file_name:
                quality = "4K UHD"
            elif "720p" in file_name:
                quality = "720p HD"
                
            audio = "Original Audio"
            if "dual" in file_name or "multi" in file_name:
                audio = "Dual/Multi Audio"
            elif "hindi" in file_name:
                audio = "Hindi Audio"
            elif "english" in file_name:
                audio = "English Audio"
            
            streams = []
            for index, url in enumerate(stream_urls):
                fmt = "M3U8" if ".m3u8" in url else "MP4"
                
                # (Note: കോഡിൽ behaviorHints കൊടുത്തിട്ടില്ലാത്തതിനാൽ പ്ലേയറിലെ പ്രോക്സി പ്രശ്നങ്ങൾ ഉണ്ടാകില്ല)
                streams.append({
                    "name": "PlayIMDb",
                    "title": f"🎥 {quality} | 🔊 {audio}\n⚙️ {fmt} | Server {index + 1}",
                    "url": url
                })
                
            return streams
    except Exception as e:
        pass

    return []

"""
MegaSource - YouTube Direct Scraper
================================
Scraper para o addon MegaSource (Nuvio Compatible)
"""

import requests
import re
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

TITLE = "YT Movies Direct"
VERSION = "1.10.1"
DESCRIPTION = "YouTube Streamer with Direct MP4 extraction for Nuvio"

# ഒഴിവാക്കേണ്ട ചാനലുകളുടെ ലിസ്റ്റ് 
BLACKLIST_CHANNELS = [
    "empire video", "empirevideomalayalam", "simply south", 
    "simplysouth", "pyramid talkies", "cine buster"
]

def get_streams(media_type, media_id, config=None):
    if media_type != "movie":
        return []
        
    if not yt_dlp:
        print("Error: yt-dlp module is not installed!")
        return []

    imdb_id = media_id.split(':')[0]

    # 1. Cinemeta-യിൽ നിന്നും സിനിമയുടെ വിവരങ്ങൾ എടുക്കുന്നു
    try:
        meta_res = requests.get(f"https://v3-cinemeta.strem.io/meta/movie/{imdb_id}.json", timeout=10).json()
        meta = meta_res.get("meta", {})
        movie_name = meta.get("name", "")
        movie_year = meta.get("year", "")
        movie_language = meta.get("language", "malayalam")
        
        cast = meta.get("cast", [])
        actor1 = cast[0] if len(cast) > 0 else ""
        actor2 = cast[1] if len(cast) > 1 else ""
    except Exception as e:
        print(f"Cinemeta Error: {e}")
        return []

    if not movie_name:
        return []

    # സെർച്ച് ചെയ്യാനുള്ള വരികൾ തയ്യാറാക്കുന്നു (Plan A)
    search_query = f"{movie_name} {movie_year} {actor1} {actor2} {movie_language} full movie".replace("  ", " ").strip()
    print(f"Searching YouTube for: {search_query}")

    # 2. yt-dlp ഉപയോഗിച്ച് സെർച്ച് ചെയ്യുന്നു (വേഗത്തിൽ റിസൾട്ട് എടുക്കാൻ 'extract_flat' ഉപയോഗിക്കുന്നു)
    ydl_search_opts = {
        'extract_flat': True,
        'default_search': 'ytsearch10',  # ആദ്യത്തെ 10 റിസൾട്ടുകൾ എടുക്കുന്നു
        'quiet': True,
        'match_filter': yt_dlp.utils.match_filter_func("duration >= 5400"), # 1.5 മണിക്കൂറിന് മുകളിലുള്ളവ
    }

    try:
        with yt_dlp.YoutubeDL(ydl_search_opts) as ydl:
            search_info = ydl.extract_info(search_query, download=False)
    except Exception as e:
        print(f"yt-dlp Search Error: {e}")
        return []

    if not search_info or 'entries' not in search_info:
        return []

    valid_videos = []
    
    # 3. ഫിൽറ്ററിംഗ് & സ്കോറിംഗ് ലോജിക്
    for vid in search_info['entries']:
        if not vid: continue
        
        channel_name = vid.get('uploader', '').lower()
        
        # കരിമ്പട്ടികയിൽ (Blacklist) പെട്ട ചാനലാണോ എന്ന് നോക്കുന്നു
        is_blacklisted = False
        for bc in BLACKLIST_CHANNELS:
            if bc in channel_name or bc.replace(" ", "") in channel_name.replace(" ", ""):
                is_blacklisted = True
                break
                
        if is_blacklisted:
            continue
            
        title = vid.get('title', '').lower()
        clean_title = re.sub(r'[^a-z0-9 ]', ' ', title)
        clean_name = re.sub(r'[^a-z0-9 ]', ' ', movie_name.lower()).strip()
        year_str = str(movie_year)
        
        score = 0
        
        # റിലവൻസ് സ്കോറിംഗ് 
        if clean_name in clean_title and year_str in clean_title:
            score += 50
        elif clean_name in clean_title:
            score += 20
            
        # ക്വാളിറ്റി സ്കോറിംഗ് 
        if "4k" in title: score += 40
        elif "1080p" in title or "full hd" in title: score += 30
        elif "720p" in title or "hd" in title: score += 20
        
        valid_videos.append({'video': vid, 'score': score})

    # മാർക്കിന്റെ അടിസ്ഥാനത്തിൽ അടുക്കുന്നു
    valid_videos.sort(key=lambda x: x['score'], reverse=True)

    if not valid_videos:
        return []

    # 4. ഏറ്റവും മികച്ച വീഡിയോയുടെ ഡയറക്റ്റ് mp4 ലിങ്ക് എടുക്കുന്നു
    top_video = valid_videos[0]['video']
    video_url = top_video.get('url')
    
    ydl_extract_opts = {
        'format': 'best',
        'quiet': True,
        'noplaylist': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_extract_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            direct_url = info.get('url')
            
            if direct_url:
                quality_text = "Standard Quality"
                if valid_videos[0]['score'] >= 40: quality_text = "🌟 4K Premium"
                elif valid_videos[0]['score'] >= 30: quality_text = "🔥 Full HD"
                elif valid_videos[0]['score'] >= 20: quality_text = "✅ HD Video"

                return [{
                    "name": "YT Direct",
                    "title": f"▶️ {quality_text}\n📺 {info.get('uploader', 'YouTube')}",
                    "url": direct_url,
                    "behaviorHints": {
                        "notWebReady": True # Nuvio-യിലെ പ്ലെയർ പ്രശ്നങ്ങൾ ഒഴിവാക്കാൻ
                    }
                }]
    except Exception as e:
        print(f"Extraction Error: {e}")

    return []

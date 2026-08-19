"""
MegaSource - YouTube Direct Scraper (API Version)
================================
Scraper para o addon MegaSource (Nuvio Compatible via Piped API)
"""

import requests
import urllib.parse
import urllib3
import re

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "YT Movies API"
VERSION = "1.10.2"
DESCRIPTION = "YouTube Streamer via Piped API for Nuvio"

# Piped API സെർവറുകൾ (ഒന്ന് വർക്ക് ആയില്ലെങ്കിൽ അടുത്തത് ഉപയോഗിക്കാൻ)
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.tokhmi.xyz",
    "https://piped-api.garudalinux.org"
]

# ഒഴിവാക്കേണ്ട ചാനലുകളുടെ ലിസ്റ്റ് 
BLACKLIST_CHANNELS = [
    "empire video", "empirevideomalayalam", "simply south", 
    "simplysouth", "pyramid talkies", "cine buster"
]

def get_streams(media_type, media_id, config=None):
    if media_type != "movie":
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

    # സെർച്ച് ചെയ്യാനുള്ള വരികൾ തയ്യാറാക്കുന്നു
    search_query = f"{movie_name} {movie_year} {actor1} {actor2} {movie_language} full movie".replace("  ", " ").strip()
    encoded_query = urllib.parse.quote(search_query)
    
    valid_videos = []
    working_instance = None

    # 2. Piped API ഉപയോഗിച്ച് സെർച്ച് ചെയ്യുന്നു
    for instance in PIPED_INSTANCES:
        try:
            search_url = f"{instance}/search?q={encoded_query}&filter=videos"
            res = requests.get(search_url, verify=False, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                items = data.get("items", [])
                
                if items:
                    working_instance = instance
                    # 3. ഫിൽറ്ററിംഗ് & സ്കോറിംഗ് ലോജിക്
                    for vid in items:
                        duration = vid.get("duration", 0)
                        if duration < 5400:  # 1.5 മണിക്കൂറിന് താഴെയുള്ളവ ഒഴിവാക്കുന്നു
                            continue
                            
                        channel_name = vid.get("uploaderName", "").lower()
                        
                        # കരിമ്പട്ടികയിൽ പെട്ട ചാനലാണോ എന്ന് നോക്കുന്നു
                        is_blacklisted = False
                        for bc in BLACKLIST_CHANNELS:
                            if bc in channel_name or bc.replace(" ", "") in channel_name.replace(" ", ""):
                                is_blacklisted = True
                                break
                                
                        if is_blacklisted:
                            continue
                            
                        title = vid.get("title", "").lower()
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
                        
                        vid_id = vid.get("url", "").replace("/watch?v=", "")
                        if vid_id:
                            valid_videos.append({
                                'id': vid_id, 
                                'title': vid.get("title", ""),
                                'uploader': vid.get("uploaderName", ""),
                                'score': score
                            })
                    
                    break # ഒരു ഇൻസ്റ്റൻസ് വർക്ക് ആയാൽ ബാക്കിയുള്ളവ ഒഴിവാക്കുന്നു
        except Exception as e:
            print(f"API Error with {instance}: {e}")
            continue

    if not valid_videos or not working_instance:
        return []

    # മാർക്കിന്റെ അടിസ്ഥാനത്തിൽ അടുക്കുന്നു
    valid_videos.sort(key=lambda x: x['score'], reverse=True)
    top_video = valid_videos[0]
    
    # 4. ഏറ്റവും മികച്ച വീഡിയോയുടെ ഡയറക്റ്റ് സ്ട്രീം ലിങ്ക് API വഴി എടുക്കുന്നു
    try:
        stream_url = f"{working_instance}/streams/{top_video['id']}"
        stream_res = requests.get(stream_url, verify=False, timeout=10)
        
        if stream_res.status_code == 200:
            stream_data = stream_res.json()
            
            # HLS ലിങ്ക് ഉണ്ടെങ്കിൽ അത് എടുക്കുന്നു (Nuvio-യ്ക്ക് ഏറ്റവും നല്ലത് അതാണ്)
            direct_link = stream_data.get("hls")
            
            # HLS ഇല്ലെങ്കിൽ ആദ്യത്തെ വീഡിയോ സ്ട്രീം എടുക്കുന്നു
            if not direct_link:
                video_streams = stream_data.get("videoStreams", [])
                if video_streams:
                    # 1080p അല്ലെങ്കിൽ 720p കണ്ടെത്തുന്നു
                    best_stream = next((s for s in video_streams if "1080p" in s.get("quality", "")), None)
                    if not best_stream:
                        best_stream = next((s for s in video_streams if "720p" in s.get("quality", "")), video_streams[0])
                    direct_link = best_stream.get("url")
            
            if direct_link:
                quality_text = "Standard Quality"
                if top_video['score'] >= 40: quality_text = "🌟 4K Premium"
                elif top_video['score'] >= 30: quality_text = "🔥 Full HD"
                elif top_video['score'] >= 20: quality_text = "✅ HD Video"

                return [{
                    "name": "YouTube API",
                    "title": f"▶️ {quality_text}\n📺 {top_video['uploader']}",
                    "url": direct_link,
                    "behaviorHints": {
                        "notWebReady": True
                    }
                }]
    except Exception as e:
        print(f"Stream Extraction Error: {e}")

    return []

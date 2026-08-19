"""
MegaSource - Qorva (Vidup) Scraper
================================
Scraper para o addon MegaSource.
"""

import requests
import urllib.parse
import urllib3

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "Qorva Scraper"
VERSION = "1.0.2"
DESCRIPTION = "Vidup API Scraper for MegaSource (Session Fixed)"

QORVA_API = "https://vidup.to"
DECRYPT_API = "https://enc-dec.app/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
TMDB_API_KEY = "307b7b8ef035c6aa336900aef4e203bd"

def get_headers():
    return {
        "User-Agent": UA,
        "Referer": f"{QORVA_API}/",
        "X-Requested-With": "XMLHttpRequest"
    }

def get_lang_code(lang_name):
    lang_name = lang_name.lower().strip()
    mapping = {
        "english": "en", "spanish": "es", "french": "fr",
        "german": "de", "italian": "it", "portuguese": "pt",
        "arabic": "ar", "japanese": "ja", "korean": "ko",
        "hindi": "hi", "thai": "th", "turkish": "tr",
        "malayalam": "ml", "tamil": "ta", "telugu": "te"
    }
    return mapping.get(lang_name, "en")

def get_tmdb_id(imdb_id, media_type):
    # 1. TMDB API
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

    # 2. Cinemeta Fallback
    try:
        meta_url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
        meta_res = requests.get(meta_url, timeout=10)
        if meta_res.status_code == 200:
            data = meta_res.json()
            if data and data.get("meta") and data["meta"].get("moviedb_id"):
                return str(data["meta"]["moviedb_id"])
    except Exception:
        pass
    return None

def resolve_server(session, csrf_token, stream_url, server):
    try:
        server_data = server.get("data")
        if not server_data:
            return None
        server_name = server.get("name", "Vidup")

        # 1. സെർവറിൽ നിന്ന് ഡാറ്റ എടുക്കുന്നു (കുക്കികൾ നിലനിർത്താൻ session ഉപയോഗിക്കുന്നു)
        post_headers = get_headers()
        post_headers["X-CSRF-Token"] = csrf_token

        req_url = f"{stream_url}/{server_data}"
        res = session.post(req_url, headers=post_headers, verify=False, timeout=15)
        
        if res.status_code != 200:
            return None
            
        enc_text = res.text

        # 2. ഡാറ്റ ഡീകോഡ് ചെയ്യുന്നു (ഇത് പുറത്തുള്ള API ആയതിനാൽ requests മതി)
        json_headers = get_headers()
        json_headers["Content-Type"] = "application/json"
        
        dec_res = requests.post(
            f"{DECRYPT_API}/dec-vidup", 
            headers=json_headers, 
            json={"text": enc_text}, 
            verify=False, 
            timeout=15
        )
        
        if dec_res.status_code != 200:
            return None

        final_data = dec_res.json()
        if final_data.get("status") != 200:
            return None

        result = final_data.get("result", {})
        final_url = result.get("url")
        if not final_url:
            return None

        # 3. സബ്ടൈറ്റിലുകൾ എടുക്കുന്നു
        tracks = result.get("tracks", [])
        subtitles = []
        for t in tracks:
            file_url = t.get("file")
            if file_url and file_url.startswith("https://"):
                label = t.get("label", "Unknown")
                subtitles.append({
                    "url": file_url,
                    "language": get_lang_code(label),
                    "name": label
                })

        return {
            "name": f"VidUp - {server_name}",
            "title": f"Quality: 1080p | Server: {server_name}",
            "url": final_url,
            "behaviorHints": {
                "notWebReady": True,
                "proxyHeaders": {
                    "request": {
                        "Referer": f"{QORVA_API}/",
                        "Origin": QORVA_API,
                        "User-Agent": UA
                    }
                }
            },
            "subtitles": subtitles
        }
    except Exception:
        return None

def get_streams(media_type, media_id, config=None):
    if ":" in media_id:
        parts = media_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else None
        episode = parts[2] if len(parts) > 2 else 1
    else:
        imdb_id = media_id
        season = None
        episode = None

    tmdb_id = get_tmdb_id(imdb_id, media_type)
    if not tmdb_id:
        return []

    # ഏറ്റവും പ്രധാനം: കുക്കികൾ സേവ് ചെയ്യാൻ Session ഉപയോഗിക്കുന്നു
    session = requests.Session()

    try:
        if media_type == "series" and season:
            page_url = f"{QORVA_API}/tv/{tmdb_id}/{season}/{episode}"
        else:
            page_url = f"{QORVA_API}/movie/{tmdb_id}"

        res = session.get(page_url, headers=get_headers(), verify=False, timeout=15)
        if res.status_code != 200:
            return []
            
        page_text = res.text

        # എൻക്രിപ്റ്റ് ചെയ്ത ടെക്സ്റ്റ് എടുക്കുന്നു
        needle = r'\"en\":\"'
        start_idx = page_text.find(needle)
        
        # കോഡ് ചിലപ്പോൾ എസ്കേപ്പ് ചെയ്യാതെയാണെങ്കിലോ എന്ന് കരുതി ഒരു Fallback
        if start_idx == -1:
            needle = '"en":"'
            start_idx = page_text.find(needle)
            end_char = '"'
        else:
            end_char = r'\"'

        if start_idx == -1:
            return []
            
        start_idx += len(needle)
        end_idx = page_text.find(end_char, start_idx)
        if end_idx == -1:
            return []
            
        enc_text = page_text[start_idx:end_idx]

        # ഡീകോഡ് API
        encoded_text = urllib.parse.quote(enc_text, safe='')
        enc_url = f"{DECRYPT_API}/enc-vidup?text={encoded_text}"
        
        enc_res = requests.get(enc_url, headers=get_headers(), verify=False, timeout=15)
        
        if enc_res.status_code != 200:
            return []
            
        enc_data = enc_res.json()
        if enc_data.get("status") != 200:
            return []

        result = enc_data.get("result", {})
        servers_url = result.get("servers")
        stream_url = result.get("stream")
        token = result.get("token")

        if not servers_url or not stream_url or not token:
            return []

        # സെർവറുകളുടെ ലിസ്റ്റ് എടുക്കുന്നു (Session വഴി CSRF Token അയക്കുന്നു)
        csrf_headers = get_headers()
        csrf_headers["X-CSRF-Token"] = token

        servers_enc_res = session.post(servers_url, headers=csrf_headers, verify=False, timeout=15)
        if servers_enc_res.status_code != 200:
            return []
            
        servers_enc_text = servers_enc_res.text

        # സെർവറുകളുടെ ലിസ്റ്റ് ഡീകോഡ് ചെയ്യുന്നു
        dec_json_headers = get_headers()
        dec_json_headers["Content-Type"] = "application/json"
        
        dec_servers_res = requests.post(
            f"{DECRYPT_API}/dec-vidup", 
            headers=dec_json_headers, 
            json={"text": servers_enc_text}, 
            verify=False, 
            timeout=15
        )
        
        if dec_servers_res.status_code != 200:
            return []
            
        dec_servers_data = dec_servers_res.json()
        if dec_servers_data.get("status") != 200:
            return []

        server_list = dec_servers_data.get("result", [])
        if not server_list:
            return []

        # ഓരോ സെർവറിലെയും ഡാറ്റ എടുക്കുന്നു
        all_streams = []
        seen_urls = set()

        for server in server_list:
            stream_data = resolve_server(session, token, stream_url, server)
            if stream_data:
                url = stream_data.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_streams.append(stream_data)

        return all_streams

    except Exception:
        return []

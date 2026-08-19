"""
MegaSource - Qorva (Vidup) Scraper
================================
Scraper para o addon MegaSource.
"""

import requests
import urllib.parse
import urllib3
import re
import json

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "Qorva Scraper"
VERSION = "1.0.0"
DESCRIPTION = "Vidup API Scraper for MegaSource"

QORVA_API = "https://vidup.to"
DECRYPT_API = "https://enc-dec.app/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"

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
        "dutch": "nl", "swedish": "sv", "danish": "da",
        "norwegian": "no", "polish": "pl", "romanian": "ro",
        "czech": "cs", "hungarian": "hu", "greek": "el",
        "ukrainian": "uk", "russian": "ru", "hebrew": "he",
        "indonesian": "id", "malay": "ms", "vietnamese": "vi",
        "persian": "fa", "chinese": "zh", "zh-tw": "zh",
        "bengali": "bn", "tamil": "ta", "telugu": "te",
        "malayalam": "ml", "kannada": "kn", "sinhala": "si"
    }
    return mapping.get(lang_name, "en")

def resolve_server(csrf_token, stream_url, server):
    try:
        server_data = server.get("data")
        if not server_data:
            return None
        server_name = server.get("name", "Vidup")

        # 1. സെർവറിൽ നിന്ന് എൻക്രിപ്റ്റ് ചെയ്ത ഡാറ്റ എടുക്കുന്നു
        post_headers = get_headers()
        post_headers["X-CSRF-Token"] = csrf_token

        req_url = f"{stream_url}/{server_data}"
        res = requests.post(req_url, headers=post_headers, verify=False, timeout=10)
        
        if res.status_code != 200:
            return None
            
        enc_text = res.text

        # 2. ഡാറ്റ ഡീകോഡ് ചെയ്യുന്നു
        json_headers = post_headers.copy()
        json_headers["Content-Type"] = "application/json"

        dec_res = requests.post(
            f"{DECRYPT_API}/dec-vidup", 
            headers=json_headers, 
            json={"text": enc_text}, 
            verify=False, 
            timeout=10
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

        # 3. സബ്ടൈറ്റിലുകൾ വേർതിരിച്ചെടുക്കുന്നു
        tracks = result.get("tracks", [])
        subtitles = []
        for t in tracks:
            file_url = t.get("file")
            if file_url and file_url.startswith("https://"):
                label = t.get("label", "Unknown")
                subtitles.append({
                    "url": file_url,
                    "language": get_lang_code(label),
                    "name": label,
                    "headers": {"Referer": f"{QORVA_API}/"}
                })

        return {
            "name": f"VidUp - {server_name}",
            "title": f"Quality: 1080p\nServer: {server_name}",
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
        tmdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else None
        episode = parts[2] if len(parts) > 2 else 1
        mt = "series"
    else:
        tmdb_id = media_id
        season = None
        episode = None
        mt = "movie"

    # TMDB ID ആണ് Qorva ഉപയോഗിക്കുന്നത് എന്ന് Rust കോഡ് കാണിക്കുന്നു
    # അതുകൊണ്ട് Stremio-ൽ നിന്ന് വരുന്ന IMDb ID-യെ TMDB ആക്കി മാറ്റേണ്ടതുണ്ട്
    if tmdb_id.startswith("tt"):
        try:
            tmdb_api_key = "307b7b8ef035c6aa336900aef4e203bd" # Default fallback key
            find_url = f"https://api.themoviedb.org/3/find/{tmdb_id}?api_key={tmdb_api_key}&external_source=imdb_id"
            r = requests.get(find_url, timeout=10).json()
            if mt == 'movie' and r.get('movie_results'):
                tmdb_id = str(r['movie_results'][0]['id'])
            elif mt == 'series' and r.get('tv_results'):
                tmdb_id = str(r['tv_results'][0]['id'])
            else:
                return []
        except Exception:
            return []

    try:
        # 1. പേജ് URL നിർമ്മിക്കുന്നു
        if mt == "series" and season:
            page_url = f"{QORVA_API}/tv/{tmdb_id}/{season}/{episode}"
        else:
            page_url = f"{QORVA_API}/movie/{tmdb_id}"

        res = requests.get(page_url, headers=get_headers(), verify=False, timeout=10)
        if res.status_code != 200:
            return []
            
        page_text = res.text

        # 2. എൻക്രിപ്റ്റ് ചെയ്ത ടെക്സ്റ്റ് വേർതിരിച്ചെടുക്കുന്നു
        needle = r'\"en\":\"'
        start_idx = page_text.find(needle)
        if start_idx == -1:
            return []
            
        start_idx += len(needle)
        end_idx = page_text.find(r'\"', start_idx)
        if end_idx == -1:
            return []
            
        enc_text = page_text[start_idx:end_idx]

        # 3. ഡീകോഡ് API വഴി വിവരങ്ങൾ എടുക്കുന്നു
        enc_url = f"{DECRYPT_API}/enc-vidup?text={urllib.parse.quote(enc_text)}"
        enc_res = requests.get(enc_url, headers=get_headers(), verify=False, timeout=10)
        
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

        # 4. സെർവറുകളുടെ ലിസ്റ്റ് എടുക്കുന്നു
        csrf_headers = get_headers()
        csrf_headers["X-CSRF-Token"] = token

        servers_enc_res = requests.post(servers_url, headers=csrf_headers, verify=False, timeout=10)
        if servers_enc_res.status_code != 200:
            return []
            
        servers_enc_text = servers_enc_res.text

        # 5. സെർവറുകളുടെ ലിസ്റ്റ് ഡീകോഡ് ചെയ്യുന്നു
        json_headers = csrf_headers.copy()
        json_headers["Content-Type"] = "application/json"

        dec_servers_res = requests.post(
            f"{DECRYPT_API}/dec-vidup", 
            headers=json_headers, 
            json={"text": servers_enc_text}, 
            verify=False, 
            timeout=10
        )
        
        if dec_servers_res.status_code != 200:
            return []
            
        dec_servers_data = dec_servers_res.json()
        if dec_servers_data.get("status") != 200:
            return []

        server_list = dec_servers_data.get("result", [])
        if not server_list:
            return []

        # 6. ഓരോ സെർവറിലെയും ഡാറ്റ എടുക്കുന്നു
        all_streams = []
        seen_urls = set()

        for server in server_list:
            stream_data = resolve_server(token, stream_url, server)
            if stream_data:
                url = stream_data.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_streams.append(stream_data)

        return all_streams

    except Exception:
        return []

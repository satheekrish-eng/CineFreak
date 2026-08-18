"""
MegaSource - CineFreak Scraper
================================
Scraper para o addon MegaSource.
"""

import requests
from bs4 import BeautifulSoup
import base64
import urllib.parse
import time
import re
import urllib3

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "CineFreak Scraper"
VERSION = "1.0.0"
DESCRIPTION = "Filmes e Series do CineFreak (Direct Stream)"

DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json"
MAIN_URL = "https://cinefreak.nl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": f"{MAIN_URL}/"
}

def fetch_and_update_domain():
    global MAIN_URL, HEADERS
    try:
        res = requests.get(DOMAINS_URL, verify=False, timeout=10)
        data = res.json()
        if data and data.get("cinefreak"):
            new_domain = data["cinefreak"]
            if new_domain != MAIN_URL:
                MAIN_URL = new_domain
                HEADERS["Referer"] = f"{MAIN_URL}/"
    except Exception:
        pass

def get_streams(media_type, media_id, config=None):
    """
    MegaSource ഫംഗ്ഷൻ: Stremio നൽകുന്ന media_id ഉപയോഗിച്ച് സ്ട്രീം ലിങ്കുകൾ കണ്ടെത്തുന്നു
    """
    fetch_and_update_domain()
    
    imdb_id = media_id.split(':')[0]
    
    # Cinemeta-യിൽ നിന്നും സിനിമയുടെ പേര് കണ്ടുപിടിക്കുന്നു
    cinemeta_url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
    try:
        meta_res = requests.get(cinemeta_url, timeout=10).json()
        movie_name = meta_res.get("meta", {}).get("name")
    except Exception:
        return []
        
    if not movie_name:
        return []

    # CineFreak-ൽ സെർച്ച് ചെയ്യുന്നു
    search_query = urllib.parse.quote(movie_name)
    search_api_url = f"{MAIN_URL}/search-api.php?q={search_query}&pg=1&_t={int(time.time() * 1000)}"
    
    try:
        search_res = requests.get(search_api_url, headers=HEADERS, verify=False, timeout=10).json()
    except Exception:
        return []

    if not search_res or not search_res.get("results"):
        return []

    movie_slug = search_res["results"][0].get("l")
    if not movie_slug:
        return []
    
    movie_page_url = f"{MAIN_URL}/{movie_slug}/"
    
    try:
        movie_res = requests.get(movie_page_url, headers=HEADERS, verify=False, timeout=10)
        soup = BeautifulSoup(movie_res.text, 'html.parser')
    except Exception:
        return []

    streams = []
    dl_containers = soup.select('.dlbtn-container')
    
    for index, el in enumerate(dl_containers):
        prev_title = el.find_previous_sibling('h4', class_='movie-title')
        raw_title = prev_title.text.strip() if prev_title else f"Link {index+1}"
        raw_title = re.sub(r'\s+', ' ', raw_title)
        
        watch_btn = el.select_one('.dlbtn-watch')
        download_btn = el.select_one('.dlbtn-download')
        
        target_btn = None
        if download_btn and download_btn.has_attr('href'):
            target_btn = download_btn['href']
        elif watch_btn and watch_btn.has_attr('href'):
            target_btn = watch_btn['href']

        if target_btn and 'generate.php?id=' in target_btn:
            try:
                encoded_id = target_btn.split('id=')[1]
                decoded_url = base64.b64decode(encoded_id).decode('utf-8')
                decoded_url = decoded_url.replace('newgo32', '')
                
                cloud_res = requests.get(decoded_url, headers=HEADERS, verify=False, timeout=15)
                cloud_soup = BeautifulSoup(cloud_res.text, 'html.parser')
                
                page_title = cloud_soup.title.string.strip() if cloud_soup.title else ""
                
                # ക്ലൗഡ്‌ഫ്ലെയർ ബ്ലോക്ക് ഉണ്ടോ എന്ന് നോക്കുന്നു
                if 'Just a moment' in page_title:
                    continue 

                csrf_meta = cloud_soup.select_one('meta[name="X-CSRF-TOKEN"]')
                csrf_token = csrf_meta['content'] if csrf_meta else None
                
                cookies = cloud_res.cookies.get_dict()
                cookie_string = "; ".join([f"{k}={v}" for k, v in cookies.items()])

                direct_link = None
                fsl_btn = cloud_soup.select_one('a.fsl-btn')
                dl_now = cloud_soup.select_one('a.download-now')
                
                if fsl_btn and fsl_btn.has_attr('href'):
                    direct_link = fsl_btn['href']
                elif dl_now and dl_now.has_attr('href'):
                    direct_link = dl_now['href']
                    
                if not direct_link or not direct_link.startswith('http'):
                    for a_tag in cloud_soup.find_all('a', href=True):
                        href = a_tag['href']
                        if re.search(r'\.(mkv|mp4)', href, re.IGNORECASE) or 'r2.dev' in href or 'r2.cloudflarestorage' in href:
                            direct_link = href
                            break

                if not direct_link and csrf_token:
                    post_url = decoded_url
                    if '/x/' in decoded_url:
                        post_url = decoded_url.replace('/x/', '/w/')
                    elif '/f/' in decoded_url:
                        post_url = decoded_url.replace('/f/', '/fastdl/')

                    post_headers = HEADERS.copy()
                    post_headers.update({
                        'Cookie': cookie_string,
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': decoded_url
                    })
                    
                    post_res = requests.post(post_url, data={"csrf_test_name": csrf_token}, headers=post_headers, verify=False, timeout=15)
                    try:
                        post_data = post_res.json()
                        if post_data and post_data.get("url"):
                            direct_link = post_data["url"]
                    except Exception:
                        pass

                if direct_link and direct_link.startswith('http'):
                    quality_match = re.search(r'(480p|720p|1080p|2160p|4K)', raw_title, re.IGNORECASE)
                    quality = quality_match.group(1) if quality_match else 'HD'
                    
                    clean_title = re.sub(r'(SD|HD|HEVC|480p|720p|1080p|2160p|4K|-2160p)', '', raw_title, flags=re.IGNORECASE)
                    clean_title = re.sub(r'\s+', ' ', clean_title).strip()

                    # മെഗാസോഴ്സ് ഫോർമാറ്റിലേക്ക് ലിങ്ക് ചേർക്കുന്നു
                    streams.append({
                        "name": f"CineFreak\n{quality}",
                        "title": f"▶ {clean_title}\n⚡ Direct Stream",
                        "url": direct_link,
                        "behaviorHints": {
                            "notWebReady": True,
                            "proxyHeaders": {
                                "request": {
                                    "User-Agent": HEADERS["User-Agent"],
                                    "Referer": decoded_url
                                }
                            }
                        }
                    })
            except Exception:
                pass

    return streams

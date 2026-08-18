import time
import base64
import re
import urllib.parse
import requests
import urllib3
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from flask_cors import CORS

# Disable insecure request warnings for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

PORT = 7000
MAIN_URL = "https://cinefreak.nl"
DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": f"{MAIN_URL}/"
}

def fetch_and_update_domain():
    global MAIN_URL, HEADERS
    try:
        response = requests.get(DOMAINS_URL, verify=False, timeout=10)
        data = response.json()
        if data and data.get("cinefreak"):
            new_domain = data["cinefreak"]
            if new_domain != MAIN_URL:
                print(f"[Domain] Updating domain from {MAIN_URL} to {new_domain}")
                MAIN_URL = new_domain
                HEADERS["Referer"] = f"{MAIN_URL}/"
    except Exception as e:
        print(f"[Domain] Failed to fetch domains. {e}")

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "id": "org.cinefreak.streams.python",
        "version": "1.0.3",
        "name": "CineFreak Streamer (Python)",
        "description": "Direct Fast Streaming Addon for CineFreak",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "catalogs": [],
        "idPrefixes": ["tt"]
    })

@app.route('/stream/<req_type>/<req_id>.json')
@app.route('/stream/<req_type>/<req_id>/<extra>.json')
def stream(req_type, req_id, extra=None):
    print(f"\n================================")
    print(f"🎬 [START] Request for ID: {req_id}")
    
    try:
        fetch_and_update_domain()

        imdb_id = req_id.split(':')[0]
        cinemeta_url = f"https://v3-cinemeta.strem.io/meta/{req_type}/{imdb_id}.json"
        
        meta_res = requests.get(cinemeta_url, timeout=10)
        meta_data = meta_res.json()
        movie_name = meta_data.get("meta", {}).get("name")

        if not movie_name:
            return jsonify({"streams": []})
        
        print(f"✅ Title Found: {movie_name}")

        search_query = urllib.parse.quote(movie_name)
        search_api_url = f"{MAIN_URL}/search-api.php?q={search_query}&pg=1&_t={int(time.time() * 1000)}"
        print(f"[Search] API: {search_api_url}")
        
        search_res = requests.get(search_api_url, headers=HEADERS, verify=False, timeout=10)
        search_data = search_res.json()

        if not search_data or not search_data.get("results"):
            print("❌ Movie not found in search results.")
            return jsonify({"streams": []})

        movie_slug = search_data["results"][0].get("l")
        movie_page_url = f"{MAIN_URL}/{movie_slug}/"
        print(f"🔗 Found Movie Page: {movie_page_url}")
        
        movie_res = requests.get(movie_page_url, headers=HEADERS, verify=False, timeout=10)
        soup = BeautifulSoup(movie_res.text, 'html.parser')

        streams = []

        # Find all download containers
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
                    
                    print(f"\n[Bypass] Fetching: {decoded_url}")

                    cloud_res = requests.get(decoded_url, headers=HEADERS, verify=False, timeout=15)
                    cloud_soup = BeautifulSoup(cloud_res.text, 'html.parser')
                    
                    page_title = cloud_soup.title.string.strip() if cloud_soup.title else ""
                    if 'Just a moment' in page_title:
                        print("Blocked by Cloudflare")
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
                        except ValueError:
                            pass

                    if direct_link and direct_link.startswith('http'):
                        quality_match = re.search(r'(480p|720p|1080p|2160p|4K)', raw_title, re.IGNORECASE)
                        quality = quality_match.group(1) if quality_match else 'HD'
                        
                        clean_title = re.sub(r'(SD|HD|HEVC|480p|720p|1080p|2160p|4K|-2160p)', '', raw_title, flags=re.IGNORECASE)
                        clean_title = re.sub(r'\s+', ' ', clean_title).strip()

                        streams.append({
                            "name": f"CineFreak\n{quality}",
                            "title": f"▶ {clean_title}\n⚡ Direct Stream",
                            "url": direct_link
                        })
                        print(f"✅ Extracted Link: {quality}")
                
                except Exception as err:
                    print(f"[Error] Failed to resolve link: {err}")
                    
        print(f"\n🎯 Extracted Total {len(streams)} streams!")
        return jsonify({"streams": streams})

    except Exception as error:
        print(f"❌ Error: {error}")
        return jsonify({"streams": []})

if __name__ == '__main__':
    print(f"✅ CineFreak Python Addon Server LIVE on Port {PORT}!")
    print(f"🔗 Local Link: http://localhost:{PORT}/manifest.json")
    app.run(port=PORT, debug=True)

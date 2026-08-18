"""
MegaSource - HDHub4u Scraper
================================
Scraper para o addon MegaSource.
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import re
import urllib3
import json

# SSL വാണിംഗുകൾ ഒഴിവാക്കാൻ
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TITLE = "HDHub4u Scraper"
VERSION = "1.0.1"
DESCRIPTION = "Filmes do HDHub4u (Direct & m3u8)"

DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json"
MAIN_URL = "https://new2.moviesdrive.christmas"

# FlareSolverr ഉപയോഗിക്കുന്നുണ്ടെങ്കിൽ ഇവിടെ ലിങ്ക് നൽകാം (ഉദാ: "http://192.168.1.100:8191")
FLARESOLVERR_URL = "" 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": f"{MAIN_URL}/"
}

def fetch_and_update_domain():
    global MAIN_URL, HEADERS
    try:
        res = requests.get(DOMAINS_URL, verify=False, timeout=10)
        data = res.json()
        if data and data.get("HDHUB4u"):
            new_domain = data["HDHUB4u"]
            if new_domain != MAIN_URL:
                MAIN_URL = new_domain
                HEADERS["Referer"] = f"{MAIN_URL}/"
    except Exception:
        pass

def make_request(url):
    """
    FlareSolverr ലഭ്യമാണെങ്കിൽ അതുവഴി റിക്വസ്റ്റ് അയക്കുന്നു. അല്ലെങ്കിൽ സാധാരണ രീതിയിൽ.
    """
    if FLARESOLVERR_URL:
        try:
            payload = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": 60000
            }
            res = requests.post(f"{FLARESOLVERR_URL}/v1", json=payload, headers={'Content-Type': 'application/json'}, timeout=65)
            data = res.json()
            if data and data.get("solution") and data["solution"].get("response"):
                return data["solution"]["response"]
        except Exception:
            pass
            
    # Fallback (FlareSolverr ഇല്ലെങ്കിൽ)
    res = requests.get(url, headers=HEADERS, verify=False, timeout=15)
    return res.text

def unpack_js(p, a, c, k):
    """
    JavaScript `eval(function(p,a,c,k,e,d))` ഡീകോഡ് ചെയ്യാനുള്ള പൈത്തൺ ലോജിക്
    """
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    def to_base(n, base):
        if n == 0: return chars[0]
        res = ""
        while n > 0:
            res = chars[n % base] + res
            n //= base
        return res

    word_dict = {}
    for i in range(c):
        key = to_base(i, a)
        word_dict[key] = k[i] if i < len(k) and k[i] else key

    def repl(match):
        word = match.group(0)
        return word_dict.get(word, word)

    return re.sub(r'\b\w+\b', repl, p)

def resolve_hdstream4u(url):
    try:
        html = make_request(url)
        
        # 1. നേരിട്ട് m3u8 ഉണ്ടോയെന്ന് നോക്കുന്നു
        m3u8_match = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html, re.IGNORECASE)
        if m3u8_match:
            return m3u8_match.group(1)
            
        # 2. പാക്ക് ചെയ്ത (Packed) ഡാറ്റ ഉണ്ടോയെന്ന് നോക്കുന്നു
        packed_match = re.search(r"eval\(function\(p,a,c,k,e,d\).*?return p}\('((?:[^'\\]|\\.)*)',\s*(\d+)\s*,\s*(\d+)\s*,\s*'([^']*)'\.split\('\|'\)", html)
        if packed_match:
            p = packed_match.group(1).replace("\\'", "'").replace("\\\\", "\\")
            a = int(packed_match.group(2))
            c = int(packed_match.group(3))
            k = packed_match.group(4).split('|')
            
            unpacked = unpack_js(p, a, c, k)
            unpacked_match = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', unpacked, re.IGNORECASE)
            if unpacked_match:
                return unpacked_match.group(1)
    except Exception:
        pass
    return None

def resolve_hubdrive(url):
    try:
        html1 = make_request(url)
        soup1 = BeautifulSoup(html1, 'html.parser')
        
        hubcloud_tag = soup1.find(lambda tag: tag.name == 'a' and 'HubCloud Server' in tag.text)
        if not hubcloud_tag:
            hubcloud_tag = soup1.find('a', string=re.compile(r'HubCloud'))
        if not hubcloud_tag or not hubcloud_tag.has_attr('href'):
            return None
            
        html2 = make_request(hubcloud_tag['href'])
        soup2 = BeautifulSoup(html2, 'html.parser')
        gamerxyt_tag = soup2.find('a', id='download')
        if not gamerxyt_tag or not gamerxyt_tag.has_attr('href'):
            return None
            
        html3 = make_request(gamerxyt_tag['href'])
        soup3 = BeautifulSoup(html3, 'html.parser')
        fsl_tag = soup3.find('a', id='fsl')
        if fsl_tag and fsl_tag.has_attr('href'):
            return fsl_tag['href']
    except Exception:
        pass
    return None

def get_streams(media_type, media_id, config=None):
    """
    MegaSource ഫംഗ്ഷൻ: സ്ട്രീം ലിങ്കുകൾ കണ്ടെത്തുന്നു
    """
    if media_type != "movie":
        return []
        
    fetch_and_update_domain()
    imdb_id = media_id.split(':')[0]
    
    # Cinemeta-യിൽ നിന്നും സിനിമയുടെ പേര് എടുക്കുന്നു
    cinemeta_url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"
    try:
        meta_res = requests.get(cinemeta_url, timeout=10).json()
        movie_name = meta_res.get("meta", {}).get("name")
    except Exception:
        return []
        
    if not movie_name:
        return []

    # പുതിയ URL ഉപയോഗിച്ച് സെർച്ച് ചെയ്യുന്നു
    search_query = urllib.parse.quote(movie_name)
    search_url = f"{MAIN_URL}/search.html?q={search_query}"
    
    try:
        search_html = make_request(search_url)
        soup = BeautifulSoup(search_html, 'html.parser')
    except Exception:
        return []

    results = []
    movie_name_lower = movie_name.lower()

    # സിനിമയുടെ പേര് ഒത്തുനോക്കുന്ന ഫംഗ്ഷൻ (Title Matching)
    def is_match(title):
        title_lower = title.lower()
        if movie_name_lower in title_lower:
            return True
        return False

    for el in soup.find_all('figcaption'):
        a_tag = el.find('a')
        if a_tag:
            url = a_tag.get('href')
            title = a_tag.text.strip()
            if url and len(url) > 10 and is_match(title):
                results.append({"title": title, "url": url})

    if not results:
        for selector in ['article', '.post', '.result-item', '.search-result']:
            for el in soup.select(selector):
                a_tag = el.find('a')
                if a_tag:
                    url = a_tag.get('href')
                    title = a_tag.text.strip()
                    if url and len(url) > 10 and is_match(title):
                        abs_url = url if url.startswith('http') else f"{MAIN_URL}{'' if url.startswith('/') else '/'}{url}"
                        results.append({"title": title, "url": abs_url})

    if not results:
        return []

    movie_page_url = results[0]["url"]
    
    try:
        movie_html = make_request(movie_page_url)
        movie_soup = BeautifulSoup(movie_html, 'html.parser')
    except Exception:
        return []

    streams = []
    
    for a_tag in movie_soup.find_all('a', href=True):
        href = a_tag['href']
        text = a_tag.text.strip() or 'Link'
        
        if 'hdstream4u.com' in href or 'hubstream.art' in href:
            m3u8_url = resolve_hdstream4u(href)
            if m3u8_url:
                streams.append({
                    "name": "HDHub Stream",
                    "title": f"▶ m3u8 (Auto/Multi)\n📺 {text}",
                    "url": m3u8_url,
                    "behaviorHints": {
                        "notWebReady": True,
                        "proxyHeaders": {
                            "request": {
                                "User-Agent": HEADERS["User-Agent"],
                                "Referer": "https://hdstream4u.com/",
                                "Origin": "https://hdstream4u.com"
                            }
                        }
                    }
                })
        
        elif any(domain in href for domain in ['hubdrive.tips', 'hubcdn.sbs', 'greenmountmotors.com']):
            direct_link = resolve_hubdrive(href)
            if direct_link:
                quality_match = re.search(r'4K|1080p|720p|480p', text, re.IGNORECASE)
                quality_text = quality_match.group(0) if quality_match else "HD Download"
                streams.append({
                    "name": "HDHub Direct",
                    "title": f"⬇ {quality_text}\n💾 Direct FSL Link",
                    "url": direct_link
                })

    return streams

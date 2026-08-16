const express = require('express');
const { addonBuilder, getRouter } = require('stremio-addon-sdk');
const axios = require('axios');
const cheerio = require('cheerio');
const https = require('https');

const app = express();
const PORT = process.env.PORT || 7000;

// ==========================================
// 1. Dynamic Domain Settings
// ==========================================
let MAIN_URL = "https://cinefreak.nl"; 
const DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json";

const agent = new https.Agent({ rejectUnauthorized: false });

let HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": `${MAIN_URL}/`
};

async function fetchAndUpdateDomain() {
    try {
        const response = await axios.get(DOMAINS_URL, { httpsAgent: agent });
        if (response.data && response.data.cinefreak) {
            const newDomain = response.data.cinefreak;
            if (newDomain !== MAIN_URL) {
                console.log(`[Domain] Updating domain from ${MAIN_URL} to ${newDomain}`);
                MAIN_URL = newDomain;
                HEADERS.Referer = `${MAIN_URL}/`;
            }
        }
    } catch (e) {
        console.error("[Domain] Failed to fetch domains.", e.message);
    }
}

// ==========================================
// 2. Stremio Manifest
// ==========================================
const manifest = {
    id: 'org.cinefreak.streams',
    version: '1.0.3',
    name: 'CineFreak Streamer',
    description: 'Direct Fast Streaming Addon for CineFreak',
    resources: ['stream'], 
    types: ['movie', 'series'],
    catalogs: [], 
    idPrefixes: ['tt'] 
};

const builder = new addonBuilder(manifest);

// ==========================================
// 3. Stream Handler
// ==========================================
builder.defineStreamHandler(async (args) => {
    console.log(`\n================================`);
    console.log(`🎬 [START] Request for ID: ${args.id}`);
    
    try {
        await fetchAndUpdateDomain();

        let imdbId = args.id.split(':')[0];
        const cinemetaUrl = `https://v3-cinemeta.strem.io/meta/${args.type}/${imdbId}.json`;
        const metaRes = await axios.get(cinemetaUrl);
        const movieName = metaRes.data?.meta?.name;

        if (!movieName) return { streams: [] };
        console.log(`✅ Title Found: ${movieName}`);

        const searchQuery = encodeURIComponent(movieName);
        const searchApiUrl = `${MAIN_URL}/search-api.php?q=${searchQuery}&pg=1&_t=${Date.now()}`;
        console.log(`[Search] API: ${searchApiUrl}`);
        
        const searchRes = await axios.get(searchApiUrl, { headers: HEADERS, httpsAgent: agent });
        const searchData = searchRes.data;

        if (!searchData || !searchData.results || searchData.results.length === 0) {
            console.log("❌ Movie not found in search results.");
            return { streams: [] };
        }

        let movieSlug = searchData.results[0].l; 
        let moviePageUrl = `${MAIN_URL}/${movieSlug}/`;
        console.log(`🔗 Found Movie Page: ${moviePageUrl}`);
        
        const movieRes = await axios.get(moviePageUrl, { headers: HEADERS, httpsAgent: agent });
        const $movie = cheerio.load(movieRes.data);

        let streams = [];
        let extractTasks = [];

        $movie('.dlbtn-container').each((i, el) => {
            const rawTitle = $movie(el).prev('h4.movie-title').text().replace(/\s+/g, ' ').trim() || `Link ${i+1}`;
            
            const watchBtn = $movie(el).find('.dlbtn-watch').attr('href');
            const downloadBtn = $movie(el).find('.dlbtn-download').attr('href');
            const targetBtn = downloadBtn || watchBtn; 

            if (targetBtn && targetBtn.includes('generate.php?id=')) {
                extractTasks.push(async () => {
                    try {
                        const encodedId = targetBtn.split('id=')[1];
                        let decodedUrl = Buffer.from(encodedId, 'base64').toString('utf-8');
                        decodedUrl = decodedUrl.replace('newgo32', '');
                        
                        console.log(`\n[Bypass] Fetching: ${decodedUrl}`);

                        const cloudRes = await axios.get(decodedUrl, { headers: HEADERS, httpsAgent: agent });
                        const $cloud = cheerio.load(cloudRes.data);
                        
                        const pageTitle = $cloud('title').text().trim();
                        if (pageTitle.includes('Just a moment')) return; // Blocked by Cloudflare

                        const csrfToken = $cloud('meta[name="X-CSRF-TOKEN"]').attr('content');
                        const cookies = cloudRes.headers['set-cookie'] ? cloudRes.headers['set-cookie'].map(c => c.split(';')[0]).join('; ') : '';

                        let directLink = null;

                        directLink = $cloud('a.fsl-btn').attr('href') || $cloud('a.download-now').attr('href');
                        
                        if (!directLink || !directLink.startsWith('http')) {
                            $cloud('a').each((_, a) => {
                                const href = $cloud(a).attr('href');
                                if (href && (href.match(/\.(mkv|mp4)/i) || href.includes('r2.dev') || href.includes('r2.cloudflarestorage'))) {
                                    directLink = href;
                                }
                            });
                        }

                        if (!directLink && csrfToken) {
                            let postUrl = decodedUrl;
                            if (decodedUrl.includes('/x/')) postUrl = decodedUrl.replace('/x/', '/w/'); 
                            else if (decodedUrl.includes('/f/')) postUrl = decodedUrl.replace('/f/', '/fastdl/'); 

                            const postRes = await axios.post(postUrl, `csrf_test_name=${csrfToken}`, {
                                headers: {
                                    ...HEADERS,
                                    'Cookie': cookies,
                                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'Referer': decodedUrl
                                },
                                httpsAgent: agent
                            });
                            
                            if (postRes.data && postRes.data.url) {
                                directLink = postRes.data.url;
                            }
                        }

                        if (directLink && directLink.startsWith('http')) {
                            // --- Formatting Title for Stremio UI (പുതിയ തിരുത്തൽ) ---
                            let qualityMatch = rawTitle.match(/(480p|720p|1080p|2160p|4K)/i);
                            let quality = qualityMatch ? qualityMatch[1] : 'HD';
                            
                            // സിനിമയുടെ പേരിൽ നിന്ന് ക്വാളിറ്റിയും, SD, HD, HEVC തുടങ്ങിയ വാക്കുകളും ഒഴിവാക്കുന്നു
                            let cleanTitle = rawTitle.replace(/(SD|HD|HEVC|480p|720p|1080p|2160p|4K|-2160p)/ig, '').replace(/\s+/g, ' ').trim();

                            streams.push({
                                name: `CineFreak\n${quality}`,
                                title: `▶ ${cleanTitle}\n⚡ Direct Stream`,
                                url: directLink
                            });
                            console.log(`✅ Extracted Link: ${quality}`);
                        }
                    } catch (err) {
                        console.log(`[Error] Failed to resolve link: ${err.message}`);
                    }
                });
            }
        });

        for (let task of extractTasks) {
            await task();
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        console.log(`\n🎯 Extracted Total ${streams.length} streams!`);
        return { streams };

    } catch (error) {
        console.error("❌ Error:", error.message);
        return { streams: [] };
    }
});

// ==========================================
// 4. Server Start
// ==========================================
app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Headers', '*');
    next();
});

app.use(getRouter(builder.getInterface()));

app.listen(PORT, () => {
    console.log(`✅ CineFreak Addon Server LIVE on Port ${PORT}!`);
    console.log(`🔗 Local Link: http://localhost:${PORT}/manifest.json`);
});
const express = require('express');
const { addonBuilder, getRouter } = require('stremio-addon-sdk');
const axios = require('axios');
const cheerio = require('cheerio');
const https = require('https');

const app = express();
const PORT = process.env.PORT || 7000;

// ==========================================
// 1. Dynamic Domain & Proxy Settings
// ==========================================
let MAIN_URL = "https://cinefreak.nl"; 
const DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json";
const FLARESOLVERR_URL = process.env.FLARESOLVERR_URL || '';

const agent = new https.Agent({ rejectUnauthorized: false });

let HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": `${MAIN_URL}/`
};

// ഡൈനാമിക് ആയി വെബ്സൈറ്റിന്റെ URL കണ്ടുപിടിക്കാൻ
let BASE_URL = `http://localhost:${PORT}`;
app.use((req, res, next) => {
    BASE_URL = `${req.protocol}://${req.get('host')}`;
    next();
});

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
    version: '1.0.5',
    name: 'CineFreak Streamer',
    description: 'Direct Fast Streaming Addon for CineFreak',
    resources: ['stream'], 
    types: ['movie', 'series'],
    catalogs: [], 
    idPrefixes: ['tt'] 
};

const builder = new addonBuilder(manifest);

// ==========================================
// 3. Stream Handler (Fast Load)
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
        
        const searchRes = await axios.get(searchApiUrl, { headers: HEADERS, httpsAgent: agent });
        const searchData = searchRes.data;

        if (!searchData || !searchData.results || searchData.results.length === 0) {
            console.log("❌ Movie not found.");
            return { streams: [] };
        }

        let movieSlug = searchData.results[0].l; 
        let moviePageUrl = `${MAIN_URL}/${movieSlug}/`;
        
        const movieRes = await axios.get(moviePageUrl, { headers: HEADERS, httpsAgent: agent });
        const $movie = cheerio.load(movieRes.data);

        let streams = [];

        // ഇവിടെ വെയിറ്റിംഗ് ഇല്ല, ലിങ്കുകൾ നേരിട്ട് ആഡ് ചെയ്യുന്നു
        $movie('.dlbtn-container').each((i, el) => {
            const rawTitle = $movie(el).prev('h4.movie-title').text().replace(/\s+/g, ' ').trim() || `Link ${i+1}`;
            const watchBtn = $movie(el).find('.dlbtn-watch').attr('href');
            const downloadBtn = $movie(el).find('.dlbtn-download').attr('href');
            const targetBtn = downloadBtn || watchBtn; 

            if (targetBtn && targetBtn.includes('generate.php?id=')) {
                const encodedId = targetBtn.split('id=')[1];
                let decodedUrl = Buffer.from(encodedId, 'base64').toString('utf-8').replace('newgo32', '');
                
                let qualityMatch = rawTitle.match(/(480p|720p|1080p|2160p|4K)/i);
                let quality = qualityMatch ? qualityMatch[1] : 'HD';
                let cleanTitle = rawTitle.replace(/(SD|HD|HEVC|480p|720p|1080p|2160p|4K|-2160p)/ig, '').replace(/\s+/g, ' ').trim();

                // പ്ലേ ചെയ്യാൻ നമ്മുടെ സ്വന്തം /play റൂട്ടിലേക്ക് തിരിച്ചുവിടുന്നു
                streams.push({
                    name: `CineFreak\n${quality}`,
                    title: `▶ ${cleanTitle}\n⚡ Direct Stream`,
                    url: `${BASE_URL}/play?target=${encodeURIComponent(decodedUrl)}`
                });
            }
        });

        console.log(`🎯 Quickly Extracted ${streams.length} streams!`);
        return { streams };

    } catch (error) {
        console.error("❌ Error:", error.message);
        return { streams: [] };
    }
});

// ==========================================
// 4. On-Demand Stream Resolver (Redirect)
// ==========================================
app.get('/play', async (req, res) => {
    const targetUrl = req.query.target;
    if (!targetUrl) return res.status(400).send("No target URL provided.");

    console.log(`\n▶️ [PLAY CLICKED] Resolving: ${targetUrl}`);
    let directLink = null;

    try {
        if (FLARESOLVERR_URL) {
            console.log(`[Proxy] Using FlareSolverr...`);
            let sessionId = `sess_${Date.now()}`;
            try {
                await axios.post(`${FLARESOLVERR_URL}/v1`, { cmd: 'sessions.create', session: sessionId });
                let getRes = await axios.post(`${FLARESOLVERR_URL}/v1`, { cmd: 'request.get', url: targetUrl, session: sessionId, maxTimeout: 60000 });
                let $cloud = cheerio.load(getRes.data.solution.response);
                
                let csrfToken = $cloud('meta[name="X-CSRF-TOKEN"]').attr('content');
                directLink = $cloud('a.fsl-btn').attr('href') || $cloud('a.download-now').attr('href');
                
                if (!directLink || !directLink.startsWith('http')) {
                    $cloud('a').each((_, a) => {
                        const href = $cloud(a).attr('href');
                        if (href && (href.match(/\.(mkv|mp4)/i) || href.includes('r2.dev') || href.includes('r2.cloudflarestorage'))) directLink = href;
                    });
                }

                if (!directLink && csrfToken) {
                    console.log(`[CSRF] Sending POST request via FlareSolverr...`);
                    let postUrl = targetUrl.includes('/x/') ? targetUrl.replace('/x/', '/w/') : targetUrl.replace('/f/', '/fastdl/'); 
                    let postRes = await axios.post(`${FLARESOLVERR_URL}/v1`, { 
                        cmd: 'request.post', url: postUrl, session: sessionId, postData: `csrf_test_name=${csrfToken}`,
                        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest" }, maxTimeout: 60000 
                    });
                    
                    let postText = cheerio.load(postRes.data.solution.response)('body').text();
                    try {
                        let parsed = JSON.parse(postText);
                        if (parsed.url) directLink = parsed.url;
                    } catch(e) {
                        let jsonMatch = postText.match(/["']?url["']?\s*:\s*["'](https?:\/\/[^"']+)["']/i);
                        if (jsonMatch) directLink = jsonMatch[1].replace(/\\\//g, '/');
                    }
                }
            } finally {
                await axios.post(`${FLARESOLVERR_URL}/v1`, { cmd: 'sessions.destroy', session: sessionId }).catch(()=>{});
            }
        } else {
            console.log(`[Local] Direct fetching...`);
            const cloudRes = await axios.get(targetUrl, { headers: HEADERS, httpsAgent: agent });
            const $cloud = cheerio.load(cloudRes.data);
            const csrfToken = $cloud('meta[name="X-CSRF-TOKEN"]').attr('content');
            const cookies = cloudRes.headers['set-cookie'] ? cloudRes.headers['set-cookie'].map(c => c.split(';')[0]).join('; ') : '';

            directLink = $cloud('a.fsl-btn').attr('href') || $cloud('a.download-now').attr('href');
            if (!directLink || !directLink.startsWith('http')) {
                $cloud('a').each((_, a) => {
                    const href = $cloud(a).attr('href');
                    if (href && (href.match(/\.(mkv|mp4)/i) || href.includes('r2.dev') || href.includes('r2.cloudflarestorage'))) directLink = href;
                });
            }

            if (!directLink && csrfToken) {
                console.log(`[CSRF] Sending POST request...`);
                let postUrl = targetUrl.includes('/x/') ? targetUrl.replace('/x/', '/w/') : targetUrl.replace('/f/', '/fastdl/'); 
                const postRes = await axios.post(postUrl, `csrf_test_name=${csrfToken}`, {
                    headers: { ...HEADERS, 'Cookie': cookies, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest', 'Referer': targetUrl },
                    httpsAgent: agent
                });
                if (postRes.data && postRes.data.url) directLink = postRes.data.url;
            }
        }

        if (directLink && directLink.startsWith('http')) {
            console.log(`✅ Redirecting to Stream...`);
            res.redirect(directLink);
        } else {
            console.log(`❌ Stream Link Not Found!`);
            res.status(404).send("Stream not found. The link might be broken or blocked.");
        }
    } catch (e) {
        console.error(`[Play Error] ${e.message}`);
        res.status(500).send("Error resolving stream");
    }
});

// ==========================================
// 5. Server Start
// ==========================================
app.use(getRouter(builder.getInterface()));

app.listen(PORT, () => {
    console.log(`✅ CineFreak Addon Server LIVE on Port ${PORT}!`);
    console.log(`🔗 Local Link: http://localhost:${PORT}/manifest.json`);
});

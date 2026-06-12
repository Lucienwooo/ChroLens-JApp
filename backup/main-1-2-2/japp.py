import os
import sys
import time

# Disable web security to allow cross-origin iframe DOM access for Range Replay feature
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-web-security --disable-site-isolation-trials'

import json
import webview
import urllib.request
import urllib.parse
import re
import concurrent.futures
import threading
import datetime
import base64
import queue
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

VERSION = "1.2.2"
proxy_port = 32569
GLOBAL_API = None
AVWIKI_CACHE = {}
TKTUBE_EXTRACTS = {}

def safe_print(*args, **kwargs):
    if not sys.is_finalizing():
        try:
            print(*args, **kwargs)
        except:
            pass

def get_resource_path():
    """ 取得打包在 exe 內的唯讀資源路徑 (HTML, CSS, JS 等) """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_data_path():
    """ 取得持久化資料庫儲存路徑 (確保與打包後的 exe 同目錄，並優先相容本機 dist 目錄) """
    base_dir = os.path.dirname(sys.executable) if hasattr(sys, 'frozen') else os.path.dirname(os.path.abspath(__file__))
    dist_path = os.path.join(base_dir, 'dist')
    if os.path.exists(os.path.join(dist_path, 'Favorites.json')):
        return dist_path
    return base_dir

def clean_code(raw_code):
    if not raw_code:
        return ""
    c = raw_code.strip().lower()
    # Remove anything in brackets or parentheses (e.g. (無碼洩露) or （合演）)
    c = re.sub(r'[\(\uff08].*?[\)\uff09]', '', c)
    # Remove common garbage suffixes at the end
    c = re.sub(r'-(ub|uncensored|leaked|破解版|正常版)$', '', c)
    # Remove trailing 'v' if it is preceded by a number (e.g. start-423v -> start-423)
    c = re.sub(r'([0-9]+)v$', r'\1', c)
    
    # Special handle for FC2
    if 'fc2' in c:
        fc2_match = re.search(r'(fc2-ppv-\d+|fc2-\d+)', c)
        if fc2_match:
            return fc2_match.group(1)
            
    # Extract the core JAV code: letters/numbers, dash, then numbers
    matches = re.findall(r'([a-z0-9]+-[0-9]+)', c)
    if matches:
        return matches[-1]
    
    # Fallback: clean all non-alphanumeric except dash
    c = re.sub(r'[^a-z0-9\-]', '', c)
    return c

def fetch_html_content(url):
    # Proactively check if we need Playwright (Cloudflare bypass)
    needs_playwright = any(domain in url for domain in ["javhdporn.net", "supjav.com", "jable.tv", "missav.ws", "javbus.com"])
    if needs_playwright and GLOBAL_API:
        try:
            html = GLOBAL_API.playwright_fetch_html(url)
            if html:
                return True, html
        except Exception as pe:
            safe_print(f"Playwright fetch fallback failed for {url}: {pe}")
            
    import urllib.error
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Referer': 'https://tktube.com/' if 'tktube.com' in url else ('https://tcav.85xvideo.com/' if 'tcav.85xvideo.com' in url else 'https://google.com/')
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return True, r.read().decode('utf-8', errors='ignore')
    except Exception as urllib_err:
        return False, ""

def fetch_url(url):
    success, html = fetch_html_content(url)
    if not success:
        return False, "", "未知"
    poster_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not poster_match:
        poster_match = re.search(r'poster=["\']([^"\']+)["\']', html, re.IGNORECASE)
    img_url = poster_match.group(1) if poster_match else ""
    
    # Extract actress name from details page HTML if available
    actress_name = "未知"
    actress_sec = re.search(r'<div>\s*<label>(?:女演員|女演员|Actresses|女优|女優):?</label>\s*(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
    if actress_sec:
        content = actress_sec.group(1)
        actresses = re.findall(r'<a href="[^"]*/actresses/[^"]+">([^<]+)</a>', content)
        if actresses:
            actress_name = ", ".join(a.strip() for a in actresses)
        else:
            plain = re.sub(r'<[^>]+>', '', content).strip()
            if plain:
                actress_name = plain
            
    return True, img_url, actress_name

def strip_ads(html):
    html = re.sub(r'<script[^>]*?src=["\'][^"\']*?(exoclick|juicyads|trafficjunky|adspyglass|popcash|popunder|clkmon|clkrev|hilltopads|propellerads|adcash|adhese|adnxs|tsyndicate)[^"\']*?["\'][^>]*>.*?</script>', '', html, flags=re.IGNORECASE|re.DOTALL)
    html = re.sub(r'<iframe[^>]*?src=["\'][^"\']*?(exoclick|juicyads|trafficjunky|adspyglass|popcash|popunder|clkmon|clkrev|hilltopads|propellerads|adcash|adhese|adnxs|tsyndicate)[^"\']*?["\'][^>]*>.*?</iframe>', '', html, flags=re.IGNORECASE|re.DOTALL)
    return html

class VideoProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        try:
            parsed_path = urlparse(self.path)
            qs = parse_qs(parsed_path.query)
            
            if '/javhdporn_proxy' in parsed_path.path:
                url_param = qs.get('url', [''])[0]
                if url_param:
                    target_url = base64.b64decode(url_param).decode('utf-8')
                    html = GLOBAL_API.playwright_fetch_html(target_url) if GLOBAL_API else None
                    if not html:
                        success, fallback_html = fetch_html_content(target_url)
                        if success:
                            html = fallback_html
                    if html:
                        html = re.sub(r'<a\s+[^>]*href=[\'"][^\'"]*(prefecture|ad|trk)[^\'"]*[\'"][^>]*>.*?</a>', '', html, flags=re.IGNORECASE|re.DOTALL)
                        blocker_js = f"""
                        <script>
                            (function() {{
                                window.Worker = undefined;
                                window.open = function() {{ return null; }};
                                window.onbeforeunload = null;
                                if (window.Hls) {{
                                    window.Hls.DefaultConfig = window.Hls.DefaultConfig || {{}};
                                    window.Hls.DefaultConfig.enableWorker = false;
                                }}
                                
                                // Auto-click play button
                                document.addEventListener("DOMContentLoaded", function() {{
                                    var poller = setInterval(function() {{
                                        var btn = document.getElementById("vserver") || document.querySelector(".play-button") || document.querySelector(".vjs-big-play-button");
                                        if (btn) {{
                                            try {{
                                                btn.click();
                                                clearInterval(poller);
                                            }} catch(e){{}}
                                        }}
                                        // Remove any invisible overlay ad layers
                                        document.querySelectorAll('a[target="_blank"], div[style*="z-index:"]').forEach(el => {{
                                            if(!el.closest('#video-player') && !el.closest('.responsive-player')) {{
                                                const z = parseInt(window.getComputedStyle(el).zIndex);
                                                if(z > 900) el.remove();
                                            }}
                                        }});
                                    }}, 500);
                                    setTimeout(function() {{ clearInterval(poller); }}, 10000);
                                    
                                    // Intercept iframe element creation to proxy surrit.store
                                    const originalCreateElement = document.createElement;
                                    document.createElement = function(tagName, options) {{
                                        const element = originalCreateElement.call(document, tagName, options);
                                        if (tagName.toLowerCase() === 'iframe') {{
                                            const originalSetAttribute = element.setAttribute;
                                            element.setAttribute = function(name, value) {{
                                                if (name.toLowerCase() === 'src' && value && value.includes('surrit.store')) {{
                                                    const encoded = btoa(value);
                                                    value = `http://127.0.0.1:{proxy_port}/surrit_proxy?url=${{encoded}}`;
                                                }}
                                                originalSetAttribute.call(this, name, value);
                                            }};
                                            Object.defineProperty(element, 'src', {{
                                                set: function(val) {{
                                                    if (val && val.includes('surrit.store')) {{
                                                        const encoded = btoa(val);
                                                        val = `http://127.0.0.1:{proxy_port}/surrit_proxy?url=${{encoded}}`;
                                                    }}
                                                    originalSetAttribute.call(this, 'src', val);
                                                }},
                                                get: function() {{
                                                    return this.getAttribute('src');
                                                }},
                                                configurable: true
                                            }});
                                        }}
                                        return element;
                                    }};
                                }});
                            }})();
                        </script>
                        """
                        custom_css = """
                        <style>
                            header, footer, .sidebar, .video-infos, .related-videos, .under-player-ad-mobile, .above-player-ad, #comments, .site-branding, #masthead, .watch-wrap .sidebar, .entry-header, .ad-container, .adsbygoogle {
                                display: none !important;
                            }
                            
                            /* Block all transparent overlays that intercept clicks */
                            a[target="_blank"], div[style*="z-index: 999"], div[style*="z-index: 2147483647"]:not(#video-player) {
                                display: none !important;
                                pointer-events: none !important;
                            }

                            html, body, #page, #content, .container, .watch-wrap, .main, .video-player-area, #video-player-area, #video-player, .responsive-player {
                                margin: 0 !important;
                                padding: 0 !important;
                                width: 100vw !important;
                                height: 100vh !important;
                                max-width: 100vw !important;
                                max-height: 100vh !important;
                                overflow: hidden !important;
                                background: #000 !important;
                            }
                            #video-player, #video-player iframe, #video-player video, .responsive-player iframe {
                                position: fixed !important;
                                top: 0 !important;
                                left: 0 !important;
                                width: 100vw !important;
                                height: 100vh !important;
                                z-index: 2147483647 !important;
                                pointer-events: auto !important;
                            }
                        </style>
                        """
                        html = html.replace('<head>', '<head>' + blocker_js + custom_css)
                        encoded = html.encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return
                self.send_error(404)
                
            elif '/supjav_proxy' in parsed_path.path:
                url_param = qs.get('url', [''])[0]
                if url_param:
                    target_url = base64.b64decode(url_param).decode('utf-8')
                    html = GLOBAL_API.playwright_fetch_html(target_url) if GLOBAL_API else None
                    if not html:
                        success, fallback_html = fetch_html_content(target_url)
                        if success:
                            html = fallback_html
                    if html:
                        blocker_js = """
                        <script>
                            (function() {
                                window.Worker = undefined;
                                window.open = function() { return null; };
                                window.onbeforeunload = null;
                                if (window.Hls) {
                                    window.Hls.DefaultConfig = window.Hls.DefaultConfig || {};
                                    window.Hls.DefaultConfig.enableWorker = false;
                                }
                                
                                // Auto-click play button
                                document.addEventListener("DOMContentLoaded", function() {
                                    var poller = setInterval(function() {
                                        var btn = document.getElementById("vserver") || document.querySelector(".play-button") || document.querySelector(".vjs-big-play-button");
                                        if (btn) {
                                            try {
                                                btn.click();
                                                clearInterval(poller);
                                            } catch(e){}
                                        }
                                        // Remove any invisible overlay ad layers
                                        document.querySelectorAll('a[target="_blank"], div[style*="z-index:"]').forEach(el => {
                                            if(!el.closest('#dz_video') && !el.closest('#player-wrap')) {
                                                const z = parseInt(window.getComputedStyle(el).zIndex);
                                                if(z > 900) el.remove();
                                            }
                                        });
                                    }, 500);
                                    setTimeout(function() { clearInterval(poller); }, 10000);
                                });
                            })();
                        </script>
                        """
                        custom_css = """
                        <style>
                            header, footer, .sidebar, .video-wrap .left .archive-title, .dz_view, .post-meta, #comments, .movv-ad, iframe[src*="go.bluetrafficstream.com"], iframe[src*="go.mnaspm.com"], .ad-container {
                                display: none !important;
                            }

                            /* Block all transparent overlays that intercept clicks */
                            a[target="_blank"], .player-overlay, div[style*="z-index: 999"], div[style*="z-index: 2147483647"]:not(#dz_video):not(#player-wrap) {
                                display: none !important;
                                pointer-events: none !important;
                            }

                            html, body, #app, main, .container, .video-wrap, .left, #dz_video, #player-wrap, #player-wrap iframe {
                                margin: 0 !important;
                                padding: 0 !important;
                                width: 100vw !important;
                                height: 100vh !important;
                                max-width: 100vw !important;
                                max-height: 100vh !important;
                                overflow: hidden !important;
                                background: #000 !important;
                            }
                            #dz_video, #player-wrap, #player-wrap iframe, #dz_video iframe, #dz_video video {
                                position: fixed !important;
                                top: 0 !important;
                                left: 0 !important;
                                width: 100vw !important;
                                height: 100vh !important;
                                z-index: 2147483647 !important;
                                pointer-events: auto !important;
                            }
                        </style>
                        """
                        html = html.replace('<head>', '<head>' + blocker_js + custom_css)
                        encoded = html.encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return
                self.send_error(404)
                
            elif '/surrit_proxy' in parsed_path.path:
                url_param = qs.get('url', [''])[0]
                if url_param:
                    try:
                        target_url = base64.b64decode(url_param).decode('utf-8')
                    except Exception:
                        target_url = urllib.parse.unquote(url_param)
                    html = GLOBAL_API.playwright_fetch_html(target_url) if GLOBAL_API else None
                    if not html:
                        success, fallback_html = fetch_html_content(target_url)
                        if success:
                            html = fallback_html
                    if html:
                        disable_worker_js = """
                        <script>
                            window.Worker = undefined;
                            window.open = function() { return null; };
                            window.onbeforeunload = null;
                            if (window.Hls) {
                                window.Hls.DefaultConfig = window.Hls.DefaultConfig || {};
                                window.Hls.DefaultConfig.enableWorker = false;
                            }
                        </script>
                        """
                        html = html.replace('<head>', '<head><base href="https://surrit.store/">' + disable_worker_js)
                        encoded = html.encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return
                
            elif '/missav_proxy' in parsed_path.path:
                url_param = qs.get('url', [''])[0]
                if url_param:
                    target_url = base64.b64decode(url_param).decode('utf-8')
                    html = GLOBAL_API.playwright_fetch_html(target_url) if GLOBAL_API else None
                    if not html:
                        success, fallback_html = fetch_html_content(target_url)
                        if success:
                            html = fallback_html
                    if html:
                        html = strip_ads(html)
                        html = html.replace('<head>', '<head><base href="https://missav.ws/"><script>window.open=function(){return null;};window.onbeforeunload=null;</script>')
                        encoded = html.encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return
                self.send_error(404)
                
            elif '/tktube_loader' in parsed_path.path:
                task_id = qs.get('id', [''])[0]
                fallback_param = qs.get('fallback', [''])[0]
                fallback_url = base64.b64decode(fallback_param).decode('utf-8') if fallback_param else ""
                
                loader_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>載入中...</title>
    <style>
        body, html {{
            margin: 0; padding: 0; width: 100%; height: 100%;
            background: #121212; color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            overflow: hidden;
        }}
        .spinner {{
            width: 50px; height: 50px;
            border: 5px solid rgba(255,255,255,0.1);
            border-radius: 50%;
            border-top-color: #ff9800;
            animation: spin 1s ease-in-out infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .text {{
            margin-top: 20px;
            font-size: 14px;
            letter-spacing: 1px;
            color: #aaa;
        }}
    </style>
</head>
<body>
    <div class="spinner"></div>
    <div class="text">自動跳過廣告中，請稍候...</div>
    <script>
        const taskId = "{task_id}";
        const fallbackUrl = "{fallback_url}";
        
        async function checkStatus() {{
            try {{
                const res = await fetch(`/tktube_status?id=${{taskId}}`);
                const data = await res.json();
                if (data.status === "ready") {{
                    const streamUrl = data.url;
                    let playerHtml = "";
                    if (streamUrl.includes(".m3u8")) {{
                        playerHtml = `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
    <style>
        body, html {{ margin:0; padding:0; width:100%; height:100%; background:#000; overflow:hidden; }}
        video {{ width:100%; height:100%; object-fit:contain; }}
    </style>
</head>
<body>
    <video id="video" controls autoplay playsinline></video>
    <script>
        var video = document.getElementById('video');
        var videoSrc = '${{streamUrl}}';
        if (Hls.isSupported()) {{
            var hls = new Hls({{
                maxBufferLength: 60,
                maxMaxBufferLength: 120,
                enableWorker: true,
                lowLatencyMode: true
            }});
            hls.loadSource(videoSrc);
            hls.attachMedia(video);
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = videoSrc;
        }}
    \\/script>
</body>
</html>`;
                    }} else {{
                        playerHtml = `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body, html {{ margin:0; padding:0; width:100%; height:100%; background:#000; overflow:hidden; }}
        video {{ width:100%; height:100%; object-fit:contain; }}
    </style>
</head>
<body>
    <video id="video" src="${{streamUrl}}" controls autoplay playsinline></video>
</body>
</html>`;
                    }}
                    
                    document.open();
                    document.write(playerHtml);
                    document.close();
                }} else if (data.status === "error") {{
                    console.log("Extraction failed, loading fallback direct embed...");
                    const encodedFallback = btoa(fallbackUrl);
                    window.location.replace(`/tktube_proxy?url=${{encodeURIComponent(encodedFallback)}}`);
                }} else {{
                    setTimeout(checkStatus, 500);
                }}
            }} catch (e) {{
                console.error("Status check failed:", e);
                setTimeout(checkStatus, 1000);
            }}
        }}
        
        checkStatus();
    </script>
</body>
</html>"""
                encoded = loader_html.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return

            elif '/tktube_status' in parsed_path.path:
                task_id = qs.get('id', [''])[0]
                res_data = {"status": "pending"}
                if task_id in TKTUBE_EXTRACTS:
                    res_url = TKTUBE_EXTRACTS[task_id]
                    if res_url == "error" or not res_url:
                        res_data = {"status": "error"}
                    else:
                        res_data = {"status": "ready", "url": res_url}
                
                res_json = json.dumps(res_data).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(res_json)))
                self.end_headers()
                self.wfile.write(res_json)
                return

            elif '/tktube_proxy' in parsed_path.path:
                url_param = qs.get('url', [''])[0]
                if url_param:
                    target_url = base64.b64decode(url_param).decode('utf-8')
                    m = re.search(r'/embed/([0-9]+)/', target_url)
                    video_id = m.group(1) if m else "0"
                    official_embed_url = f"https://tktube.com/zh/embed/{video_id}/"
                    
                    # === ALWAYS Fallback to HTML injection for same-origin DOM access and zero Playwright latency ===
                    video_url = None
                    
                    # === FALLBACK: Serve embed HTML with ad-killer injection ===
                    safe_print(f"[TKTube] Serving HTML injection for {video_id}")
                    html = fetch_html_content(target_url)[1] if fetch_html_content(target_url)[0] else None
                    
                    if html:
                        # 1. 嘗試直接提取串流 URL (Method 1)
                        video_url_match = re.search(r"video_url:\s*['\"]([^'\"]+)['\"]", html)
                        if video_url_match:
                            video_url = video_url_match.group(1)
                            video_alt_url_match = re.search(r"video_alt_url:\s*['\"]([^'\"]+)['\"]", html)
                            video_alt_url = video_alt_url_match.group(1) if video_alt_url_match else ""
                            preview_url_match = re.search(r"preview_url:\s*['\"]([^'\"]+)['\"]", html)
                            preview_url = preview_url_match.group(1) if preview_url_match else ""
                            video_title_match = re.search(r"video_title:\s*['\"]([^'\"]+)['\"]", html)
                            video_title = video_title_match.group(1) if video_title_match else "JApp Player"
                            
                            # 安全地清理標題特殊字元，避免破壞 HTML
                            video_title_escaped = video_title.replace('"', '&quot;').replace("'", "&#39;")
                            
                            def proxy_url_direct(orig_url):
                                if not orig_url:
                                    return ""
                                if orig_url.startswith('/'):
                                    orig_url = "https://tktube.com" + orig_url
                                encoded_url = base64.b64encode(orig_url.encode('utf-8')).decode('utf-8')
                                return f"http://127.0.0.1:{proxy_port}/?url={encoded_url}"
                                
                            video_url_encoded = proxy_url_direct(video_url)
                            video_alt_encoded = proxy_url_direct(video_alt_url)
                            
                            custom_player_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{video_title_escaped}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: #000;
            overflow: hidden;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        video {{
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
            background-color: #000;
            outline: none;
        }}
        .controls-overlay {{
            position: absolute;
            top: 15px;
            right: 15px;
            z-index: 100;
            display: flex;
            gap: 8px;
        }}
        .quality-btn {{
            background: rgba(0, 0, 0, 0.7);
            color: #ccc;
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-weight: 500;
            transition: all 0.2s ease;
            backdrop-filter: blur(4px);
        }}
        .quality-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            border-color: rgba(255, 255, 255, 0.5);
        }}
        .quality-btn.active {{
            background: #ff5500;
            color: #fff;
            border-color: #ff5500;
            box-shadow: 0 0 8px rgba(255, 85, 0, 0.5);
        }}
    </style>
</head>
<body>
    <div class="controls-overlay" id="qualityOverlay"></div>
    <video id="player" controls autoplay playsinline poster="{preview_url}">
        <source id="videoSource" src="{video_url_encoded}" type="video/mp4">
        Your browser does not support the video tag.
    </video>
    <script>
        const video = document.getElementById('player');
        const source = document.getElementById('videoSource');
        const qualityOverlay = document.getElementById('qualityOverlay');
        
        const qualities = [];
        const sdUrl = "{video_url_encoded}";
        const hdUrl = "{video_alt_encoded}";
        
        if (sdUrl) qualities.push({{ label: 'SD', url: sdUrl }});
        if (hdUrl) qualities.push({{ label: 'HD', url: hdUrl }});
        
        if (qualities.length > 1) {{
            qualities.forEach(q => {{
                const btn = document.createElement('button');
                btn.className = 'quality-btn';
                btn.innerText = q.label;
                
                const defaultHD = qualities.find(x => x.label === 'HD');
                const defaultLabel = defaultHD ? 'HD' : 'SD';
                if (q.label === defaultLabel) {{
                    btn.classList.add('active');
                }}
                
                btn.onclick = () => {{
                    document.querySelectorAll('.quality-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    const currentTime = video.currentTime;
                    const isPaused = video.paused;
                    source.src = q.url;
                    video.load();
                    video.currentTime = currentTime;
                    if (!isPaused) {{
                        video.play().catch(() => {{}});
                    }}
                }};
                qualityOverlay.appendChild(btn);
            }});
        }}
        
        if (hdUrl && qualities.length > 1) {{
            source.src = hdUrl;
            video.load();
        }}
    </script>
</body>
</html>"""
                            encoded = custom_player_html.encode('utf-8')
                            self.send_response(200)
                            self.send_header('Content-Type', 'text/html; charset=utf-8')
                            self.send_header('Content-Length', str(len(encoded)))
                            self.end_headers()
                            self.wfile.write(encoded)
                            return

                        # Proxy the get_file urls to bypass Referer checks
                        def proxy_tktube_url(match):
                            orig_url = match.group(0)
                            if orig_url.startswith('/'):
                                orig_url = "https://tktube.com" + orig_url
                            encoded_url = base64.b64encode(orig_url.encode('utf-8')).decode('utf-8')
                            return f"http://127.0.0.1:{proxy_port}/?url={encoded_url}"
                        
                        html = re.sub(r'(?:https?://[a-zA-Z0-9\.-]*tktube\.com)?/[a-z]*/?get_file/[^\'\"]+', proxy_tktube_url, html)

                        # Method 3: Remove obfuscated script tags loading exo mobile/pc scripts
                        html = re.sub(
                            r'<script[^>]*?>\s*if\s*\(\s*navigator\.userAgent\.match.*?atob\(.*?</script>',
                            '', html, flags=re.IGNORECASE|re.DOTALL
                        )
                        # Remove known ad scripts
                        html = re.sub(
                            r'<script[^>]*?src=["\'][^"\'"]*(exo_pc|adlib|exoclick|juicyads|trafficjunky|popcash|popunder|propellerads|adnxs)[^"\'"]*(js|php)[^>]*>.*?</script>',
                            '', html, flags=re.IGNORECASE|re.DOTALL
                        )
                        # Method 4: Strip all adv_ keys from flashvars
                        html = re.sub(r'adv_[a-zA-Z0-9_]+\s*:\s*\'[^\']*\'\s*,?\s*', '', html)

                        tktube_ad_killer = """
<script>
(function() {
    // Block JavaScript popups
    try {
        Object.defineProperty(Window.prototype, 'open', {
            value: function() {
                console.log("[Injected AdBlock] Blocked Window.prototype.open!");
                return null;
            },
            writable: false,
            configurable: false
        });
    } catch(e) {
        window.open = function() {
            console.log("[Injected AdBlock] Blocked window.open!");
            return null;
        };
    }
    window.onbeforeunload = null;

    // Block dynamic script injections (Method 3)
    var _origWrite = document.write;
    document.write = function(str) {
        if (str && (str.includes('exo_') || str.includes('adlib') || str.includes('exoclick') || str.includes('magsrv'))) {
            console.log("[Injected AdBlock] Blocked document.write of ad script:", str);
            return;
        }
        return _origWrite.call(document, str);
    };

    var _origCreateElement = document.createElement;
    document.createElement = function(tagName) {
        var el = _origCreateElement.call(document, tagName);
        if (tagName.toLowerCase() === 'script') {
            var _origSetAttribute = el.setAttribute;
            el.setAttribute = function(name, value) {
                if (name === 'src' && value) {
                    var valLower = value.toLowerCase();
                    if (valLower.includes('exoclick') || valLower.includes('magsrv') || valLower.includes('adlib') || valLower.includes('exo_')) {
                        console.log("[Injected AdBlock] Blocked dynamic script setAttribute:", value);
                        return;
                    }
                }
                return _origSetAttribute.apply(this, arguments);
            };
            Object.defineProperty(el, 'src', {
                set: function(val) {
                    if (val) {
                        var valLower = val.toLowerCase();
                        if (valLower.includes('exoclick') || valLower.includes('magsrv') || valLower.includes('adlib') || valLower.includes('exo_')) {
                            console.log("[Injected AdBlock] Blocked dynamic script src assignment:", val);
                            return;
                        }
                    }
                    el.setAttribute('src', val);
                },
                get: function() {
                    return el.getAttribute('src');
                }
            });
        }
        return el;
    };

    // Block ad XHRs
    try {
        var _origXHRProto = window.XMLHttpRequest.prototype.open;
        window.XMLHttpRequest.prototype.open = function(method, url) {
            if (url && typeof url === 'string') {
                var lowerUrl = url.toLowerCase();
                if (lowerUrl.includes('magsrv.com') || lowerUrl.includes('vast') || lowerUrl.includes('adlib') || lowerUrl.includes('exo_pc') || lowerUrl.includes('exoclick') || lowerUrl.includes('rv16888') || lowerUrl.includes('tklivechat')) {
                    console.log("[Injected AdBlock] Blocked ad XHR:", url);
                    arguments[1] = 'data:application/xml,<VAST version="3.0"></VAST>';
                }
            }
            return _origXHRProto.apply(this, arguments);
        };
    } catch(e) {}

    // Inject CSS to hide ad layouts
    var style = document.createElement('style');
    style.textContent = `
        [class*="popunder"], [id*="popunder"], [class*="ad-container"], [id*="ad-banner"], 
        iframe[src*="magsrv"], iframe[src*="adlib"], iframe[src*="exoclick"], 
        div[style*="z-index: 2147483647"], div[style*="z-index:2147483647"],
        .mg-native-wrap, .exoclick-ad, a[href*="magsrv.com"], a[href*="exoclick"] { 
            display: none !important; 
            visibility: hidden !important; 
            pointer-events: none !important; 
            width: 0 !important; 
            height: 0 !important; 
        }
    `;
    document.head.appendChild(style);

    // Capture event interceptors
    var blockAdEvents = function(e) {
        if (!e.isTrusted) return;
        var target = e.target;
        
        var link = target.closest('a');
        if (link && link.href) {
            var href = link.href.toLowerCase();
            if (!href.startsWith('javascript:') && !href.startsWith('#')) {
                console.log("[Injected AdBlock] Blocked hyperlink event:", link.href);
                e.preventDefault();
                e.stopPropagation();
                return;
            }
        }

        if (target.closest('[target="_blank"]')) {
            console.log("[Injected AdBlock] Blocked target=_blank event");
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        var isControl = target.closest('.fp-controls, .fp-ui, video, button, .loop-btn, [class*="kt-api-btn"], .kt-api-btn-start, .fp-ad-skip, .fp-skip, [class*="fp-skip"], [class*="skip-ad"], .fp-icon');
        if (!isControl) {
            console.log("[Injected AdBlock] Blocked event on non-control:", e.type, target);
            e.preventDefault();
            e.stopPropagation();
        }
    };
    
    document.addEventListener('click', blockAdEvents, true);
    document.addEventListener('mousedown', blockAdEvents, true);
    document.addEventListener('mouseup', blockAdEvents, true);

    document.addEventListener('submit', function(e) {
        console.log("[Injected AdBlock] Blocked form submit!");
        e.preventDefault();
        e.stopPropagation();
    }, true);

    var ticks = 0, openAdClicked = false;
    var t = setInterval(function() {
        ticks++;
        if (ticks > 400) { clearInterval(t); return; }

        var btn = document.querySelector('button.kt-api-btn-start, .kt-api-btn-start, [class*="kt-api-btn"]');
        if (!btn) {
            var allBtnElems = document.querySelectorAll('button, a, div, span');
            for (var i = 0; i < allBtnElems.length; i++) {
                var el = allBtnElems[i];
                if ((el.innerText || '').toLowerCase().includes('open ad')) {
                    btn = el;
                    break;
                }
            }
        }
        if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0) && !openAdClicked) {
            console.log("[Injected AdBlock] Clicking Open AD button...");
            try { 
                btn.click(); 
                openAdClicked = true;
            } catch(e) {}
        }

        var skipBtn = document.querySelector('.fp-ad-skip, .fp-skip, [class*="fp-skip"], [class*="skip-ad"], .skip-ad-btn, [class*="skip"]');
        if (!skipBtn) {
            var allElems = document.querySelectorAll('*');
            for (var i = 0; i < allElems.length; i++) {
                var el = allElems[i];
                if (el.children.length < 4 && (el.innerText || '').toLowerCase().includes('skip ad') && (el.offsetParent !== null || el.offsetWidth > 0)) {
                    skipBtn = el;
                    break;
                }
            }
        }
        if (skipBtn && (skipBtn.offsetParent !== null || skipBtn.offsetWidth > 0)) {
            console.log("[Injected AdBlock] Clicking Skip AD button...");
            try { skipBtn.click(); } catch(e) {}
        }
    }, 150);
})();
</script>
"""

                        # Method 2: Inject Content-Security-Policy meta tag
                        csp_meta = "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self' 'unsafe-inline' 'unsafe-eval' http://127.0.0.1:* ws://127.0.0.1:* https://*.tkcdns.com https://*.tktube.com; media-src *; img-src *; style-src 'self' 'unsafe-inline' https://*.tktube.com; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.tktube.com http://127.0.0.1:*;\">"
                        if '<head>' in html:
                            html = html.replace('<head>', f'<head>{csp_meta}<base href="https://tktube.com/">' + tktube_ad_killer)
                        elif '<HEAD>' in html:
                            html = html.replace('<HEAD>', f'<HEAD>{csp_meta}<base href="https://tktube.com/">' + tktube_ad_killer)
                        else:
                            html = csp_meta + '<base href="https://tktube.com/">' + tktube_ad_killer + html

                        encoded = html.encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(encoded)))
                        self.end_headers()
                        self.wfile.write(encoded)
                        return
                    else:
                        self.send_response(302)
                        self.send_header('Location', official_embed_url)
                        self.end_headers()
                        return
                self.send_error(404)

            elif parsed_path.path == '/' and 'url' in qs:
                url_param = qs.get('url', [''])[0]
                if url_param:
                    target_url = base64.b64decode(url_param).decode('utf-8')
                    # Method 5: Request-level blocklist in Python proxy
                    lower_url = target_url.lower()
                    ad_keywords = ['exoclick', 'magsrv', 'trafficjunky', 'juicyads', 'popcash', 'popunder', 'propellerads', 'adnxs', 'adlib', 'exo_pc', 'exo_mobile', 'rv16888', 'tklivechat']
                    if any(kw in lower_url for kw in ad_keywords):
                        safe_print(f"[Proxy] Blocked network ad request to: {target_url}")
                        self.send_response(403)
                        self.end_headers()
                        return

                    req_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    if 'Range' in self.headers:
                        req_headers['Range'] = self.headers['Range']
                    if 'tktube.com' in target_url:
                        req_headers['Referer'] = 'https://tktube.com/'
                            
                    req = urllib.request.Request(target_url, headers=req_headers)
                    try:
                        with urllib.request.urlopen(req, timeout=15) as r:
                            content_type = r.headers.get('Content-Type', '')
                            # Intercept and rewrite M3U8 manifests
                            if '.m3u8' in target_url or 'mpegurl' in content_type.lower():
                                text = r.read().decode('utf-8')
                                lines = text.splitlines()
                                new_lines = []
                                for line in lines:
                                    if line.startswith('#') or not line.strip():
                                        new_lines.append(line)
                                    else:
                                        uri = line.strip()
                                        if not uri.startswith('http'):
                                            base = target_url.rsplit('/', 1)[0]
                                            uri = f"{base}/{uri}"
                                        encoded_uri = base64.b64encode(uri.encode('utf-8')).decode('utf-8')
                                        new_lines.append(f"http://127.0.0.1:{proxy_port}/?url={encoded_uri}")
                                rewritten_text = '\n'.join(new_lines).encode('utf-8')
                                self.send_response(200)
                                self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                                self.send_header('Content-Length', str(len(rewritten_text)))
                                self.end_headers()
                                self.wfile.write(rewritten_text)
                                return
                                
                            self.send_response(r.status)
                            for k, v in r.getheaders():
                                if k.lower() in ['content-type', 'content-length', 'content-range', 'accept-ranges']:
                                    self.send_header(k, v)
                            self.end_headers()
                            while True:
                                chunk = r.read(1024 * 64)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                            return
                    except Exception as e:
                        print(f"Proxy Error for {target_url}: {e}")
                        self.send_response(302)
                        self.send_header('Location', target_url)
                        self.end_headers()
                        return
                self.send_error(404)
            else:
                self.send_error(404)
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except:
                pass

PROXY_SERVER = None

def start_proxy_server():
    global PROXY_SERVER
    server = HTTPServer(('127.0.0.1', proxy_port), VideoProxyHandler)
    PROXY_SERVER = server
    server.serve_forever()

threading.Thread(target=start_proxy_server, daemon=True).start()

def fetch_jable_metadata(ccode, api_instance):
    if not api_instance or not api_instance.browser_context:
        return None
    ccode_lower = ccode.lower().strip()
    url = f"https://jable.tv/videos/{ccode_lower}/"
    html = api_instance.playwright_fetch_html(url, timeout_ms=10000)
    if not html or "404 Not Found" in html or "Page not found" in html or "class=\"video-info\"" not in html:
        search_url = f"https://jable.tv/search/{ccode_lower}/"
        html = api_instance.playwright_fetch_html(search_url, timeout_ms=10000)
        if html:
            m_link = re.search(r'href="(https://jable\.tv/videos/[^/]+/)"', html)
            if m_link:
                url = m_link.group(1)
                html = api_instance.playwright_fetch_html(url, timeout_ms=10000)
    if html and "class=\"video-info\"" in html:
        m_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if not m_title:
            m_title = re.search(r'<title>(.*?)</title>', html, re.I)
        if m_title:
            title_text = m_title.group(1).split(' - ')[0].strip()
            models = re.findall(r'data-original-title="([^"]+)"', html)
            clean_title_text = title_text.replace(ccode.upper(), "").replace(ccode.lower(), "").strip()
            parsed_actress = parse_actress_from_title(clean_title_text)
            if parsed_actress and parsed_actress != "未知":
                return {"actress": parsed_actress, "title": clean_title_text}
            elif models:
                return {"actress": ", ".join(models), "title": clean_title_text}
            else:
                return {"actress": "未知", "title": clean_title_text}
    return None

def fetch_metadata_info(ccode, api_instance=None, priority=0):
    if not ccode:
        return {"actress": "未知", "title": None, "date": ""}
        
    ccode_lower = ccode.lower().strip()
    if ccode_lower in AVWIKI_CACHE:
        return AVWIKI_CACHE[ccode_lower]
        
    non_std_keywords = ["fc2", "md", "mdyd", "sht", "mianbar", "hs", "cc", "tw", "pk", "lu", 
                        "nureane", "octavia", "skmj", "bacj", "aldn", "cead", "rctd", "huntc", 
                        "nact", "jrze", "nsfs", "flav", "uman", "scop", "bonu", "dvaj", "svvrt", "apgh"]
    is_non_std = any(k in ccode_lower for k in non_std_keywords)
    
    actress = "未知"
    title = None
    date = ""
    
    try:
        jable_info = fetch_jable_metadata(ccode, api_instance)
        if jable_info and jable_info.get("actress") and jable_info["actress"] != "未知":
            res = {"actress": jable_info["actress"], "title": jable_info["title"], "date": date}
            AVWIKI_CACHE[ccode_lower] = res
            return res
    except Exception as e:
        safe_print(f"Jable metadata fetch failed for {ccode}: {e}")

    if is_non_std:
        res = {"actress": actress, "title": title, "date": date}
        AVWIKI_CACHE[ccode_lower] = res
        return res

    if api_instance and api_instance.browser_context:
        try:
            avwiki_url = f"https://av-wiki.net/{ccode_lower}/"
            html = api_instance.playwright_fetch_html(avwiki_url, timeout_ms=10000)
            if html:
                m_title_tag = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                if m_title_tag:
                    title_text = m_title_tag.group(1)
                    m_actress = re.search(r'に出演のAV女優は誰？\s*(.*?)\s*\|', title_text)
                    if m_actress and m_actress.group(1).strip():
                        actress = m_actress.group(1).strip()
                    m_title = re.search(r'：(.*?)に出演のAV女優は誰？', title_text)
                    if m_title and m_title.group(1).strip():
                        title = m_title.group(1).strip()
                        
                if actress != "未知" or title:
                    res = {"actress": actress, "title": title, "date": date}
                    AVWIKI_CACHE[ccode_lower] = res
                    return res
        except Exception as e:
            safe_print(f"Playwright av-wiki fetch failed: {e}")

    if api_instance and api_instance.browser_context:
        try:
            url = f"https://www.javbus.com/{ccode.upper()}"
            html = api_instance.playwright_fetch_html(url, timeout_ms=10000)
            if html:
                m_actresses = re.findall(r'<a href="https://www\.javbus\.com/star/[^"]+">([^<]+)</a>', html)
                if m_actresses:
                    actress = ", ".join(m_actresses)
                m_title = re.search(r'<h3>(.*?)</h3>', html)
                if m_title:
                    title = m_title.group(1).strip()
                m_date = re.search(r'<span class="header">發行日期:</span>\s*([\d-]+)', html)
                if m_date:
                    date = m_date.group(1).strip()
                    
                if actress != "未知" and actress != "":
                    res = {"actress": actress, "title": title, "date": date}
                    AVWIKI_CACHE[ccode_lower] = res
                    return res
        except Exception as e:
            safe_print(f"Playwright JavBus fetch failed: {e}")
        
    res = {"actress": actress, "title": title, "date": date}
    AVWIKI_CACHE[ccode_lower] = res
    return res

def parse_actress_from_title(title):
    if not title:
        return "未知"
    t = title.strip()
    t = re.sub(r'[\(\[（【].*?[\)\]）】]', '', t).strip()
    
    exclude_terms = {
        "中出", "巨乳", "美乳", "爆乳", "潮吹", "高清", "字幕", "破解", "流出", "合集", "下卷", "上卷", "精選",
        "中文字幕", "中文", "近親", "相姦", "亂倫", "強姦", "輪姦", "運動", "性感", "美女", "熟女", "人妻", 
        "主婦", "OL", "學生", "女僕", "教師", "醫生", "護士", "空姐", "痴漢", "野外", "溫泉", "旅館", "露出",
        "自慰", "潮吹", "噴水", "失禁", "榨汁", "乳交", "口交", "肛交", "內射", "高潮", "呻吟", "恍惚",
        "禁慾", "挑逗", "性愛", "進化", "拷貝", "複製", "修復", "洩露", "版本", "合演", "主演", "演出", "新人",
        "約會", "一日", "旅行", "溫泉", "旅館", "酒店", "飯店", "同居", "同床", "同房", "上司", "同事", "客戶",
        "老師", "學生", "同學", "班長", "會長", "校長", "護士", "醫生", "病人", "妹妹", "姐姐", "媽媽", "阿姨",
        "女演員", "女優", "小姐", "大嫂", "媳婦", "婆婆", "無碼", "破解", "字幕", "合集", "系列", "精選",
        "特輯", "推薦", "排行", "熱門", "最新", "經典", "超清", "高清", "完整版", "流出版", "破壞版", "解禁版",
        "未公開", "未發行", "未曝光", "幕後", "花絮", "紀錄", "採訪", "訪談", "對談", "談話", "聊天", "交流",
        "互動", "體驗", "嘗試", "挑戰", "冒險", "探索", "研究", "分析", "調查", "報告", "總結", "回顧", "展望",
        "計劃", "方案", "策略", "方法", "技巧", "秘訣", "指南", "教程", "課程", "培訓", "講座", "研討",
        "動漫", "遊戲", "影視", "音樂", "舞蹈", "戲劇", "曲藝", "書畫", "雕塑", "攝影", "設計", "手工",
        "制服", "黑絲", "網絲", "眼鏡", "美腿", "長腿", "可愛", "漂亮", "苗條", "豐滿", "骨感", "高挑",
        "順從", "調教", "綁架", "監禁", "虐待", "羞恥", "按摩", "自拍",
        "sod", "s1", "moodyz", "ipx", "ebod", "fsd", "das", "idea", "pocket", "prestiges", "prestige",
        "tokyo", "hot", "caribbean", "caribbeancom", "pacopacomama", "1pondo", "10musume", "heyzo",
        "kawaii", "oppai", "honda", "mide", "abp", "dvd", "blu-ray", "bd", "vr", "hd", "fhd", "4k",
        "完全", "配信", "先行", "限定", "作品", "出演", "販售", "開始", "解禁", "特別", "限定", "決定", "保存",
        "豪華", "決定版", "監督", "企劃", "特寫", "密著", "熱愛", "性感", "初出演", "初登場"
    }

    match = re.search(r'([\u4e00-\u9fa5]{2,4})$', t)
    if match:
        actress = match.group(1)
        is_excluded = actress in exclude_terms or any(term in actress for term in exclude_terms)
        if not is_excluded:
            return actress
            
    candidates = re.findall(r'[\u4e00-\u9fa5]{2,4}', t)
    for cand in candidates:
        is_excluded = cand in exclude_terms or any(term in cand for term in exclude_terms)
        if not is_excluded:
            return cand
            
    return "未知"

HOME_ITEM_RE = re.compile(
    r'<a href="(/tw/v/[^"]+)" class="poster">.*?<img([^>]*?)>.*?<a href="[^"]+" class="title">\s*<span class="code">([^<]+)</span>\s*<span>([^<]+)</span>',
    re.DOTALL | re.IGNORECASE
)
PREVIEW_URL_RE1 = re.compile(r'<d-tag\s+[^>]*?url=["\']([^"\']+)["\'][^>]*?src=["\']Preview["\']', re.IGNORECASE)
PREVIEW_URL_RE2 = re.compile(r'<d-tag\s+[^>]*?src=["\']Preview["\'][^>]*?url=["\']([^"\']+)["\']', re.IGNORECASE)

def parse_relative_time(relative_str):
    if not relative_str:
        return ""
    
    relative_str = relative_str.strip()
    now = datetime.datetime.now()
    days = 0
    hours = 0
    minutes = 0
    
    week_match = re.search(r'(\d+)\s*週', relative_str)
    day_match = re.search(r'(\d+)\s*天', relative_str)
    hour_match = re.search(r'(\d+)\s*小時', relative_str)
    min_match = re.search(r'(\d+)\s*分鐘', relative_str)
    month_match = re.search(r'(\d+)\s*個月', relative_str)
    year_match = re.search(r'(\d+)\s*年', relative_str)
    
    if week_match:
        days += int(week_match.group(1)) * 7
    if day_match:
        days += int(day_match.group(1))
    if hour_match:
        hours += int(hour_match.group(1))
    if min_match:
        minutes += int(min_match.group(1))
    if month_match:
        days += int(month_match.group(1)) * 30
    if year_match:
        days += int(year_match.group(1)) * 365
        
    if days == 0 and hours == 0 and minutes == 0:
        eng_hour = re.search(r'(\d+)\s*hour', relative_str, re.IGNORECASE)
        eng_day = re.search(r'(\d+)\s*day', relative_str, re.IGNORECASE)
        eng_week = re.search(r'(\d+)\s*week', relative_str, re.IGNORECASE)
        eng_min = re.search(r'(\d+)\s*min', relative_str, re.IGNORECASE)
        eng_month = re.search(r'(\d+)\s*month', relative_str, re.IGNORECASE)
        eng_year = re.search(r'(\d+)\s*year', relative_str, re.IGNORECASE)
        
        if eng_week:
            days += int(eng_week.group(1)) * 7
        if eng_day:
            days += int(eng_day.group(1))
        if eng_hour:
            hours += int(eng_hour.group(1))
        if eng_min:
            minutes += int(eng_min.group(1))
        if eng_month:
            days += int(eng_month.group(1)) * 30
        if eng_year:
            days += int(eng_year.group(1)) * 365
            
    delta = datetime.timedelta(days=days, hours=hours, minutes=minutes)
    upload_time = now - delta
    return upload_time.strftime('%Y-%m-%d')

def parse_javhdporn_list(html, url=""):
    articles = re.findall(r'<article[^>]*>.*?</article>', html, re.DOTALL)
    results = []
    seen_codes = set()
    
    # Determine type
    v_type = "無碼破解版" if "decensored" in url else "正常版"
    
    for art in articles:
        if 'thumb-block-native-ad' in art or 'ad_box' in art:
            continue
            
        link_m = re.search(r'<a class="archive-entry"\s+href="([^"]+)"\s+title="([^"]+)"', art)
        if not link_m:
            link_m = re.search(r'<a class="archive-entry"\s+title="([^"]+)"\s+href="([^"]+)"', art)
            if link_m:
                title, link = link_m.groups()
            else:
                continue
        else:
            link, title = link_m.groups()
            
        img = ""
        for attr in ["data-lazy-src", "data-src", "src"]:
            img_m = re.search(attr + r'=["\']([^"\']+)["\']', art)
            if img_m and img_m.group(1):
                val = img_m.group(1).strip()
                if not any(x in val for x in ["placeholder", "clear.gif", "transparent"]):
                    img = val
                    break
        if not img:
            img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', art)
            img = img_m.group(1).strip() if img_m else ""
            
        preview_m = re.search(r'data-mediabook=["\']([^"\']+)["\']', art)
        preview = preview_m.group(1).strip() if preview_m else ""
        
        slug = link.strip().rstrip('/').split('/')[-1]
        code = clean_code(slug).upper()
        if not code:
            code = slug.upper()
            
        if code in seen_codes:
            continue
        seen_codes.add(code)
        
        actress = parse_actress_from_title(title)
        
        results.append({
            "code": code,
            "title": title.strip(),
            "cover": img,
            "preview": preview,
            "url": link.strip(),
            "type": v_type,
            "actress": actress,
            "relative_time": "最新",
            "upload_date": "",
            "source": "javhdporn"
        })
    return results

def parse_supjav_list(html, url=""):
    posts = html.split('<div class="post">')[1:]
    if not posts:
        posts = html.split('<div class="post')[1:]
        
    results = []
    seen_codes = set()
    
    for post in posts:
        title_m = re.search(r'class="img"\s+title="([^"]+)"', post)
        if not title_m:
            title_m = re.search(r'title="([^"]+)"\s+class="img"', post)
        if not title_m:
            title_m = re.search(r'<a[^>]+title="([^"]+)"', post)
            
        title = title_m.group(1).strip() if title_m else ""
        link_m = re.search(r'href="([^"]+)"', post)
        link = link_m.group(1) if link_m else ""
        if not link:
            continue
            
        img = ""
        for attr in ["data-original", "data-src", "src"]:
            img_m = re.search(attr + r'=["\']([^"\']+)["\']', post)
            if img_m and img_m.group(1):
                val = img_m.group(1).strip()
                if not any(x in val for x in ["placeholder", "clear.gif", "transparent"]):
                    img = val
                    break
        if not img:
            img_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', post)
            img = img_m.group(1).strip() if img_m else ""
            
        code = ""
        img_filename = img.split('/')[-1] if img else ""
        code_m = re.search(r'([a-zA-Z0-9\-]+)\.(?:jpg|png|webp|gif|jpeg)', img_filename, re.I)
        if code_m:
            raw_code = code_m.group(1).split('!')[0]
            if 'fc2' in raw_code.lower():
                digits = re.findall(r'\d+', raw_code)
                if digits:
                    code = f"FC2-PPV-{digits[-1]}"
                else:
                    code = raw_code.upper()
            else:
                code = clean_code(raw_code).upper()
                
        if not code:
            code_m = re.search(r'(fc2\s*ppv\s*\d+|fc2\s*\d+)', title.lower())
            if code_m:
                num_m = re.search(r'(\d+)', code_m.group(1))
                code = f"FC2-PPV-{num_m.group(1)}" if num_m else code_m.group(1).upper()
                
        if not code:
            slug = link.strip().rstrip('/').split('/')[-1]
            code = slug.replace(".html", "").upper()
            
        if code in seen_codes:
            continue
        seen_codes.add(code)
        
        meta_m = re.search(r'<div class="meta">\s*(.*?)\s*<span', post, re.DOTALL)
        if not meta_m:
            meta_m = re.search(r'<div class="meta">\s*(.*?)\s*</div>', post, re.DOTALL)
        date = re.sub(r'<[^>]+>', '', meta_m.group(1)).strip() if meta_m else ""
        date = date.split(' ')[0].split('\n')[0].strip()
        date = re.sub(r'[^\d/]', '', date).replace('/', '-')
        
        actress = parse_actress_from_title(title)
        
        results.append({
            "code": code,
            "title": title.strip(),
            "cover": img,
            "preview": "",
            "url": link.strip(),
            "type": "FC2",
            "actress": actress,
            "relative_time": f"加入日期: {date}" if date else "最新",
            "upload_date": date,
            "source": "supjav"
        })
    return results

class PlatformRegistry:
    def __init__(self, api):
        self.api = api
        
    def _fetch_javhdporn_info(self, ccode):
        search_url = f"https://www.javhdporn.net/zh/?s={ccode.lower()}"
        success, html = fetch_html_content(search_url)
        if success:
            videos = parse_javhdporn_list(html, search_url)
            for v in videos:
                if clean_code(v.get("code")).upper() == ccode.upper():
                    return {
                        "url": v["url"],
                        "img": v["cover"],
                        "preview": v["preview"],
                        "type": v["type"],
                        "actress": v["actress"]
                    }
        return None

    def _fetch_supjav_info(self, ccode):
        search_url = f"https://supjav.com/?s={ccode.lower()}"
        success, html = fetch_html_content(search_url)
        if success:
            videos = parse_supjav_list(html, search_url)
            for v in videos:
                if clean_code(v.get("code")).upper() == ccode.upper():
                    return {
                        "url": v["url"],
                        "img": v["cover"],
                        "preview": v["preview"],
                        "type": v["type"],
                        "actress": v["actress"]
                    }
        return None

    def get_providers(self):
        return [
            {
                "name": "javhdporn",
                "fetch_info": lambda ccode: self._fetch_javhdporn_info(ccode),
                "get_home": lambda url: self.api.get_home_videos(url)
            },
            {
                "name": "supjav",
                "fetch_info": lambda ccode: self._fetch_supjav_info(ccode),
                "get_home": lambda url: self.api.get_home_videos(url)
            },
            {
                "name": "tcav",
                "fetch_info": lambda ccode: self.api.fetch_tcav_info(ccode),
                "get_home": lambda url: self.api.get_tcav_home_videos(url)
            },
            {
                "name": "tktube",
                "fetch_info": lambda ccode: self.api.fetch_tktube_info(ccode),
                "get_home": lambda url: self.api.get_tktube_home_videos(url)
            }
        ]

class Api:
    def __init__(self):
        self.data = []
        self.data_path = os.path.join(get_data_path(), 'Favorites.json')
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception as e:
                safe_print("Error loading json:", e)
                import shutil
                bak_path = self.data_path + ".corrupted.bak"
                try:
                    shutil.copy2(self.data_path, bak_path)
                    safe_print(f"Backed up corrupted Favorites.json to {bak_path}")
                except Exception as backup_err:
                    safe_print("Failed to backup corrupted file:", backup_err)
                self.data = []
        
        threading.Thread(target=self.heal_favorites_background, daemon=True).start()
        
        self.current_version = VERSION
        from version_manager import VersionManager
        self.version_manager = VersionManager(self.current_version, logger=print)
        self.update_progress = {"status": "idle", "percent": 0, "detail": "", "error": None}
        self._window = None
        
        self.playwright_queue = queue.Queue()
        self.browser_context = None
        self.playwright_err = None
        
        global GLOBAL_API
        GLOBAL_API = self
        
        threading.Thread(target=self.init_playwright_background, daemon=True).start()
                
    def get_videos(self):
        return self.data

    def toggle_devtools(self):
        pass

    def get_cached_metadata(self, ccodes):
        res = {}
        for c in ccodes:
            cl = c.lower()
            if cl in AVWIKI_CACHE:
                res[c] = AVWIKI_CACHE[cl]
        return res

    def get_metadata(self, ccode):
        res = fetch_metadata_info(ccode, self)
        return res if res else {"actress": "未知", "title": None}

    def request_actress_async(self, ccode):
        def background_fetch():
            fetch_metadata_info(ccode, self, priority=10)
        threading.Thread(target=background_fetch, daemon=True).start()
        return True

    def get_preview_data(self, url):
        if not url: return ""
        import base64
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            data = urllib.request.urlopen(req, timeout=10).read()
            encoded = base64.b64encode(data).decode('utf-8')
            return f"data:video/mp4;base64,{encoded}"
        except Exception as e:
            safe_print("Preview fetch error:", e)
            return ""

    def save_videos(self, new_data):
        self.data = new_data
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            safe_print("Save error:", e)
            return False

    def fetch_video_info(self, raw_code):
        ccode = clean_code(raw_code)
        if not ccode:
            return {"raw": raw_code, "clean": "", "code": raw_code, "url": "", "img": "", "found": False, "type": "無", "actress": "未知"}
            
        providers = PlatformRegistry(self).get_providers()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as executor:
            future_to_prov = {
                executor.submit(prov["fetch_info"], ccode): prov
                for prov in providers
            }
            
            concurrent.futures.wait(future_to_prov.keys(), timeout=6)
            
            results = {}
            for future, prov in future_to_prov.items():
                try:
                    res = future.result()
                    if res:
                        results[prov["name"]] = res
                except:
                    pass
            
            actress_name = "未知"
            for name in ["javhdporn", "supjav", "tktube", "tcav"]:
                if name in results and "actress" in results[name] and results[name]["actress"] != "未知":
                    actress_name = results[name]["actress"]
                    break
            
            is_tcav_priority = any(x in ccode.lower() for x in ["fc2", "md", "mdyd", "sht", "mianbar", "hs", "cc", "tw", "pk", "lu"])
            priority_list = ["tcav", "supjav", "tktube", "javhdporn"] if is_tcav_priority else ["tktube", "javhdporn", "supjav", "tcav"]
            
            best_res = None
            for name in priority_list:
                if name in results:
                    r = results[name]
                    if r.get("type") in ["無碼破解版", "FC2"]:
                        best_res = (name, r)
                        break
                        
            if not best_res:
                for name in priority_list:
                    if name in results:
                        best_res = (name, results[name])
                        break
                        
            if best_res:
                name, r = best_res
                
                final_actress = actress_name
                meta_info = fetch_metadata_info(ccode, self)
                if meta_info and meta_info.get("actress") and meta_info["actress"] != "未知":
                    final_actress = meta_info["actress"]
                
                resolved_date = r.get("upload_date") or (meta_info.get("date") if meta_info else "") or ""
                
                return {
                    "raw": raw_code,
                    "clean": ccode,
                    "code": ccode.upper(),
                    "url": r["url"],
                    "img": r["img"],
                    "preview": r.get("preview") or "",
                    "found": True,
                    "type": r["type"],
                    "actress": final_actress,
                    "upload_date": resolved_date,
                    "relative_time": f"加入日期: {resolved_date}" if resolved_date else ""
                }
                    
        if ccode and re.search(r'[A-Z0-9]+-[0-9]+', ccode):
            parsed_actress = parse_actress_from_title(raw_code)
            meta_info = fetch_metadata_info(ccode, self)
            final_actress = parsed_actress
            if meta_info and meta_info.get("actress") and meta_info["actress"] != "未知":
                final_actress = meta_info["actress"]
            resolved_date = (meta_info.get("date") if meta_info else "") or ""
            
            return {
                "raw": raw_code,
                "clean": ccode,
                "code": ccode.upper(),
                "url": f"https://missav.ws/{ccode.lower()}",
                "img": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop",
                "preview": "",
                "found": True,
                "type": "正常版",
                "actress": final_actress,
                "upload_date": resolved_date,
                "relative_time": f"加入日期: {resolved_date}" if resolved_date else ""
            }
            
        return {
            "raw": raw_code,
            "clean": ccode,
            "code": ccode.upper(),
            "url": "",
            "img": "",
            "found": False,
            "type": "無",
            "actress": "未知"
        }

    def enrich_videos_with_metadata(self, videos):
        if not videos:
            return []
            
        def enrich_video(v):
            ccode = v.get("code")
            if ccode:
                meta_info = fetch_metadata_info(ccode, self)
                if meta_info:
                    if meta_info.get("actress") and meta_info["actress"] != "未知":
                        v["actress"] = meta_info["actress"]
                    if meta_info.get("title") and (not v.get("title") or ccode in v.get("title")):
                        prefix = ""
                        m_prefix = re.match(r'(\[[^\]]+\])', v.get("title", ""))
                        if m_prefix: 
                            prefix = m_prefix.group(1) + " "
                        v["title"] = prefix + meta_info["title"]
            return v
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as enrich_executor:
            enriched = list(enrich_executor.map(enrich_video, videos))
        return enriched

    def search_all_platforms(self, query):
        if not query:
            return {"videos": [], "total_pages": 1, "current_page": 1}
            
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        
        javhdporn_search_url = f"https://www.javhdporn.net/zh/?s={encoded_query}"
        supjav_search_url = f"https://supjav.com/?s={encoded_query}"
        tcav_search_url = f"https://tcav.85xvideo.com/?s={encoded_query}"
        tktube_search_url = f"https://tktube.com/zh/search/{encoded_query}/"
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_javhdporn = executor.submit(self.get_home_videos, javhdporn_search_url)
            future_supjav = executor.submit(self.get_home_videos, supjav_search_url)
            future_tcav = executor.submit(self.get_tcav_home_videos, tcav_search_url)
            future_tktube = executor.submit(self.get_tktube_home_videos, tktube_search_url)
            
            concurrent.futures.wait([future_javhdporn, future_supjav, future_tcav, future_tktube], timeout=8)
            
            try:
                javhdporn_res = future_javhdporn.result()
                javhdporn_videos = javhdporn_res.get("videos") if isinstance(javhdporn_res, dict) else javhdporn_res
            except Exception as e:
                safe_print("javhdporn search error:", e)
                javhdporn_videos = []
                
            try:
                supjav_res = future_supjav.result()
                supjav_videos = supjav_res.get("videos") if isinstance(supjav_res, dict) else supjav_res
            except Exception as e:
                safe_print("supjav search error:", e)
                supjav_videos = []
                
            try:
                tcav_res = future_tcav.result()
                tcav_videos = tcav_res.get("videos") if isinstance(tcav_res, dict) else tcav_res
            except Exception as e:
                safe_print("TCAV search error:", e)
                tcav_videos = []
                
            try:
                tktube_res = future_tktube.result()
                tktube_videos = tktube_res.get("videos") if isinstance(tktube_res, dict) else tktube_res
            except Exception as e:
                safe_print("TKTube search error:", e)
                tktube_videos = []
                
            merged_videos = []
            seen_codes = set()
            
            clean_q = clean_code(query).upper()
            
            def is_match(v):
                v_code = v.get("code", "").upper()
                return clean_q in v_code or v_code in clean_q or query.upper() in v_code
                
            matches = []
            others = []
            
            is_fc2_query = "fc2" in query.lower()
            platform_order = [tcav_videos, supjav_videos, tktube_videos, javhdporn_videos] if is_fc2_query else [tktube_videos, javhdporn_videos, supjav_videos, tcav_videos]
            
            for vlist in platform_order:
                if not vlist: continue
                for v in vlist:
                    code = v.get("code", "").upper()
                    if not code or code in seen_codes:
                        continue
                    seen_codes.add(code)
                    
                    if is_match(v):
                        matches.append(v)
                    else:
                        others.append(v)
                        
            ccode = clean_code(query).upper()
            if ccode and re.search(r'[A-Z0-9]+-[0-9]+', ccode):
                cover_img = ""
                actress_name = "未知"
                preview_url = ""
                for v in matches + others:
                    if clean_code(v.get("code", "")).upper() == ccode:
                        if v.get("cover"):
                            cover_img = v["cover"]
                        if v.get("preview"):
                            preview_url = v["preview"]
                        if v.get("actress") and v["actress"] != "未知":
                            actress_name = v["actress"]
                        break
                
                if not cover_img:
                    for item in self.data:
                        if clean_code(item.get("code", "")).upper() == ccode:
                            if item.get("img"):
                                cover_img = item["img"]
                            if item.get("preview"):
                                preview_url = item["preview"]
                            if item.get("actress") and item["actress"] != "未知":
                                actress_name = item["actress"]
                            break
                            
                if not cover_img:
                    cover_img = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=500&auto=format&fit=crop"
                
                missav_leaked = {
                    "code": ccode,
                    "title": f"[MissAV 無碼破解] {ccode}",
                    "cover": cover_img,
                    "preview": preview_url,
                    "url": f"https://missav.ws/{ccode.lower()}-uncensored-leak",
                    "type": "無碼破解版",
                    "actress": actress_name,
                    "relative_time": "加入日期: 2026-05-18",
                    "source": "missav"
                }
                
                missav_normal = {
                    "code": ccode,
                    "title": f"[MissAV 一般版] {ccode}",
                    "cover": cover_img,
                    "preview": preview_url,
                    "url": f"https://missav.ws/{ccode.lower()}",
                    "type": "正常版",
                    "actress": actress_name,
                    "relative_time": "加入日期: 2026-05-18",
                    "source": "missav"
                }
                
                matches.insert(0, missav_leaked)
                matches.insert(1, missav_normal)
                        
            final_videos = matches + others
            final_videos = self.enrich_videos_with_metadata(final_videos)
            
            return {
                "videos": final_videos[:60],
                "total_pages": 1,
                "current_page": 1
            }

    def fetch_tktube_info(self, ccode):
        tktube_url = f"https://tktube.com/zh/search/{ccode}/"
        success, html = fetch_html_content(tktube_url)
        if success:
            res = self.parse_tktube_html(html, ccode)
            if res: return res
            
        tktube_url_2 = f"https://tktube.com/zh/search/{ccode.replace('-', '--')}/"
        success, html = fetch_html_content(tktube_url_2)
        if success:
            res = self.parse_tktube_html(html, ccode)
            if res: return res
            
        tktube_url_3 = f"https://tktube.com/zh/search/?q={ccode}"
        success, html = fetch_html_content(tktube_url_3)
        if success:
            res = self.parse_tktube_html(html, ccode)
            if res: return res
            
        return None

    def parse_tktube_html(self, html, ccode):
        best_uncensored = None
        best_normal = None
        uncensored_keywords = ["馬賽克破壞", "破除馬賽克", "馬賽克解除", "去馬賽克", "無修正", "無碼", "破解", "解除馬賽克", "破壞版"]
        
        blocks = html.split('<div class="item')[1:]
        for block in blocks:
            href_m = re.search(r'href="([^"]+)"', block)
            if not href_m: continue
            video_url = href_m.group(1)
            
            title_m = re.search(r'alt="([^"]+)"', block)
            if not title_m:
                title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', block, re.DOTALL)
            title = title_m.group(1).strip() if title_m else ""
            
            img_url = ""
            for attr in ["data-original", "data-src", "src"]:
                img_m = re.search(attr + r'="([^"]+)"', block)
                if img_m and img_m.group(1) and not any(x in img_m.group(1) for x in ["placeholder", "clear.gif", "transparent"]):
                    img_url = img_m.group(1)
                    break
            if not img_url:
                img_m = re.search(r'src="([^"]+)"', block)
                img_url = img_m.group(1) if img_m else ""
            
            preview_m = re.search(r'data-preview="([^"]+)"', block)
            preview_url = preview_m.group(1) if preview_m else ""
            
            if video_url.startswith('/'):
                video_url = "https://tktube.com" + video_url
                
            lower_title = title.lower()
            lower_url = video_url.lower()
            
            if ccode in lower_title or ccode.replace("-", "") in lower_title or ccode in lower_url or ccode.replace("-", "") in lower_url:
                is_uncensored = any(kw in lower_title for kw in uncensored_keywords)
                video_data = {
                    "url": video_url,
                    "img": img_url,
                    "preview": preview_url,
                    "type": "無碼破解版" if is_uncensored else "正常版"
                }
                if is_uncensored:
                    if not best_uncensored:
                        best_uncensored = video_data
                else:
                    if not best_normal:
                        best_normal = video_data
                        
        if best_uncensored:
            return best_uncensored
        if best_normal:
            return best_normal
        return None

# Parsers moved to top-level to prevent class indentation errors.

    def parse_home_videos(self, html, url=""):
        if not html:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        try:
            current_page = 1
            page_match = re.search(r'[?&]page=(\d+)', url)
            if not page_match:
                page_match = re.search(r'/page/(\d+)/?', url)
            if page_match:
                current_page = int(page_match.group(1))
                
            total_pages = current_page
            page_nums = [int(p) for p in re.findall(r'/page/(\d+)/?', html)]
            if page_nums:
                total_pages = max(max(page_nums), current_page)
                
            if "javhdporn.net" in url:
                results = parse_javhdporn_list(html, url)
            elif "supjav.com" in url:
                results = parse_supjav_list(html, url)
            else:
                results = []
                
            unique = []
            seen = set()
            for v in results:
                if v['code'] not in seen:
                    unique.append(v)
                    seen.add(v['code'])
            return {
                "videos": unique,
                "total_pages": total_pages,
                "current_page": current_page
            }
        except Exception as e:
            safe_print("Home parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": 1}

    def _merge_video_entries(self, v1, v2):
        actress1 = v1.get("actress", "未知")
        actress2 = v2.get("actress", "未知")
        
        def is_valid_actress(name):
            if not name: return False
            return name.strip() not in ["", "未知", "未知女優", "新加入", "女優", "None", "undefined"]
            
        final_actress = actress1
        if not is_valid_actress(actress1) and is_valid_actress(actress2):
            final_actress = actress2
        elif is_valid_actress(actress1) and is_valid_actress(actress2):
            names = set(a.strip() for a in actress1.split(",") + actress2.split(","))
            final_actress = ", ".join(sorted(names))
            
        cover = v1.get("cover") or v1.get("img") or v2.get("cover") or v2.get("img") or ""
        preview = v1.get("preview") or v2.get("preview") or ""
        url = v1.get("url") or v2.get("url") or ""
        v_type = v1.get("type") or v2.get("type") or "正常版"
        
        if v1.get("type") == "無碼破解版" or v2.get("type") == "無碼破解版":
            v_type = "無碼破解版"
        elif v1.get("type") == "FC2" or v2.get("type") == "FC2":
            v_type = "FC2"
            
        return {
            "code": v1.get("code") or v2.get("code"),
            "title": v1.get("title") or v2.get("title"),
            "cover": cover,
            "preview": preview,
            "url": url,
            "type": v_type,
            "actress": final_actress,
            "relative_time": v1.get("relative_time") or v2.get("relative_time"),
            "upload_date": v1.get("upload_date") or v2.get("upload_date")
        }

    def get_home_videos(self, url=None):
        if not url:
            url = "https://tktube.com/zh/"
            
        page_num = 1
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            page_num = int(page_match.group(1))
            
        # At this point, script.js always passes a tktube url
        target_url = self.format_tktube_url(url, page_num)
        
        success, html = fetch_html_content(target_url)
        if not success:
            return {"videos": [], "total_pages": 1, "current_page": page_num}
            
        res = self.parse_tktube_home_videos(html, target_url)
        # We do NOT run enrich_videos_with_metadata here because it causes massive timeouts
        # Other sites will only be used to fetch actress names when the user uses the search function
        
        return res

    def fetch_page_and_parse_dates(self, base_url, page_num):
        if "tktube.com" in base_url:
            url = self.format_tktube_url(base_url, page_num)
        else:
            clean_url = re.sub(r'[?&]page=\d+', '', base_url)
            if not clean_url.endswith('/'):
                clean_url += '/'
            url = f"{clean_url}page/{page_num}/" if page_num > 1 else clean_url
                
        success, html = fetch_html_content(url)
        if not success:
            return []
            
        try:
            if "tktube.com" in base_url:
                blocks = html.split('<div class="item')[1:]
                results = []
                seen_codes = set()
                for block in blocks:
                    href_m = re.search(r'href="([^"]+)"', block)
                    if not href_m: continue
                    video_url = href_m.group(1)
                    
                    title_m = re.search(r'alt="([^"]+)"', block)
                    if not title_m:
                        title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', block, re.DOTALL)
                    title = title_m.group(1).strip() if title_m else ""
                    
                    img_url = ""
                    for attr in ["data-original", "data-src", "src"]:
                        img_m = re.search(attr + r'="([^"]+)"', block)
                        if img_m and img_m.group(1) and not any(x in img_m.group(1) for x in ["placeholder", "clear.gif", "transparent"]):
                            img_url = img_m.group(1)
                            break
                    if not img_url:
                        img_m = re.search(r'src="([^"]+)"', block)
                        img_url = img_m.group(1) if img_m else ""
                    
                    preview_m = re.search(r'data-preview="([^"]+)"', block)
                    preview_url = preview_m.group(1) if preview_m else ""
                    
                    if video_url.startswith('/'):
                        video_url = "https://tktube.com" + video_url
                        
                    code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', title.lower())
                    if not code_m:
                        code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', video_url.lower())
                        
                    if code_m:
                        code = code_m.group(1).upper()
                    else:
                        continue
                        
                    if code in seen_codes:
                        continue
                    seen_codes.add(code)
                    
                    date_m = re.search(r'<div class="added">\s*<em>([^<]+)</em>', block)
                    if not date_m:
                        date_m = re.search(r'<em>(\d{4}-\d{2}-\d{2})</em>', block)
                    upload_date = date_m.group(1).strip() if date_m else ""
                    
                    clean_title = title.replace(code, "").replace(code.lower(), "").strip()
                    clean_title = re.sub(r'[\[【\(（].*?[\]】\)）]', '', clean_title).strip()
                    clean_title = re.sub(r'^(hd|1080p|720p|高清|字幕|中字)\s*', '', clean_title, flags=re.IGNORECASE).strip()
                    if not clean_title:
                        clean_title = f"{code} 影片"
                    
                    results.append({
                        "code": code,
                        "title": clean_title,
                        "cover": img_url,
                        "url": video_url,
                        "preview": preview_url,
                        "type": "無碼破解版",
                        "actress": parse_actress_from_title(title),
                        "upload_date": upload_date,
                        "relative_time": f"加入日期: {upload_date}",
                        "source": "tktube"
                    })
                return results
            else:
                parsed_res = self.parse_home_videos(html, url)
                return parsed_res.get("videos", [])
        except Exception as e:
            return []

    def scan_pages_for_date(self, base_url, target_prefix):
        if not target_prefix:
            return []
            
        tktube_base = None
        if "javhdporn.net" in base_url:
            if "censored" in base_url:
                tktube_base = "https://tktube.com/zh/categories/d7925a1dc9f80c4da5a47d8bf0ffb1d6/"
            elif "decensored" in base_url:
                tktube_base = "https://tktube.com/zh/categories/454545388bfe05b5b43cdc4fb9496ac6/"
            else:
                tktube_base = "https://tktube.com/zh/"
        elif "supjav.com" in base_url:
            tktube_base = "https://tktube.com/zh/categories/fc2/"
            
        scan_url = tktube_base if tktube_base else base_url
        success, html = fetch_html_content(scan_url)
        total_pages = 100
        if success:
            if "tktube.com" in scan_url:
                total_match = re.search(r'Total:(\d+)', html)
                if total_match:
                    total_pages = min(int(total_match.group(1)), 500)
                else:
                    total_pages = 200
            else:
                page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
                if page_nums:
                    total_pages = max(page_nums)
                
        low = 1
        high = total_pages
        target_page = -1
        
        while low <= high:
            mid = (low + high) // 2
            time.sleep(0.05)
            videos = self.fetch_page_and_parse_dates(scan_url, mid)
            if not videos:
                high = mid - 1
                continue
                
            newest_date = videos[0].get('upload_date', '')
            oldest_date = videos[-1].get('upload_date', '')
            
            has_match = any(v.get('upload_date', '').startswith(target_prefix) for v in videos)
            if has_match:
                target_page = mid
                break
                
            if oldest_date and oldest_date > target_prefix:
                low = mid + 1
            else:
                high = mid - 1
                
        if target_page == -1:
            matching_pages = []
            for p in range(1, 6):
                time.sleep(0.05)
                videos = self.fetch_page_and_parse_dates(scan_url, p)
                if any(v.get('upload_date', '').startswith(target_prefix) for v in videos):
                    matching_pages.append(p)
            return matching_pages
            
        matching_pages = []
        for p in range(max(1, target_page - 3), min(total_pages + 1, target_page + 4)):
            time.sleep(0.05)
            videos = self.fetch_page_and_parse_dates(scan_url, p)
            if videos and any(v.get('upload_date', '').startswith(target_prefix) for v in videos):
                matching_pages.append(p)
                
        return sorted(list(set(matching_pages)))

    def get_embed_url(self, url):
        if not url: return ""
        if "missav" in url:
            m = re.search(r'missav\.[a-z]+/(?:zh/|ja/|tw/|cn/|en/)?([^/?#]+)', url)
            if m:
                video_code = m.group(1)
                target_url = f"https://missav.ws/play/{video_code}"
                encoded_url = base64.b64encode(target_url.encode('utf-8')).decode('utf-8')
                return f"http://127.0.0.1:{proxy_port}/missav_proxy?url={encoded_url}"
            return url
            
        if "tktube.com" in url:
            m = re.search(r'/([0-9]+)/', url)
            if m:
                video_id = m.group(1)
                embed_target = f"https://tktube.com/zh/embed/{video_id}/"
                encoded_url = base64.b64encode(embed_target.encode('utf-8')).decode('utf-8')
                return f"http://127.0.0.1:{proxy_port}/tktube_proxy?url={encoded_url}"
            return url
            
        if "tcav.85xvideo.com" in url:
            success, html = fetch_html_content(url)
            if success:
                m3u8_matches = re.findall(r'https?://[^"\']+\.m3u8', html)
                if m3u8_matches:
                    m3u8_url = m3u8_matches[0]
                    import urllib.parse
                    player_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>HLS Player</title>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
    <style>
        body, html {{ margin:0; padding:0; width:100%; height:100%; background:#000; overflow:hidden; }}
        video {{ width:100%; height:100%; object-fit:contain; }}
    </style>
</head>
<body>
    <video id="video" controls playsinline></video>
    <script>
        var video = document.getElementById('video');
        var videoSrc = '{m3u8_url}';
        if (Hls.isSupported()) {{
            var hls = new Hls({{
                maxBufferLength: 60,
                maxMaxBufferLength: 120,
                enableWorker: true,
                lowLatencyMode: true
            }});
            hls.loadSource(videoSrc);
            hls.attachMedia(video);
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = videoSrc;
        }}
    </script>
</body>
</html>"""
                    encoded_html = urllib.parse.quote(player_html)
                    return f"data:text/html;charset=utf-8,{encoded_html}"
            return url
            
        if "javhdporn" in url:
            encoded_url = base64.b64encode(url.encode('utf-8')).decode('utf-8')
            return f"http://127.0.0.1:{proxy_port}/javhdporn_proxy?url={encoded_url}"
            
        if "supjav" in url:
            encoded_url = base64.b64encode(url.encode('utf-8')).decode('utf-8')
            return f"http://127.0.0.1:{proxy_port}/supjav_proxy?url={encoded_url}"
            
        success, html = fetch_html_content(url)
        if not success:
            return url
            
        try:
            iframes = re.findall(r'<iframe\s+[^>]*?src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            for src in iframes:
                lower_src = src.lower()
                if 'ad' in lower_src and 'load' not in lower_src:
                    continue
                if 'banner' in lower_src or 'pop' in lower_src:
                    continue
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    parsed_domain = urlparse(url)
                    src = f"{parsed_domain.scheme}://{parsed_domain.netloc}{src}"
                return src
            return url
        except Exception as e:
            safe_print("Error fetching embed:", e)
            return url

    def fetch_tcav_info(self, ccode):
        url = f"https://tcav.85xvideo.com/?s={ccode}"
        success, html = fetch_html_content(url)
        if not success:
            return None
            
        try:
            img_matches = re.finditer(r'<img\s+post-id="(\d+)"([^>]*?)>', html, re.IGNORECASE)
            for m in img_matches:
                post_id, img_attrs = m.groups()
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', img_attrs)
                alt = alt_m.group(1).strip() if alt_m else ""
                
                img_url = ""
                for attr in ["data-original", "data-src", "src"]:
                    img_m = re.search(attr + r'=["\']([^"\']+)["\']', img_attrs)
                    if img_m and img_m.group(1):
                        val = img_m.group(1).strip()
                        if not any(x in val for x in ["placeholder", "clear.gif", "transparent"]):
                            img_url = val
                            break
                if not img_url:
                    img_m = re.search(r'src=["\']([^"\']+)["\']', img_attrs)
                    img_url = img_m.group(1).strip() if img_m else ""
                    
                img_pos = m.start()
                context = html[max(0, img_pos - 400) : min(len(html), img_pos + 1200)]
                
                hrefs = re.findall(r'href="([^"]+)"', context)
                detail_url = ""
                for h in hrefs:
                    if h.startswith("https://tcav.85xvideo.com/") and not any(x in h for x in ["/category/", "/tag/", "/feed/", "/page/", "wp-json", "xmlrpc"]):
                        if h != "https://tcav.85xvideo.com/":
                            detail_url = h
                            break
                            
                if detail_url:
                    slug = detail_url.split('/')[-2] if detail_url.endswith('/') else detail_url.split('/')[-1]
                    slug_decoded = urllib.parse.unquote(slug).lower()
                    ccode_clean = ccode.lower()
                    
                    if ccode_clean in slug_decoded or ccode_clean.replace("-", "") in slug_decoded or ccode_clean in alt.lower():
                        return {
                            "url": detail_url,
                            "img": img_url,
                            "preview": "",
                            "type": "FC2" if "FC2" in ccode.upper() else "無碼破解版"
                        }
            return None
        except Exception as e:
            safe_print("TCAV parse error:", e)
            return None

    def parse_tcav_home_videos(self, html, url=""):
        if not html:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        current_page = 1
        page_match = re.search(r'[?&]paged?=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        
        try:
            total_pages = current_page
            page_nums = [int(p) for p in re.findall(r'/page/(\d+)', html)]
            if page_nums:
                total_pages = max(max(page_nums), current_page)
                
            img_matches = re.finditer(r'<img\s+post-id="(\d+)"([^>]*?)>', html, re.IGNORECASE)
            
            results = []
            seen_codes = set()
            import urllib.parse
            
            for m in img_matches:
                post_id, img_attrs = m.groups()
                
                alt_m = re.search(r'alt=["\']([^"\']+)["\']', img_attrs)
                alt = alt_m.group(1).strip() if alt_m else ""
                
                img_url = ""
                for attr in ["data-original", "data-src", "src"]:
                    img_m = re.search(attr + r'=["\']([^"\']+)["\']', img_attrs)
                    if img_m and img_m.group(1):
                        val = img_m.group(1).strip()
                        if not any(x in val for x in ["placeholder", "clear.gif", "transparent"]):
                            img_url = val
                            break
                if not img_url:
                    img_m = re.search(r'src=["\']([^"\']+)["\']', img_attrs)
                    img_url = img_m.group(1).strip() if img_m else ""
                    
                img_pos = m.start()
                context = html[max(0, img_pos - 400) : min(len(html), img_pos + 1200)]
                
                hrefs = re.findall(r'href="([^"]+)"', context)
                detail_url = ""
                for h in hrefs:
                    if h.startswith("https://tcav.85xvideo.com/") and not any(x in h for x in ["/category/", "/tag/", "/feed/", "/page/", "wp-json", "xmlrpc"]):
                        if h != "https://tcav.85xvideo.com/":
                            detail_url = h
                            break
                            
                if not detail_url:
                    continue
                    
                slug = detail_url.split('/')[-2] if detail_url.endswith('/') else detail_url.split('/')[-1]
                slug_decoded = urllib.parse.unquote(slug)
                
                code_match = re.search(r'([a-zA-Z0-9]+-[0-9]+)', slug_decoded)
                if code_match:
                    code = code_match.group(1).upper()
                else:
                    code_match = re.search(r'([a-zA-Z0-9]+-[0-9]+)', alt)
                    if code_match:
                        code = code_match.group(1).upper()
                    else:
                        code = slug_decoded.split('%')[0].split('-')[0].upper()
                        
                title = alt.replace(code, "").replace(code.lower(), "").replace("-", " ").strip()
                if not title:
                    title = slug_decoded.replace(code, "").replace("-", " ").strip()
                if not title:
                    title = alt
                    
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                
                results.append({
                    "code": code,
                    "title": title,
                    "cover": img_url,
                    "url": detail_url,
                    "preview": "",
                    "type": "FC2" if "FC2" in code else "正常版",
                    "actress": "未知女優",
                    "upload_date": "2026-05-18",
                    "relative_time": "最新",
                    "source": "tcav"
                })
                
            return {
                "videos": results,
                "total_pages": total_pages,
                "current_page": current_page
            }
        except Exception as e:
            safe_print("TCAV parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": current_page}

    def get_tcav_home_videos(self, url=None):
        if not url or url == "tcav":
            url = "https://tcav.85xvideo.com/"
        elif url.startswith("tcav"):
            page_match = re.search(r'[?&]page=(\d+)', url)
            if page_match:
                url = f"https://tcav.85xvideo.com/?paged={page_match.group(1)}"
            else:
                url = "https://tcav.85xvideo.com/"
            
        current_page = 1
        page_match = re.search(r'[?&]paged?=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
            
        success, html = fetch_html_content(url)
        if not success:
            return {"videos": [], "total_pages": 1, "current_page": current_page}
            
        res = self.parse_tcav_home_videos(html, url)
        if res and "videos" in res:
            res["videos"] = self.enrich_videos_with_metadata(res["videos"])
        return res

    def parse_tktube_home_videos(self, html, url=""):
        if not html:
            return {"videos": [], "total_pages": 1, "current_page": 1}
        current_page = 1
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        else:
            slash_match = re.search(r'/zh/(\d+)/?$', url)
            if not slash_match:
                slash_match = re.search(r'/(\d+)/?$', url)
            if slash_match:
                current_page = int(slash_match.group(1))
            
        try:
            total_pages = current_page
            total_match = re.search(r'Total:(\d+)', html)
            if total_match:
                total_pages = int(total_match.group(1))
            else:
                total_change_match = re.search(r'_pagechange\([^,]+,\s*(\d+)\)', html)
                if total_change_match:
                    total_pages = int(total_change_match.group(1))
                else:
                    page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
                    if page_nums:
                        total_pages = max(max(page_nums), current_page)
                    else:
                        total_pages = max(current_page + 10, 50)
                
            blocks = html.split('<div class="item')[1:]
            results = []
            seen_codes = set()
            
            for block in blocks:
                href_m = re.search(r'href="([^"]+)"', block)
                if not href_m: continue
                video_url = href_m.group(1)
                
                title_m = re.search(r'alt="([^"]+)"', block)
                if not title_m:
                    title_m = re.search(r'<strong class="title">\s*(.*?)\s*</strong>', block, re.DOTALL)
                title = title_m.group(1).strip() if title_m else ""
                
                img_url = ""
                for attr in ["data-original", "data-src", "src"]:
                    img_m = re.search(attr + r'="([^"]+)"', block)
                    if img_m and img_m.group(1) and not any(x in img_m.group(1) for x in ["placeholder", "clear.gif", "transparent"]):
                        img_url = img_m.group(1)
                        break
                if not img_url:
                    img_m = re.search(r'src="([^"]+)"', block)
                    img_url = img_m.group(1) if img_m else ""
                
                preview_m = re.search(r'data-preview="([^"]+)"', block)
                preview_url = preview_m.group(1) if preview_m else ""
                
                if video_url.startswith('/'):
                    video_url = "https://tktube.com" + video_url
                    
                code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', title.lower())
                if not code_m:
                    code_m = re.search(r'([a-zA-Z0-9]+-ppv-\d+|[a-zA-Z0-9]+-\d+(_\d+)?|fc2-ppv-\d+|fc2-\d+)', video_url.lower())
                
                if code_m:
                    code = code_m.group(1).upper()
                else:
                    continue
                    
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                
                date_m = re.search(r'<div class="added">\s*<em>([^<]+)</em>', block)
                if not date_m:
                    date_m = re.search(r'<em>(\d{4}-\d{2}-\d{2})</em>', block)
                upload_date = date_m.group(1).strip() if date_m else ""
                
                clean_title = title.replace(code, "").replace(code.lower(), "").strip()
                clean_title = re.sub(r'[\[【\(（].*?[\]】\)）]', '', clean_title).strip()
                clean_title = re.sub(r'^(hd|1080p|720p|高清|字幕|中字)\s*', '', clean_title, flags=re.IGNORECASE).strip()
                if not clean_title:
                    clean_title = f"{code} 影片"
                
                results.append({
                    "code": code,
                    "title": clean_title,
                    "cover": img_url,
                    "url": video_url,
                    "preview": preview_url,
                    "type": "無碼破解版",
                    "actress": parse_actress_from_title(title),
                    "upload_date": upload_date,
                    "relative_time": f"加入日期: {upload_date}",
                    "source": "tktube"
                })
                
            return {
                "videos": results,
                "total_pages": total_pages,
                "current_page": current_page
            }
        except Exception as e:
            safe_print("TKTube parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": current_page}

    def format_tktube_url(self, base_url, page_num):
        if page_num <= 1:
            return base_url
        
        clean_url = re.sub(r'([?&]page=\d+|\/zh\/\d+\/|\/\d+\/)$', '', base_url)
        if not clean_url.endswith('/'):
            clean_url += '/'
            
        if clean_url in ['https://tktube.com/zh/', 'https://tktube.com/zh/latest-updates/']:
            return f"https://tktube.com/zh/latest-updates/{page_num}/"
            
        if 'tktube.com/zh/' in clean_url:
            return f"{clean_url}{page_num}/"
            
        return f"{clean_url}?page={page_num}"

    def get_tktube_home_videos(self, url=None):
        log_file = "dist/debug_pagination.log"
        try:
            os.makedirs("dist", exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"\n--- TKTube Request: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                lf.write(f"Incoming URL: {url}\n")
        except Exception:
            pass

        if not url or url == "tktube":
            url = "https://tktube.com/zh/latest-updates/"
        elif url.startswith("tktube"):
            page_match = re.search(r'[?&]page=(\d+)', url)
            if page_match:
                url = f"https://tktube.com/zh/latest-updates/?page={page_match.group(1)}"
            else:
                url = "https://tktube.com/zh/latest-updates/"
            
        current_page = 1
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            current_page = int(page_match.group(1))
        else:
            slash_match = re.search(r'/(\d+)/?$', url)
            if slash_match:
                current_page = int(slash_match.group(1))
        
        base_url = re.sub(r'[?&]page=\d+', '', url)
        base_url = re.sub(r'/\d+/?$', '/', base_url)
        if not base_url.endswith('/'):
            base_url += '/'
        
        target_url = self.format_tktube_url(base_url, current_page)
        
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Parsed Page: {current_page}\n")
                lf.write(f"Formatted Base URL: {base_url}\n")
                lf.write(f"Target URL: {target_url}\n")
        except Exception:
            pass

        success, html = fetch_html_content(target_url)
        
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Fetch HTML Success: {success} (Length: {len(html) if success else 0})\n")
        except Exception:
            pass

        if not success:
            return {"videos": [], "total_pages": 1, "current_page": current_page}
            
        res = self.parse_tktube_home_videos(html, target_url)
        if res and "videos" in res:
            res["videos"] = self.enrich_videos_with_metadata(res["videos"])
        
        try:
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f"Parsed Videos Count: {len(res.get('videos', []))}\n")
                lf.write(f"Returned Current Page: {res.get('current_page')}\n")
                lf.write(f"Returned Total Pages: {res.get('total_pages')}\n")
        except Exception:
            pass

        return res

    def parse_tktube_html_client(self, html, url):
        try:
            res = self.parse_tktube_home_videos(html, url)
            if res and "videos" in res:
                res["videos"] = self.enrich_videos_with_metadata(res["videos"])
            return res
        except Exception as e:
            safe_print("Client HTML parse error:", e)
            return {"videos": [], "total_pages": 1, "current_page": 1}

    def parse_tktube_total_pages_client(self, html):
        try:
            total_pages = 1
            total_match = re.search(r'Total:(\d+)', html)
            if total_match:
                total_pages = int(total_match.group(1))
            else:
                total_change_match = re.search(r'_pagechange\([^,]+,\s*(\d+)\)', html)
                if total_change_match:
                    total_pages = int(total_change_match.group(1))
                else:
                    page_nums = [int(p) for p in re.findall(r'page=(\d+)', html)]
                    if page_nums:
                        total_pages = max(page_nums)
                    else:
                        total_pages = 50
            return total_pages
        except Exception as e:
            safe_print("Client HTML parse total pages error:", e)
            return 50

    def parse_page_dates_client(self, html, target_prefix):
        try:
            blocks = html.split('<div class="item')[1:]
            if not blocks:
                return {"newest_date": "", "oldest_date": "", "has_match": False}
            
            dates = []
            for block in blocks:
                date_m = re.search(r'<div class="added">\s*<em>([^<]+)</em>', block)
                if not date_m:
                    date_m = re.search(r'<em>(\d{4}-\d{2}-\d{2})</em>', block)
                if date_m:
                    dates.append(date_m.group(1).strip())
            
            if not dates:
                return {"newest_date": "", "oldest_date": "", "has_match": False}
                
            newest = dates[0]
            oldest = dates[-1]
            has_match = any(d.startswith(target_prefix) for d in dates)
            
            return {
                "newest_date": newest,
                "oldest_date": oldest,
                "has_match": has_match
            }
        except Exception as e:
            safe_print("Client HTML parse page dates error:", e)
            return {"newest_date": "", "oldest_date": "", "has_match": False}

    def init_playwright_background(self):
        try:
            from playwright.sync_api import sync_playwright
            safe_print("Playwright: Initializing worker thread headless browser...")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-web-security',
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox'
                    ]
                )
                browser_context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720}
                )
                self.browser_context = browser_context
                global PROXY_SERVER
                if PROXY_SERVER:
                    PROXY_SERVER.playwright_cookies = {}
                    
                safe_print("Playwright: Headless Chromium worker thread active!")
                
                browser_context.add_cookies([
                    {
                        'name': 'existmag',
                        'value': 'all',
                        'domain': '.javbus.com',
                        'path': '/'
                    },
                    {
                        'name': 'existmag',
                        'value': 'all',
                        'domain': 'www.javbus.com',
                        'path': '/'
                    }
                ])
                
                while True:
                    if sys.is_finalizing():
                        break
                    try:
                        task = self.playwright_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    if task is None:
                        break
                    
                    # Support two task formats:
                    #  3-tuple: (url, response_queue, timeout_ms) -> regular HTML fetch
                    #  4-tuple: ('TKTUBE_EXTRACT', embed_url, response_queue, timeout_ms) -> full tktube automation
                    if isinstance(task, tuple) and len(task) == 4 and task[0] == 'TKTUBE_EXTRACT':
                        _, embed_url, response_queue, timeout_ms = task
                        # === TKTUBE EXTRACTION MODE ===
                        # Run full browser automation: block ads, click Open AD, click Skip, capture video URL
                        captured_urls = []
                        try:
                            page = browser_context.new_page()
                            
                            def tktube_route_handler(route):
                                req = route.request
                                req_url = req.url
                                resource_type = req.resource_type
                                
                                # Capture video stream URLs
                                if any(x in req_url for x in ['.m3u8', '.mp4', 'get_file']):
                                    captured_urls.append(req_url)
                                
                                # Block ad network - fulfill with empty VAST
                                if any(x in req_url.lower() for x in ['magsrv.com', 'exo_pc', 'adlib', 'vast', 'rv16888', 'tklivechat']):
                                    try:
                                        route.fulfill(status=200, content_type='application/xml', body='<VAST version="3.0"></VAST>')
                                    except:
                                        pass
                                    return
                                
                                # Block heavy resources from non-tktube domains
                                if resource_type in ('image', 'font', 'stylesheet') and 'tktube.com' not in req_url:
                                    try: route.abort()
                                    except: pass
                                    return
                                
                                try: route.continue_()
                                except: pass
                            
                            page.route('**/*', tktube_route_handler)
                            page.add_init_script('window.open = function(){return null;}; window.onbeforeunload = null;')
                            
                            page.goto(embed_url, wait_until='domcontentloaded', timeout=timeout_ms)
                            page.wait_for_timeout(2000)
                            
                            # Phase 1: Click "Open AD & Play" button programmatically to bypass overlays
                            open_ad_clicked = False
                            for _ in range(30):
                                btn = (page.query_selector('button.kt-api-btn-start') or
                                       page.query_selector('.kt-api-btn-start') or
                                       page.query_selector('[class*="kt-api-btn"]'))
                                if not btn:
                                    btn = page.evaluate_handle("""
                                        () => { for(let el of document.querySelectorAll('button,a')){
                                            if((el.innerText||'').toLowerCase().includes('open ad')) return el;
                                        } return null; }
                                    """)
                                    if btn and btn.as_element() is None: btn = None
                                
                                if btn:
                                    try:
                                        page.evaluate("el => el.click()", btn)
                                        open_ad_clicked = True
                                        safe_print('[TKTube] Clicked Open AD programmatically')
                                    except:
                                        pass
                                    break
                                page.wait_for_timeout(300)
                                    
                            # Fallback: If Open AD is not found, try standard play button
                            if not open_ad_clicked:
                                play_btn = page.query_selector('.fp-play') or page.query_selector('.fp-ui')
                                if play_btn:
                                    try:
                                        page.evaluate("el => el.click()", play_btn)
                                        open_ad_clicked = True
                                        safe_print('[TKTube] Clicked standard play button programmatically as fallback')
                                    except:
                                        pass
                            
                            # Phase 2: Wait for ad, click Skip AD, capture URL
                            page.wait_for_timeout(3000)
                            for _ in range(60):
                                if captured_urls: break
                                # Try to click skip button
                                skip = page.evaluate_handle("""
                                    () => {
                                        let sel = document.querySelector('.fp-ad-skip,.fp-skip,[class*="fp-skip"],[class*="skip-ad"]');
                                        if(sel) return sel;
                                        for(let el of document.querySelectorAll('*')){
                                            if(el.children.length>3) continue;
                                            let t=(el.innerText||'').trim();
                                            if(t && t.toLowerCase().includes('skip ad') &&
                                               (el.offsetParent!==null||window.getComputedStyle(el).position==='fixed')) return el;
                                        } return null;
                                    }
                                """)
                                if skip and skip.as_element():
                                    try:
                                        page.evaluate("el => el.click()", skip)
                                        safe_print('[TKTube] Clicked Skip AD programmatically')
                                    except:
                                        pass
                                    page.wait_for_timeout(1500)
                                # Check <video> src too
                                if not captured_urls:
                                    vsrc = page.evaluate("""() => { let v=document.querySelector('video'); return (v&&v.src&&v.src.startsWith('http'))?v.src:null; }""")
                                    if vsrc: captured_urls.append(vsrc); break
                                page.wait_for_timeout(300)
                            
                            page.close()
                            video_url = captured_urls[-1] if captured_urls else None
                            safe_print(f'[TKTube] Extracted URL: {str(video_url)[:80] if video_url else "NONE"}')
                            response_queue.put(video_url)
                        except Exception as e:
                            safe_print(f'[TKTube] Worker extraction error: {e}')
                            try: page.close()
                            except: pass
                            response_queue.put(None)
                        continue
                    
                    # === REGULAR HTML FETCH MODE ===
                    url, response_queue, timeout_ms = task
                    try:
                        page = browser_context.new_page()
                        
                        def block_ad_and_media(route):
                            request = route.request
                            resource_type = request.resource_type
                            req_url = request.url.lower()
                            
                            block_types = ["image", "font", "stylesheet"]
                            # NOTE: Do NOT block 'media' - that blocks video streams!
                            # Only block specific ad networks by URL
                            ad_keywords = ["google-analytics", "doubleclick", "adservice", "popunder", "exoclick", "juicyads", "trafficjunky", "histats"]
                            
                            if resource_type in block_types or any(kw in req_url for kw in ad_keywords):
                                route.abort()
                            else:
                                route.continue_()
                                
                        page.route("**/*", block_ad_and_media)
                        wait_state = "networkidle" if ("embed" in url or "play" in url) else "domcontentloaded"
                        page.goto(url, wait_until=wait_state, timeout=timeout_ms)
                        
                        if wait_state == "networkidle":
                            # Additional wait for any dynamic video tags to be injected
                            try:
                                page.wait_for_selector('video, source', timeout=2000)
                            except:
                                pass
                                
                        html = page.content()
                        
                        try:
                            if PROXY_SERVER:
                                cookies = browser_context.cookies()
                                PROXY_SERVER.playwright_cookies = {c['name']: c['value'] for c in cookies}
                        except Exception as e:
                            safe_print(f"Failed to extract cookies in worker: {e}")
                            
                        if "existmag" not in html and "javbus.com" in url:
                            page.evaluate('''
                                document.cookie="existmag=all;expires=Thu, 01 Jan 2099 00:00:00 GMT;path=/";
                            ''')
                            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                            html = page.content()
                            
                        page.close()
                        response_queue.put(html)
                    except Exception as e:
                        if not sys.is_finalizing():
                            safe_print(f"Playwright worker error for {url}: {e}")
                        try:
                            page.close()
                        except:
                            pass
                        response_queue.put(None)
                        
                browser.close()
        except Exception as e:
            self.playwright_err = str(e)
            if not sys.is_finalizing():
                safe_print("Playwright worker thread crash/error:", e)

    def playwright_fetch_html(self, url, timeout_ms=15000):
        if not self.browser_context:
            safe_print("Playwright: Worker not ready yet, falling back...")
            return None
            
        response_queue = queue.Queue()
        self.playwright_queue.put((url, response_queue, timeout_ms))
        
        try:
            html = response_queue.get(timeout=timeout_ms / 1000.0)
            return html
        except Exception as e:
            safe_print(f"Playwright fetch timeout/error for {url}: {e}")
            return None

    def playwright_extract_tktube_url(self, embed_url, timeout_ms=30000):
        """Queue a TKTUBE_EXTRACT task into the Playwright worker thread
        (all Playwright ops must run in the same thread as browser_context)."""
        if not self.browser_context:
            return None
        response_queue = queue.Queue()
        self.playwright_queue.put(('TKTUBE_EXTRACT', embed_url, response_queue, timeout_ms))
        try:
            return response_queue.get(timeout=timeout_ms / 1000.0 + 5)
        except Exception as e:
            safe_print(f'[TKTube] Queue timeout/error: {e}')
            return None

    def __del__(self):
        try:
            self.playwright_queue.put(None)
        except:
            pass

    def heal_favorites_background(self):
        time.sleep(1.0)
        
        def is_invalid_actress(actress):
            if not actress:
                return True
            actress_clean = str(actress).replace('*', '').strip()
            return actress_clean in ("", "未知", "未知女優", "新加入", "女優", "None", "undefined")
            
        needs_healing = []
        for idx, item in enumerate(self.data):
            raw = item.get('raw') or item.get('code') or ""
            ccode = clean_code(raw)
            if (item.get('code') != ccode.upper()) or (not item.get('url')) or (not item.get('found')) or is_invalid_actress(item.get('actress')):
                needs_healing.append((idx, raw, ccode))
                
        if not needs_healing:
            return
            
        safe_print(f"Healer: Automatically cleaning and healing {len(needs_healing)} favorites in background...")
        
        changed = False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_to_idx = {
                executor.submit(self.fetch_video_info, raw): idx 
                for idx, raw, ccode in needs_healing
            }
            
            for future in concurrent.futures.as_completed(future_to_idx):
                if sys.is_finalizing():
                    break
                idx = future_to_idx[future]
                try:
                    res = future.result()
                    if res and res.get('found'):
                        original_id = self.data[idx].get('id')
                        original_actress = self.data[idx].get('actress')
                        scraped_actress = res.get('actress')
                        
                        if is_invalid_actress(original_actress) and not is_invalid_actress(scraped_actress):
                            final_actress = scraped_actress
                        else:
                            final_actress = original_actress if not is_invalid_actress(original_actress) else scraped_actress
                            
                        meta_info = fetch_metadata_info(res["code"], self)
                        final_title = self.data[idx].get('title', '')
                        if meta_info:
                            if meta_info.get("actress") and meta_info["actress"] != "未知":
                                final_actress = meta_info["actress"]
                            if meta_info.get("title") and (not final_title or res["code"] in final_title):
                                prefix = ""
                                m_prefix = re.match(r'(\[[^\]]+\])', final_title)
                                if m_prefix: prefix = m_prefix.group(1) + " "
                                final_title = prefix + meta_info["title"]
                            
                        existing_upload_date = self.data[idx].get('upload_date')
                        new_upload_date = (meta_info.get("date") if meta_info else "") or res.get("upload_date") or existing_upload_date or ""
                        
                        self.data[idx] = {
                            "id": original_id,
                            "raw": self.data[idx].get('raw') or self.data[idx].get('code'),
                            "clean": res["clean"],
                            "code": res["code"],
                            "title": final_title,
                            "url": res["url"],
                            "img": res["img"],
                            "preview": res.get("preview") or self.data[idx].get("preview") or "",
                            "found": True,
                            "type": res["type"],
                            "actress": final_actress,
                            "upload_date": new_upload_date,
                            "relative_time": "已修復: " + time.strftime("%Y-%m-%d")
                        }
                        changed = True
                except Exception as e:
                    safe_print(f"Healer: Failed to heal favorite index {idx}: {e}")
                    
        if changed:
            safe_print("Healer: Healing complete! Saving updated JSON and updating web interface...")
            self.save_videos(self.data)
            try:
                webview.windows[0].evaluate_js("if(typeof loadData === 'function') { loadData(); }")
            except Exception as e:
                pass

    def copy_to_clipboard(self, text):
        import ctypes
        try:
            if not ctypes.windll.user32.OpenClipboard(None):
                return False
            ctypes.windll.user32.EmptyClipboard()
            text_bytes = text.encode('utf-16le')
            h_mem = ctypes.windll.kernel32.GlobalAlloc(0x0002, len(text_bytes) + 2)
            if not h_mem:
                ctypes.windll.user32.CloseClipboard()
                return False
            p_mem = ctypes.windll.kernel32.GlobalLock(h_mem)
            if not p_mem:
                ctypes.windll.kernel32.GlobalFree(h_mem)
                ctypes.windll.user32.CloseClipboard()
                return False
            ctypes.memmove(p_mem, text_bytes, len(text_bytes))
            ctypes.memset(p_mem + len(text_bytes), 0, 2)
            ctypes.windll.kernel32.GlobalUnlock(h_mem)
            ctypes.windll.user32.SetClipboardData(13, h_mem)
            ctypes.windll.user32.CloseClipboard()
            return True
        except Exception as e:
            safe_print(f"Clipboard Error: {e}")
            return False

    def get_version(self):
        return self.current_version

    def check_for_updates(self):
        try:
            res = self.version_manager.check_for_updates()
            return res
        except Exception as e:
            safe_print(f"check_for_updates error: {e}")
            return None

    def start_update(self, download_url):
        if self.update_progress["status"] in ["downloading", "extracting", "applying"]:
            return {"success": False, "msg": "更新已在進行中"}
        
        self.update_progress = {
            "status": "downloading",
            "percent": 0,
            "detail": "準備下載更新檔案...",
            "error": None
        }
        self._notify_js_progress()
        threading.Thread(target=self._run_update_flow, args=(download_url,), daemon=True).start()
        return {"success": True, "msg": "更新流程已成功啟動"}

    def get_update_progress(self):
        return self.update_progress

    def _notify_js_progress(self):
        if self._window:
            try:
                status = self.update_progress["status"]
                percent = self.update_progress["percent"]
                detail = self.update_progress["detail"]
                error = self.update_progress["error"] or ""
                
                detail_esc = detail.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                error_esc = error.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                
                js = f"if (typeof onUpdateProgress === 'function') {{ onUpdateProgress('{status}', {percent}, '{detail_esc}', '{error_esc}'); }}"
                self._window.evaluate_js(js)
            except Exception as e:
                safe_print(f"Failed to notify JS progress: {e}")

    def _run_update_flow(self, download_url):
        try:
            def progress_callback(downloaded, total):
                if total > 0:
                    percent = int((downloaded / total) * 40)
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    self.update_progress = {
                        "status": "downloading",
                        "percent": percent,
                        "detail": f"正在下載更新: {downloaded_mb:.2f}MB / {total_mb:.2f}MB ({int((downloaded/total)*100)}%)",
                        "error": None
                    }
                    self._notify_js_progress()
                    
            zip_path = self.version_manager.download_update(download_url, progress_callback)
            if not zip_path:
                raise Exception("下載更新檔案失敗，請檢查網路連線或稍後再試。")
                
            self.update_progress = {
                "status": "extracting",
                "percent": 40,
                "detail": "正在解壓縮更新檔案...",
                "error": None
            }
            self._notify_js_progress()
            
            for p in range(40, 70, 5):
                time.sleep(0.1)
                self.update_progress["percent"] = p
                self._notify_js_progress()
                
            extract_dir = self.version_manager.extract_update(zip_path)
            if not extract_dir:
                raise Exception("解壓縮更新檔案失敗，檔案可能已損壞。")
                
            self.update_progress["percent"] = 70
            self.update_progress["detail"] = "解壓縮完成，準備安裝更新..."
            self._notify_js_progress()
            time.sleep(0.3)
            
            self.update_progress = {
                "status": "applying",
                "percent": 80,
                "detail": "正在創建並執行更新腳本...",
                "error": None
            }
            self._notify_js_progress()
            
            success = self.version_manager.apply_update(extract_dir, restart_after=True)
            if success:
                self.update_progress = {
                    "status": "completed",
                    "percent": 100,
                    "detail": "更新檔案佈署成功！程式將於 2 秒後重啟以套用更新...",
                    "error": None
                }
                self._notify_js_progress()
                time.sleep(2.0)
                os._exit(0)
            else:
                raise Exception("無法啟動更新批次腳本，請確認是否有系統權限。")
                
        except Exception as e:
            self.update_progress = {
                "status": "error",
                "percent": 0,
                "detail": f"更新失敗: {str(e)}",
                "error": str(e)
            }
            self._notify_js_progress()

if __name__ == '__main__':
    api = Api()
    html_path = os.path.join(get_resource_path(), 'index.html')
    window_title = f"JApp_{VERSION}"
    window = webview.create_window(window_title, html_path, js_api=api, width=1200, height=800)
    api._window = window
    webview.start(debug=False)

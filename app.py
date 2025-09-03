import asyncio
import re
from urllib.parse import urlparse, urlunparse
from flask import Flask, request, render_template
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

QUALITY_PRIORITY = ["4K", "2K", "2160P", "1440P", "1080P", "720P", "480P", "360P", "240P"]

def normalize_url(link):
    if link.startswith("//"):
        return "https:" + link
    elif link.startswith("/"):
        return "https:" + link
    return link

def strip_query_params(link):
    parsed = urlparse(link)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))

def pick_highest_quality(links):
    normalized = [normalize_url(l) for l in links]
    for q in QUALITY_PRIORITY:
        for l in normalized:
            if q.lower() in l.lower():
                return strip_query_params(l)
    return strip_query_params(normalized[0]) if normalized else None

async def get_m3u8_links(url):
    links = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # request
        page.on("request", lambda req: links.add(req.url) if ".m3u8" in req.url else None)

        # response
        page.on("response", lambda res: links.add(res.url) if ".m3u8" in res.url else None)

        async def handle_response(response):
            try:
                ctype = response.headers.get("content-type") or ""
                if "json" in ctype or "text" in ctype:
                    body = await response.text()
                    pattern = r'(?:https?:\/\/[^\s"\']+|\/\/[^\s"\']+|\/[^\s"\']+)\.m3u8[^\s"\']*'
                    raw_links = re.findall(pattern, body)
                    clean_links = [link.replace(r'\/', '/') for link in raw_links]
                    for l in clean_links:
                        links.add(l)
            except:
                pass

        page.on("response", handle_response)

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        await browser.close()

    return [strip_query_params(normalize_url(l)) for l in links]

def scrape(url):
    return asyncio.run(get_m3u8_links(url))

@app.route("/", methods=["GET", "POST"])
def index():
    results = {}
    if request.method == "POST":
        urls_text = request.form.get("urls")
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(scrape, u): u for u in urls}
            for f in futures:
                links = f.result()
                results[futures[f]] = {
                    "all": links,
                    "best": pick_highest_quality(links)
                }
    return render_template("index.html", results=results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

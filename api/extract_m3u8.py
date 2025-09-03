from playwright.async_api import async_playwright
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
import json
import os

app = FastAPI()

class URLInput(BaseModel):
    urls: list[str]

async def extract_m3u8_links(url):
    m3u8_links = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        def handle_request(request):
            if request.url.endswith('.m3u8'):
                m3u8_links.append(request.url)
        
        page.on('request', handle_request)
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Error loading {url}: {e}")
        
        await browser.close()
    
    high_quality_links = [link for link in m3u8_links if re.search(r'1080|720|high|master|hd', link, re.IGNORECASE)]
    return high_quality_links if high_quality_links else m3u8_links

@app.post("/extract")
async def extract_m3u8(input: URLInput):
    results = {}
    for url in input.urls:
        print(f"Processing {url}...")
        m3u8_links = await extract_m3u8_links(url)
        results[url] = m3u8_links
    
    return {"results": results}

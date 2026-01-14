# The website_loader immediately branches out. Instead of just looking at the home page, 
# it uses Concurrency to look at multiple pages at once: /about, /products, /services, and /solutions.

import requests
from bs4 import BeautifulSoup
from readability import Document
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from app.config import IMPORTANT_PATHS, DEFAULT_TIMEOUT, MAX_CONCURRENT_REQUESTS

def fetch_page(session: requests.Session, url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    try:
        response = session.get(url, timeout=DEFAULT_TIMEOUT, headers=headers)
        response.raise_for_status()

        doc = Document(response.text)
        html = doc.summary()
        soup = BeautifulSoup(html, "html.parser")

        text = soup.get_text(separator=" ", strip=True)
        return text
    except Exception as e:
        print(f"[WARNING] Failed to fetch {url}: {e}")
        return ""

def load_website_content(base_url: str) -> str:
    """Fetches content from multiple important paths of a website concurrently."""
    collected_text = []
    urls = [urljoin(base_url.rstrip("/") + "/", path) for path in IMPORTANT_PATHS]

    with requests.Session() as session:
        # Use ThreadPoolExecutor for concurrent requests
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            # Map fetch_page across all URLs
            results = executor.map(lambda url: fetch_page(session, url), urls)
            
            for text in results:
                if text:
                    collected_text.append(text)

    if not collected_text:
        print(f"[ERROR] Could not extract any content from {base_url}")
        return ""

    return "\n".join(collected_text)


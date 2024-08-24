import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiohttp
from bs4 import BeautifulSoup
import asyncio
import random
from typing import List, Tuple
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    num_results: int = 10

class SearchResult(BaseModel):
    title: str
    url: str

class SearchResponse(BaseModel):
    global_results: List[SearchResult]
    archive_results: List[SearchResult]

async def perform_search(search_url: str, num_results: int, retries: int = 3, backoff_factor: float = 1) -> List[Tuple[str, str]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers) as response:
                    if response.status == 200:
                        soup = BeautifulSoup(await response.text(), 'html.parser')
                        results = []
                        for g in soup.find_all('div', class_='g'):
                            link = g.find('a', href=True)
                            title = g.find('h3')
                            if link and title:
                                href = link['href']
                                url = href.split("&")[0].split("?q=")[-1]
                                results.append((title.text, url))
                        return results[:num_results]
                    elif response.status == 429:
                        raise HTTPException(status_code=429, detail="Rate limit exceeded")
                    else:
                        raise HTTPException(status_code=response.status, detail=f"Unexpected response status: {response.status}")
        except Exception as e:
            if attempt < retries - 1:
                sleep_time = backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(sleep_time)
            else:
                raise HTTPException(status_code=500, detail=f"All {retries} attempts failed. Error: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    global_search_url = f"https://www.google.com/search?q=filetype:pdf+{request.query}"
    archive_search_url = f"https://www.google.com/search?q=site:archive.org+filetype:pdf+{request.query}"

    global_results, archive_results = await asyncio.gather(
        perform_search(global_search_url, request.num_results),
        perform_search(archive_search_url, request.num_results)
    )

    return SearchResponse(
        global_results=[SearchResult(title=title, url=url) for title, url in global_results],
        archive_results=[SearchResult(title=title, url=url) for title, url in archive_results]
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

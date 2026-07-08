import os
import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Universal Video Downloader API")

# Updated options: Uses a modern mobile/desktop User-Agent instead of 'impersonate'
COMMON_YTDL_OPTS = {
    'format': 'bestvideo+bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
}

class URLPayload(BaseModel):
    url: str

def get_video_info(url: str) -> dict:
    """Helper function to extract video metadata and direct stream links."""
    with yt_dlp.YoutubeDL(COMMON_YTDL_OPTS) as ydl:
        try:
            # download=False ensures we only fetch metadata and CDN links
            info = ydl.extract_info(url, download=False)
            return ydl.sanitize_info(info)
        except Exception as e:
            # Catching the error explicitly to see if it's a block or invalid link
            raise HTTPException(status_code=400, detail=f"Extraction failed: {str(e)}")

@app.post("/extract")
async def extract_video_links(payload: URLPayload):
    """
    EXTRACT ENDPOINT (Recommended for Mobile Apps)
    Accepts any share link from YouTube, TikTok, Instagram, or Facebook.
    Returns direct CDN URLs so your mobile app can fetch or play the video.
    """
    info = get_video_info(payload.url)
    
    # Structure the response cleanly for mobile integration
    response_data = {
        "title": info.get("title", "Unknown Title"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "platform": info.get("extractor_key"),
        # 'url' usually holds the best pre-merged stream or primary link
        "direct_download_url": info.get("url"), 
        # Detailed formats if your mobile app wants to let users choose resolutions
        "formats": [
            {
                "format_id": f.get("format_id"),
                "resolution": f.get("resolution"),
                "ext": f.get("ext"),
                "url": f.get("url"),
                "filesize": f.get("filesize")
            } for f in info.get("formats", []) if f.get("url")
        ]
    }
    
    return JSONResponse(content=response_data)


@app.get("/download")
async def download_video_file(url: str = Query(..., description="The social media video URL")):
    """
    DOWNLOAD ENDPOINT
    Downloads the physical file onto the server, then pushes it to the client.
    """
    output_dir = "downloads"
    os.makedirs(output_dir, exist_ok=True)
    
    download_opts = {
        **COMMON_YTDL_OPTS,
        # 'best' tells it to grab a single file that already has video+audio together.
        # '[ext=mp4]' ensures it targets standard web-compatible MP4 files.
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
    }
    
    with yt_dlp.YoutubeDL(download_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if os.path.exists(filename):
                return FileResponse(
                    path=filename, 
                    filename=f"{info.get('title', 'video')}.mp4", 
                    media_type='video/mp4'
                )
            else:
                raise HTTPException(status_code=500, detail="File processing error.")
                
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
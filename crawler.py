from fastapi import FastAPI, Query, HTTPException
import requests
import yt_dlp
import os
import subprocess
import json
import time
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import threading

load_dotenv("keys.env") 

# Configuration variables
RAW_VIDEO_PATH = os.getenv("RAW_VIDEO_PATH", "test_video.mp4")
ENCODED_VIDEO_PATH = os.getenv("ENCODED_VIDEO_PATH", "test_video_encoded.mp4")
LOCAL_THUMBNAIL_PATH = os.getenv("LOCAL_THUMBNAIL_PATH", "thumbnail.webp")
API_KEY = os.getenv("BUNNY_API_KEY")
LIBRARY_ID = os.getenv("LIBRARY_ID")
WP_SITE = os.getenv("WP_SITE")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_PASSWORD = os.getenv("WP_PASSWORD")

auth = HTTPBasicAuth(WP_USERNAME, WP_PASSWORD)
app = FastAPI()

# Global set and lock for tracking video URLs in process.
processing_videos = set()
processing_lock = threading.Lock()

# ... [All your helper functions remain the same] ...

@app.get("/process_video/")
def process_video(video_url: str = Query(...)):
    """
    Process the video from XHamster and create a new WordPress post.
    This version checks if the given video_url is already being processed.
    """
    # Check if the video is already in process.
    with processing_lock:
        if video_url in processing_videos:
            raise HTTPException(status_code=400, detail="This video is already being processed.")
        processing_videos.add(video_url)

    try:
        # Step 1: Extract video info.
        video_download_url, video_title, video_description = get_xhamster_video_info(video_url)
        if not video_download_url:
            return {"status": "failed", "message": "Could not extract video information."}
        
        # Step 2: Download video.
        if not download_video(video_download_url, RAW_VIDEO_PATH):
            return {"status": "failed", "message": "Video download failed."}
        
        # Step 3: Check compatibility.
        print("[DEBUG] Checking video compatibility...")
        if check_mp4_compatibility(RAW_VIDEO_PATH):
            print("[DEBUG] Video is compatible. Skipping encoding.")
            file_to_upload = RAW_VIDEO_PATH
            thumbnail_source = RAW_VIDEO_PATH
            use_bunny_preview = True
        else:
            print("[DEBUG] Video is not compatible. Starting encoding process...")
            if not encode_video(RAW_VIDEO_PATH, ENCODED_VIDEO_PATH):
                return {"status": "failed", "message": "Video encoding failed."}
            print("[DEBUG] Encoding finished.")
            file_to_upload = ENCODED_VIDEO_PATH
            thumbnail_source = ENCODED_VIDEO_PATH
            use_bunny_preview = False
        
        # Step 4: Upload the video file to Bunny.net.
        video_id, preview_url = upload_video(API_KEY, LIBRARY_ID, file_to_upload, video_title)
        if not video_id:
            return {"status": "failed", "message": "Video upload failed."}
        
        # Step 5: Build the iframe embed code.
        iframe_code = (f"<iframe src='https://iframe.mediadelivery.net/embed/{LIBRARY_ID}/{video_id}' "
                       f"width='100%' height='500px' allowfullscreen></iframe>")
        
        # Step 6: Determine thumbnail.
        if use_bunny_preview and preview_url:
            print("[DEBUG] Using Bunny.net previewAnimationUrl for thumbnail.")
            time.sleep(2)  # wait briefly for Bunny.net to process the preview
            if not download_image(preview_url, LOCAL_THUMBNAIL_PATH):
                print("[ERROR] Failed to download preview thumbnail; falling back to local generation.")
                if not generate_animated_thumbnail(thumbnail_source, LOCAL_THUMBNAIL_PATH):
                    return {"status": "failed", "message": "Thumbnail generation failed."}
        else:
            print("[DEBUG] Generating animated thumbnail from the video's midpoint.")
            if not generate_animated_thumbnail(thumbnail_source, LOCAL_THUMBNAIL_PATH):
                return {"status": "failed", "message": "Thumbnail generation failed."}
        
        # Step 7: Create a new WordPress post.
        payload = {
            "title": video_title,
            "content": "",
            "excerpt": video_description,
            "status": "draft",
            "categories": [38],
            "meta": {"tie_embed_code": ""}
        }
        new_post = create_wordpress_post(payload)
        if not new_post:
            return {"status": "failed", "message": "Failed to create new post."}
        new_post_id = new_post.get("id")
        
        # Step 8: Update the post meta and featured media.
        update_wordpress_post(new_post_id, {"meta": {"tie_embed_code": iframe_code}, "excerpt": video_description})
        media_id = upload_thumbnail(LOCAL_THUMBNAIL_PATH, video_title)
        if media_id:
            update_wordpress_post(new_post_id, {"featured_media": media_id})
        
        return {"status": "success", "video_id": video_id, "post_id": new_post_id}
    finally:
        # Remove the video URL from the processing set.
        with processing_lock:
            processing_videos.discard(video_url)

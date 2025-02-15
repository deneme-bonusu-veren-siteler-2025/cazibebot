from fastapi import FastAPI, Query
import requests
import yt_dlp
import os
import subprocess
import json
import time
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv


load_dotenv("keys.env") 

# Now, retrieve variables using os.getenv:
# === Configuration ===

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

# === Helper Function: Get Video Duration ===
def get_video_duration(file_path):
    """
    Use ffprobe to determine the duration (in seconds) of the video.
    """
    try:
        command = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        # Sometimes ffprobe outputs multiple lines. Take the first non-empty line.
        lines = result.stdout.strip().splitlines()
        if not lines:
            raise ValueError("No duration data found")
        duration = float(lines[0])
        print(f"[DEBUG] Video duration: {duration} seconds")
        return duration
    except Exception as e:
        print("[ERROR] Failed to get video duration:", e)
        return None

# === Helper Function: Check MP4 Compatibility ===
def check_mp4_compatibility(file_path):
    """
    Check if the given MP4 file is compatible:
      - Video codec must be 'h264'
      - Audio codec must be 'aac'
    Returns True if compatible; otherwise, False.
    """
    try:
        command = [
            'ffprobe', '-v', 'error',
            '-print_format', 'json',
            '-show_streams', file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        metadata = json.loads(result.stdout)
        video_codec = None
        audio_codec = None
        for stream in metadata.get("streams", []):
            if stream.get("codec_type") == "video":
                video_codec = stream.get("codec_name")
            elif stream.get("codec_type") == "audio":
                audio_codec = stream.get("codec_name")
        print(f"[DEBUG] Video codec: {video_codec}, Audio codec: {audio_codec}")
        return video_codec == "h264" and audio_codec == "aac"
    except Exception as e:
        print("[ERROR] Error checking video compatibility:", e)
        return False

# === Video Processing Helpers ===
def get_xhamster_video_info(video_url):
    """
    Extract the direct video URL, title, and description from XHamster using yt-dlp.
    The yt-dlp options include cookies from 'cookies.json' for bypassing restrictions.
    Returns a tuple: (video_direct_url, title, description)
    """
    ydl_opts = {
        'quiet': True,
        'format': 'best',
        'noplaylist': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0',
        'cookies': 'cookies.json'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_direct_url = info.get("url")
            title = info.get("title", "XHamster Video")
            description = info.get("description", "")
            return video_direct_url, title, description
    except Exception as e:
        print(f"[ERROR] yt-dlp extraction failed: {e}")
        return None, None, None

def download_video(video_url, save_path):
    """
    Download the video using yt-dlp (with ffmpeg as the downloader).
    """
    print("[DEBUG] Video download started.")
    command = [
        "yt-dlp", "-f", "best", "--downloader", "ffmpeg",
        "--hls-use-mpegts", "--no-part", "-o", save_path, video_url
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(save_path):
        print("[DEBUG] Video downloaded successfully.")
        return True
    else:
        print("[ERROR] Video download failed.")
        return False

def encode_video(input_path, output_path):
    """
    Encode the downloaded video for compatibility using ffmpeg.
    """
    print("[DEBUG] Encoding started.")
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-preset", "slow", "-crf", "23",
        "-b:a", "128k", "-c:a", "aac", "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(output_path):
        print("[DEBUG] Encoding finished.")
        return True
    else:
        print("[ERROR] Encoding failed.")
        return False

def generate_animated_thumbnail(video_path, thumbnail_path, position=None, duration="3", fps="10", scale="320:-1"):
    """
    Generate an animated WebP thumbnail from the video using FFmpeg.
    If 'position' is not provided, calculates the video's midpoint.
    """
    if position is None:
        video_duration = get_video_duration(video_path)
        if video_duration is None:
            print("[ERROR] Could not determine video duration; thumbnail generation aborted.")
            return False
        position = f"{video_duration / 2:.2f}"
    print(f"[DEBUG] Generating animated thumbnail starting at {position} seconds.")
    command = [
        "ffmpeg", "-y", "-i", video_path,
        "-ss", position, "-t", duration,
        "-vf", f"fps={fps},scale={scale}:flags=lanczos",
        "-loop", "0", thumbnail_path
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[DEBUG] Thumbnail generation output: {result.stderr.decode()}")
    if os.path.exists(thumbnail_path):
        print("[DEBUG] Thumbnail generation finished successfully.")
        return True
    else:
        print("[ERROR] Thumbnail generation failed.")
        return False

def download_image(url, save_path):
    """
    Download an image from the given URL and save it to the specified path.
    """
    try:
        print(f"[DEBUG] Downloading image from URL: {url}")
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print("[DEBUG] Image downloaded successfully.")
            return True
        else:
            print(f"[ERROR] Image download failed with status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Exception during image download: {e}")
        return False

def upload_video(api_key, library_id, file_path, title):
    """
    Upload the video file to Bunny.net and return a tuple: (video_id, preview_url).
    'preview_url' is taken from the 'previewAnimationUrl' field if available.
    """
    print("[DEBUG] Uploading video to Bunny.net started.")
    create_video_url = f"https://video.bunnycdn.com/library/{library_id}/videos"
    headers = {"AccessKey": api_key, "Content-Type": "application/json"}
    create_payload = {"title": title.strip()}
    response = requests.post(create_video_url, json=create_payload, headers=headers)
    video_response = response.json()
    print(f"[DEBUG] Bunny.net Video Creation Response: {video_response}")
    if response.status_code not in [200, 201]:
        print("[ERROR] Bunny.net video creation failed!")
        return None, None
    video_id = video_response.get("guid")
    preview_url = video_response.get("previewAnimationUrl")
    if not video_id:
        print("[ERROR] No video_id returned.")
        return None, None
    upload_url = f"https://video.bunnycdn.com/library/{library_id}/videos/{video_id}"
    with open(file_path, 'rb') as file:
        upload_headers = {"AccessKey": api_key, "Content-Type": "application/octet-stream"}
        upload_response = requests.put(upload_url, headers=upload_headers, data=file)
    if upload_response.status_code != 200:
        print(f"[ERROR] Bunny.net upload failed! Response: {upload_response.json()}")
        return None, None
    print("[DEBUG] Uploading video to Bunny.net finished.")
    return video_id, preview_url

def upload_thumbnail(local_thumbnail_path, title):
    """
    Upload the animated WebP thumbnail to WordPress via multipart/form-data.
    The alt text is set to the video title.
    """
    print("[DEBUG] Uploading thumbnail to WordPress started.")
    media_url = f"{WP_SITE}/media"
    try:
        with open(local_thumbnail_path, 'rb') as f:
            files = {'file': (os.path.basename(local_thumbnail_path), f, 'image/webp')}
            data = {'title': f"{title} Thumbnail", 'alt_text': title}
            response = requests.post(media_url, auth=auth, files=files, data=data)
        if response.status_code in [200, 201]:
            print(f"[DEBUG] Thumbnail uploaded: {response.json()}")
            print("[DEBUG] Uploading thumbnail to WordPress finished.")
            return response.json().get("id")
        else:
            print(f"[ERROR] Thumbnail upload failed: {response.json()}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception during thumbnail upload: {e}")
        return None

# === WordPress Post Operations ===
def get_post(post_id):
    url = f"{WP_SITE}/posts/{post_id}?context=edit"
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] Could not fetch source post: {response.json()}")
        return None

def create_wordpress_post(payload):
    print("[DEBUG] Creating WordPress post started.")
    url = f"{WP_SITE}/posts"
    response = requests.post(url, json=payload, auth=auth)
    if response.status_code in [200, 201]:
        post = response.json()
        print(f"[DEBUG] New post created: {post}")
        print("[DEBUG] Creating WordPress post finished.")
        return post
    else:
        print(f"[ERROR] Failed to create new post: {response.json()}")
        return None

def update_wordpress_post(post_id, payload):
    print(f"[DEBUG] Updating WordPress post {post_id} started.")
    url = f"{WP_SITE}/posts/{post_id}"
    response = requests.post(url, json=payload, auth=auth)
    if response.status_code in [200, 201]:
        print(f"[DEBUG] Post updated: {response.json()}")
        print(f"[DEBUG] Updating WordPress post {post_id} finished.")
        return response.json()
    else:
        print(f"[ERROR] Failed to update post: {response.json()}")
        return None

# === FastAPI Endpoint ===
@app.get("/process_video/")
def process_video(video_url: str = Query(...)):
    """
    Process the video from XHamster and create a new WordPress post.
    
    Workflow:
      1. Extract video info (URL, title, description).
      2. Download the video.
      3. Check if the downloaded video is compatible:
         - If compatible, skip encoding.
         - Otherwise, encode the video.
      4. Upload the chosen video file to Bunny.net.
      5. Build the iframe embed code.
      6. For compatible videos, if Bunny.net provides a previewAnimationUrl:
             Wait briefly and download that image as the thumbnail.
         Otherwise, generate an animated thumbnail from the video's midpoint.
      7. Create a new WordPress post (empty content, default category [38]).
      8. Update the post's meta with the iframe embed code and update featured media.
    """
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
        # Wait briefly to allow Bunny.net to process and generate the preview.
        time.sleep(2)
        if not download_image(preview_url, LOCAL_THUMBNAIL_PATH):
            print("[ERROR] Failed to download preview thumbnail from Bunny.net; falling back to local generation.")
            if not generate_animated_thumbnail(thumbnail_source, LOCAL_THUMBNAIL_PATH):
                return {"status": "failed", "message": "Thumbnail generation failed."}
    else:
        print("[DEBUG] Generating animated thumbnail from the video's midpoint.")
        if not generate_animated_thumbnail(thumbnail_source, LOCAL_THUMBNAIL_PATH):
            return {"status": "failed", "message": "Thumbnail generation failed."}
    
    # Step 7: Create a new WordPress post (empty content so that the iframe is stored only in meta).
    payload = {
        "title": video_title,
        "content": "",
        "excerpt": video_description,
        "status": "publish",
        "categories": [38],
        "meta": {"tie_embed_code": ""}
    }
    new_post = create_wordpress_post(payload)
    if not new_post:
        return {"status": "failed", "message": "Failed to create new post."}
    new_post_id = new_post.get("id")
    
    # Step 8: Update the new post's meta with the iframe embed code and update featured media.
    update_wordpress_post(new_post_id, {"meta": {"tie_embed_code": iframe_code}, "excerpt": video_description})
    media_id = upload_thumbnail(LOCAL_THUMBNAIL_PATH, video_title)
    if media_id:
        update_wordpress_post(new_post_id, {"featured_media": media_id})
    
    return {"status": "success", "video_id": video_id, "post_id": new_post_id}

import os
import tweepy
from dotenv import load_dotenv

# Load environment variables
load_dotenv("keys.env")

# Twitter API credentials from environment variables
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

# Authenticate with Twitter
auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
api = tweepy.API(auth)

def post_tweet(title, description, video_url, thumbnail_url):
    """
    Posts a tweet with a Twitter card that includes:
    - Title
    - Description (if available)
    - Thumbnail (animated WebP)
    - Redirect link to the post
    
    Parameters:
        title (str): Title of the video/post
        description (str): Video description
        video_url (str): URL of the video post
        thumbnail_url (str): URL of the animated thumbnail
    """
    
    # Create the tweet message
    tweet_text = f"{title}\n\n{description[:200]}...\n\nWatch here: {video_url}"
    
    # Upload media (thumbnail)
    media = api.media_upload(thumbnail_url)
    
    # Post tweet with media
    api.update_status(status=tweet_text, media_ids=[media.media_id])
    print("[INFO] Tweet posted successfully!")
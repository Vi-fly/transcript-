from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import re
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv()

def extract_video_id(url):
    """Extract video ID from YouTube URL."""
    # YouTube URL patterns
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\?\/]+)',
        r'youtube.com/watch\?.*v=([^&]+)',
        r'youtube.com/shorts/([^&\?\/]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL")

def get_youtube_api_client():
    """Initialize YouTube API client."""
    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
        return None
    return build('youtube', 'v3', developerKey=api_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_video_info_from_api(video_id):
    """Get video info using YouTube API."""
    youtube = get_youtube_api_client()
    if not youtube:
        return None

    try:
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        )
        response = request.execute()
        if response['items']:
            return response['items'][0]
        return None
    except Exception:
        return None

def get_video_info(url):
    """Get video title and other metadata using YouTube API or yt-dlp."""
    try:
        video_id = extract_video_id(url)
        
        # First try YouTube API
        api_info = get_video_info_from_api(video_id)
        if api_info:
            snippet = api_info['snippet']
            content_details = api_info['contentDetails']
            # Convert ISO 8601 duration to seconds
            duration_str = content_details['duration'].replace('PT', '').lower()
            duration = 0
            for part in re.findall(r'(\d+[hms])', duration_str):
                value = int(part[:-1])
                if 'h' in part:
                    duration += value * 3600
                elif 'm' in part:
                    duration += value * 60
                else:
                    duration += value

            return {
                'title': snippet['title'],
                'author': snippet['channelTitle'],
                'length': duration,
                'thumbnail_url': snippet['thumbnails']['high']['url']
            }
        
        # Fallback to yt-dlp if API fails
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'format': 'best',
            'nocheckcertificate': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            return {
                'title': info.get('title', 'Unknown Title'),
                'author': info.get('uploader', 'Unknown Author'),
                'length': info.get('duration', 0),
                'thumbnail_url': info.get('thumbnail', '')
            }
    except Exception as e:
        raise ValueError(f"Error fetching video info: {str(e)}")

def get_youtube_transcript(video_id):
    """Get transcript from YouTube using the transcript API."""
    try:
        # First try to get available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to get manual English transcript first
        try:
            transcript = transcript_list.find_manually_created_transcript(['en'])
        except:
            try:
                # Try auto-generated English transcript
                transcript = transcript_list.find_transcript(['en'])
            except:
                try:
                    # Try any manual transcript
                    transcript = transcript_list.find_manually_created_transcript()
                except:
                    try:
                        # Try any auto-generated transcript
                        transcript = transcript_list.find_generated_transcript(['en'])
                    except:
                        return None  # No transcript available

        # Get the transcript text
        transcript_data = transcript.fetch()
        
        # Combine all text parts with proper timing
        transcript_text = []
        for entry in transcript_data:
            # Add a period if the segment doesn't end with punctuation
            text = entry['text'].strip()
            if text and not text[-1] in '.!?':
                text += '.'
            transcript_text.append(text)
        
        return ' '.join(transcript_text)
        
    except Exception:
        return None  # Return None if any error occurs
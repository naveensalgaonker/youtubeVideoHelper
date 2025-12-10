"""
YouTube handler module for extracting video metadata and transcriptions.
Uses yt-dlp for metadata and youtube-transcript-api for captions.
"""

import logging
import re
import time
import random
from typing import Optional, Dict, Any, List
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, 
    NoTranscriptFound,
    VideoUnavailable
)
import os

logger = logging.getLogger(__name__)

# User agents to rotate for avoiding detection
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


class YouTubeHandler:
    """Handles YouTube video metadata extraction and transcription retrieval."""
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.
        
        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        
        Args:
            url: YouTube URL
        
        Returns:
            Video ID or None if invalid
        """
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        logger.warning(f"Could not extract video ID from URL: {url}")
        return None
    
    @staticmethod
    def get_video_metadata(url: str) -> Dict[str, Any]:
        """
        Extract video metadata using yt-dlp.
        
        Args:
            url: YouTube video URL
        
        Returns:
            Dictionary containing video metadata
        
        Raises:
            Exception: If video is unavailable or cannot be accessed
        """
        try:
            # Add delay to avoid rate limiting
            time.sleep(random.uniform(3, 7))
            
            # Random user agent
            user_agent = random.choice(USER_AGENTS)
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'user_agent': user_agent,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Extract upload date
                upload_date = None
                if info.get('upload_date'):
                    # Format: YYYYMMDD -> YYYY-MM-DD
                    date_str = info['upload_date']
                    upload_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                
                metadata = {
                    'video_id': info.get('id'),
                    'video_url': url,
                    'title': info.get('title'),
                    'duration_seconds': info.get('duration'),
                    'channel_name': info.get('uploader') or info.get('channel'),
                    'upload_date': upload_date,
                    'views': info.get('view_count'),
                    'description': info.get('description', '')[:500] if info.get('description') else None
                }
                
                logger.info(f"Extracted metadata for: {metadata['title']} ({metadata['video_id']})")
                return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata from {url}: {str(e)}")
            raise
    
    @staticmethod
    def get_available_transcripts(video_id: str) -> List[Dict[str, Any]]:
        """
        Get list of all available transcripts for a video.
        
        Args:
            video_id: YouTube video ID
        
        Returns:
            List of available transcripts with language codes and types
        """
        try:
            # Check for cookies file to bypass IP blocks
            cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            
            # Get transcript list using the list method
            if os.path.exists(cookies_path):
                import requests
                session = requests.Session()
                
                # Set random user agent
                session.headers.update({
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                })
                
                # Load cookies from file
                try:
                    from http.cookiejar import MozillaCookieJar
                    cookie_jar = MozillaCookieJar(cookies_path)
                    cookie_jar.load(ignore_discard=True, ignore_expires=True)
                    session.cookies = cookie_jar
                    api = YouTubeTranscriptApi(http_client=session)
                    transcript_list = api.list(video_id)
                except Exception as e:
                    logger.warning(f"Failed to load cookies, using default: {str(e)}")
                    api = YouTubeTranscriptApi()
                    transcript_list = api.list(video_id)
            else:
                api = YouTubeTranscriptApi()
                transcript_list = api.list(video_id)
            
            available = []
            
            # Manually created transcripts
            try:
                for transcript in transcript_list._manually_created_transcripts.values():
                    available.append({
                        'language': transcript.language_code,
                        'language_name': transcript.language,
                        'type': 'manual',
                        'is_translatable': transcript.is_translatable
                    })
            except:
                pass
            
            # Auto-generated transcripts
            try:
                for transcript in transcript_list._generated_transcripts.values():
                    available.append({
                        'language': transcript.language_code,
                        'language_name': transcript.language,
                        'type': 'generated',
                        'is_translatable': transcript.is_translatable
                    })
            except:
                pass
            
            logger.info(f"Found {len(available)} available transcripts for {video_id}")
            return available
            
        except Exception as e:
            logger.error(f"Failed to list transcripts for {video_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_transcription_by_language(video_id: str, language_code: str) -> Dict[str, Any]:
        """
        Get video transcription for a specific language.
        
        Args:
            video_id: YouTube video ID
            language_code: Language code (e.g., 'en', 'hi', 'es')
        
        Returns:
            Dictionary with transcription_text, language, and source
        
        Raises:
            Exception: If transcript is not available
        """
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(5, 10))
        
        try:
            # Check for cookies file to bypass IP blocks
            cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            
            if os.path.exists(cookies_path):
                import requests
                session = requests.Session()
                
                # Set random user agent
                session.headers.update({
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                })
                
                # Load cookies from file
                try:
                    from http.cookiejar import MozillaCookieJar
                    cookie_jar = MozillaCookieJar(cookies_path)
                    cookie_jar.load(ignore_discard=True, ignore_expires=True)
                    session.cookies = cookie_jar
                    api = YouTubeTranscriptApi(http_client=session)
                    logger.info("Successfully loaded cookies for transcript requests")
                except Exception as e:
                    logger.warning(f"Failed to load cookies, using default: {str(e)}")
                    api = YouTubeTranscriptApi()
            else:
                api = YouTubeTranscriptApi()
                logger.info("No cookies file found, using default API")
            
            # Get transcript in specified language
            transcript_data = api.fetch(video_id, languages=[language_code])
            text = YouTubeHandler._format_transcript(transcript_data.snippets)
            
            logger.info(f"Retrieved transcript for {video_id} in {language_code}")
            return {
                'transcription_text': text,
                'language': language_code,
                'source': 'available'
            }
            
        except Exception as e:
            logger.error(f"Failed to get transcription for {video_id} in {language_code}: {str(e)}")
            raise
    
    @staticmethod
    def get_transcription(video_id: str, preferred_languages: List[str] = None) -> Dict[str, Any]:
        """
        Get video transcription with fallback logic.
        
        Tries in order:
        1. Manual captions in preferred languages
        2. Auto-generated captions in preferred languages
        3. Any available captions
        
        Args:
            video_id: YouTube video ID
            preferred_languages: List of language codes (e.g., ['en', 'en-US'])
        
        Returns:
            Dictionary with transcription_text, language, and source
        
        Raises:
            Exception: If no transcriptions are available
        """
        if preferred_languages is None:
            preferred_languages = ['en', 'en-US', 'en-GB']
        
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(5, 10))
        
        try:
            # Check for cookies file to bypass IP blocks
            cookies_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
            
            if os.path.exists(cookies_path):
                logger.info(f"Using cookies from {cookies_path}")
                # Create custom session with cookies
                import requests
                session = requests.Session()
                
                # Set random user agent
                session.headers.update({
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                })
                
                # Load cookies from file
                try:
                    from http.cookiejar import MozillaCookieJar
                    cookie_jar = MozillaCookieJar(cookies_path)
                    cookie_jar.load(ignore_discard=True, ignore_expires=True)
                    session.cookies = cookie_jar
                    api = YouTubeTranscriptApi(http_client=session)
                    logger.info("Successfully loaded cookies for transcript requests")
                except Exception as e:
                    logger.warning(f"Failed to load cookies, using default: {str(e)}")
                    api = YouTubeTranscriptApi()
            else:
                api = YouTubeTranscriptApi()
                logger.info("No cookies file found, using default API")
            
            # Retry logic with exponential backoff
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Try to get transcript in preferred languages
                    for lang in preferred_languages:
                        try:
                            transcript_data = api.fetch(video_id, languages=[lang])
                            text = YouTubeHandler._format_transcript(transcript_data.snippets)
                            
                            logger.info(f"Found transcript for {video_id} in {lang}")
                            return {
                                'transcription_text': text,
                                'language': lang,
                                'source': 'available'
                            }
                        except NoTranscriptFound:
                            continue
                        except Exception as e:
                            logger.warning(f"Error getting transcript in {lang}: {str(e)}")
                            continue
                    
                    # If preferred languages didn't work, try to get any available transcript
                    transcript_data = api.fetch(video_id)
                    text = YouTubeHandler._format_transcript(transcript_data.snippets)
                    
                    logger.info(f"Found transcript for {video_id} (auto-detected language)")
                    return {
                        'transcription_text': text,
                        'language': 'auto',
                        'source': 'available'
                    }
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All retry attempts failed for {video_id}")
                        raise
            
        except TranscriptsDisabled:
            logger.error(f"Transcripts are disabled for video {video_id}")
            raise Exception(f"Transcripts are disabled for this video")
        
        except VideoUnavailable:
            logger.error(f"Video {video_id} is unavailable")
            raise Exception(f"Video is unavailable")
        
        except NoTranscriptFound:
            logger.error(f"No transcripts found for video {video_id}")
            raise Exception(f"No transcripts available for this video")
        
        except Exception as e:
            logger.error(f"Failed to get transcription for {video_id}: {str(e)}")
            raise
    
    @staticmethod
    def _format_transcript(transcript_data: List) -> str:
        """
        Format transcript data into readable text.
        
        Args:
            transcript_data: List of transcript snippets
        
        Returns:
            Formatted transcript text
        """
        # Join all text segments with spaces
        # Handle both dict format (old API) and object format (new API)
        text_parts = []
        for segment in transcript_data:
            if hasattr(segment, 'text'):
                # New API: FetchedTranscriptSnippet object
                text_parts.append(segment.text)
            elif isinstance(segment, dict) and 'text' in segment:
                # Old API: dict format
                text_parts.append(segment['text'])
        
        text = ' '.join(text_parts)
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate if URL is a valid YouTube URL.
        
        Args:
            url: URL to validate
        
        Returns:
            True if valid YouTube URL
        """
        video_id = YouTubeHandler.extract_video_id(url)
        return video_id is not None
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Format duration in seconds to human-readable format.
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            Formatted string (e.g., "1:23:45" or "12:34")
        """
        if seconds is None:
            return "Unknown"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"

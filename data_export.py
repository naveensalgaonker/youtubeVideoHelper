"""
Data export and retrieval module for querying and exporting processed video data.
Supports listing, searching, and exporting to CSV/JSON formats.
"""

import json
import csv
import os
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from database import Database
from youtube_handler import YouTubeHandler

# Load environment variables
load_dotenv()


def get_database() -> Database:
    """Get database instance."""
    db_path = os.getenv("DATABASE_PATH", "youtube_videos.db")
    return Database(db_path)


def export_all_transcriptions_txt(db: Database = None, output_file: str = None) -> str:
    """
    Export all transcriptions to a single text file with video names and metadata.
    
    Args:
        db: Database instance (optional, will create if not provided)
        output_file: Output filename (optional, will auto-generate if not provided)
    
    Returns:
        Path to the created file
    """
    if db is None:
        db = get_database()
    
    if output_file is None:
        output_file = f"transcriptions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # Get all videos with transcriptions
    videos = db.list_videos()
    videos_with_transcriptions = []
    
    for video in videos:
        video_data = db.get_video_by_db_id(video['id'])
        if video_data and video_data.get('transcription'):
            videos_with_transcriptions.append(video_data)
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("YOUTUBE VIDEO TRANSCRIPTIONS EXPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Videos: {len(videos_with_transcriptions)}\n")
        f.write("="*80 + "\n\n")
        
        for i, video in enumerate(videos_with_transcriptions, 1):
            f.write("\n" + "="*80 + "\n")
            f.write(f"VIDEO #{i}\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Title: {video.get('title', 'Untitled')}\n")
            f.write(f"URL: {video.get('url', 'N/A')}\n")
            f.write(f"Channel: {video.get('channel', 'Unknown')}\n")
            
            duration = video.get('duration_seconds')
            if duration:
                f.write(f"Duration: {YouTubeHandler.format_duration(duration)}\n")
            
            if video.get('upload_date'):
                f.write(f"Upload Date: {video.get('upload_date')}\n")
            
            if video.get('category'):
                f.write(f"Category: {video.get('category')}\n")
            
            f.write("\n" + "-"*80 + "\n")
            f.write("TRANSCRIPTION:\n")
            f.write("-"*80 + "\n\n")
            
            f.write(video.get('transcription', 'No transcription available'))
            f.write("\n\n")
            
            if video.get('summary'):
                f.write("-"*80 + "\n")
                f.write("SUMMARY:\n")
                f.write("-"*80 + "\n\n")
                f.write(video.get('summary'))
                f.write("\n\n")
    
    print(f"\n✓ Exported {len(videos_with_transcriptions)} transcription(s) to: {output_file}\n")
    return output_file


def list_videos(category: Optional[str] = None, limit: Optional[int] = None):

    """
    List all processed videos.
    
    Args:
        category: Filter by category (optional)
        limit: Limit number of results (optional)
    """
    db = get_database()
    
    if category:
        videos = db.list_videos_by_category(category)
        print(f"\n{'='*80}")
        print(f"Videos in category: {category}")
        print(f"{'='*80}\n")
    else:
        videos = db.list_all_videos(limit=limit)
        print(f"\n{'='*80}")
        print(f"All Processed Videos" + (f" (showing {limit})" if limit else ""))
        print(f"{'='*80}\n")
    
    if not videos:
        print("No videos found.\n")
        return
    
    for i, video in enumerate(videos, 1):
        duration = YouTubeHandler.format_duration(video.get('duration_seconds'))
        category_str = video.get('category', 'Uncategorized')
        status = video.get('status', 'unknown')
        
        print(f"{i}. {video['title']}")
        print(f"   ID: {video['video_id']}")
        print(f"   Channel: {video.get('channel_name', 'Unknown')}")
        print(f"   Duration: {duration}")
        print(f"   Category: {category_str}")
        print(f"   Status: {status}")
        
        if video.get('summary_text'):
            summary = video['summary_text']
            # Truncate long summaries
            if len(summary) > 150:
                summary = summary[:150] + "..."
            print(f"   Summary: {summary}")
        
        print()


def show_video(video_id: str):
    """
    Show detailed information for a specific video.
    
    Args:
        video_id: YouTube video ID
    """
    db = get_database()
    video = db.get_complete_video_data(video_id)
    
    if not video:
        print(f"\nVideo not found: {video_id}\n")
        return
    
    print(f"\n{'='*80}")
    print(f"Video Details")
    print(f"{'='*80}\n")
    
    print(f"Title: {video['title']}")
    print(f"Video ID: {video['video_id']}")
    print(f"URL: {video['video_url']}")
    print(f"Channel: {video.get('channel_name', 'Unknown')}")
    print(f"Duration: {YouTubeHandler.format_duration(video.get('duration_seconds'))}")
    print(f"Upload Date: {video.get('upload_date', 'Unknown')}")
    print(f"Status: {video.get('status', 'unknown')}")
    
    if video.get('category'):
        print(f"\nCategory: {video['category']}")
    
    if video.get('summary_text'):
        print(f"\nSummary:")
        print(f"{video['summary_text']}")
    
    if video.get('transcription_text'):
        print(f"\nTranscription Preview:")
        transcription = video['transcription_text']
        preview = transcription[:500] + ("..." if len(transcription) > 500 else "")
        print(f"{preview}")
        print(f"\nTranscription Length: {len(transcription)} characters")
        print(f"Language: {video.get('language', 'Unknown')}")
        print(f"Source: {video.get('transcription_source', 'Unknown')}")
    
    if video.get('ai_model'):
        print(f"\nAI Model: {video['ai_model']}")
    
    print(f"\nProcessed: {video.get('created_at', 'Unknown')}")
    print()


def search_videos(search_term: str):
    """
    Search for videos by transcription content.
    
    Args:
        search_term: Term to search for
    """
    db = get_database()
    results = db.search_transcriptions(search_term)
    
    print(f"\n{'='*80}")
    print(f"Search Results for: '{search_term}'")
    print(f"{'='*80}\n")
    
    if not results:
        print("No videos found matching your search.\n")
        return
    
    print(f"Found {len(results)} video(s)\n")
    
    for i, video in enumerate(results, 1):
        print(f"{i}. {video['title']}")
        print(f"   ID: {video['video_id']}")
        print(f"   Channel: {video.get('channel_name', 'Unknown')}")
        print(f"   Category: {video.get('category', 'Uncategorized')}")
        
        # Show context around search term
        transcription = video.get('transcription_text', '')
        if transcription:
            # Find the term in transcription
            lower_transcription = transcription.lower()
            lower_term = search_term.lower()
            
            index = lower_transcription.find(lower_term)
            if index != -1:
                # Extract context (100 chars before and after)
                start = max(0, index - 100)
                end = min(len(transcription), index + len(search_term) + 100)
                context = transcription[start:end]
                
                if start > 0:
                    context = "..." + context
                if end < len(transcription):
                    context = context + "..."
                
                print(f"   Context: {context}")
        
        print()


def export_data(format: str, output_path: str, category: Optional[str] = None):
    """
    Export video data to CSV or JSON.
    
    Args:
        format: 'csv' or 'json'
        output_path: Output file path
        category: Filter by category (optional)
    """
    db = get_database()
    
    if category:
        videos = db.list_videos_by_category(category)
    else:
        videos = db.list_all_videos()
    
    if not videos:
        print("No videos to export.\n")
        return
    
    if format == 'csv':
        _export_csv(videos, output_path)
    elif format == 'json':
        _export_json(videos, output_path)
    
    print(f"\n✓ Exported {len(videos)} video(s) to: {output_path}\n")


def _export_csv(videos: list, output_path: str):
    """Export videos to CSV format."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'video_id', 'title', 'channel_name', 'duration_seconds', 
            'category', 'summary', 'status', 'created_at'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for video in videos:
            writer.writerow({
                'video_id': video.get('video_id', ''),
                'title': video.get('title', ''),
                'channel_name': video.get('channel_name', ''),
                'duration_seconds': video.get('duration_seconds', ''),
                'category': video.get('category', ''),
                'summary': video.get('summary_text', ''),
                'status': video.get('status', ''),
                'created_at': video.get('created_at', '')
            })


def _export_json(videos: list, output_path: str):
    """Export videos to JSON format."""
    export_data = []
    
    for video in videos:
        export_data.append({
            'video_id': video.get('video_id'),
            'title': video.get('title'),
            'channel_name': video.get('channel_name'),
            'duration_seconds': video.get('duration_seconds'),
            'category': video.get('category'),
            'summary': video.get('summary_text'),
            'status': video.get('status'),
            'created_at': video.get('created_at')
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)


def show_stats():
    """Display database statistics."""
    db = get_database()
    stats = db.get_statistics()
    categories = db.get_all_categories()
    
    print(f"\n{'='*80}")
    print(f"Database Statistics")
    print(f"{'='*80}\n")
    
    print(f"Total Videos: {stats['total_videos']}")
    print(f"Completed: {stats['completed_videos']}")
    print(f"Failed: {stats['failed_videos']}")
    print(f"Pending: {stats['total_videos'] - stats['completed_videos'] - stats['failed_videos']}")
    print(f"\nTotal Categories: {stats['total_categories']}")
    
    if categories:
        print(f"\nCategories:")
        for category in categories:
            # Count videos in each category
            videos = db.list_videos_by_category(category)
            print(f"  - {category}: {len(videos)} video(s)")
    
    print()

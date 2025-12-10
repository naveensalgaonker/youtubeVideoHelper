"""
Main orchestration module for YouTube video processing.
Handles CLI interface, batch processing, and coordination between modules.
"""

import argparse
import logging
import sys
import os
import time
from typing import List
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

from database import Database
from youtube_handler import YouTubeHandler
from ai_handler import AIHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('youtube_summarizer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class VideoProcessor:
    """Main processor for handling YouTube video batch operations."""
    
    def __init__(self, skip_ai: bool = False, user_id: int = None):
        """Initialize processor with database and handlers."""
        # Load environment variables
        load_dotenv()
        
        # Initialize components
        db_path = os.getenv("DATABASE_PATH", "youtube_videos.db")
        self.db = Database(db_path)
        self.youtube_handler = YouTubeHandler()
        self.skip_ai = skip_ai
        self.user_id = user_id  # Store user_id for video ownership
        self.force_reprocess = False  # Can be set to force reprocessing of existing videos
        self.force_reprocess = False
        
        # Initialize AI handler only if needed
        if not skip_ai:
            ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
            self.ai_handler = AIHandler(provider=ai_provider)
            logger.info(f"Initialized VideoProcessor with {ai_provider} AI provider")
        else:
            self.ai_handler = None
            logger.info("Initialized VideoProcessor in transcription-only mode (AI disabled)")
    
    def process_video(self, url: str) -> bool:
        """
        Process a single video: extract metadata, transcription, and generate summary.
        
        Args:
            url: YouTube video URL
        
        Returns:
            True if successful, False otherwise
        """
        video_db_id = None
        
        try:
            # Step 1: Validate URL
            if not self.youtube_handler.validate_url(url):
                logger.error(f"Invalid YouTube URL: {url}")
                return False
            
            video_id = self.youtube_handler.extract_video_id(url)
            
            # Check if already exists in database
            existing = self.db.get_video_by_video_id(video_id)
            if existing and not self.force_reprocess:
                if existing['status'] == 'completed':
                    logger.info(f"Video already completed: {existing['title']}")
                    print(f"⏭️  Skipping (already completed): {existing['title']}")
                    return True
                elif existing['status'] == 'processing':
                    logger.info(f"Video currently processing: {existing['title']}")
                    print(f"⏭️  Skipping (currently processing): {existing['title']}")
                    return True
                elif existing['status'] == 'failed':
                    logger.info(f"Retrying previously failed video: {existing['title']}")
                    print(f"🔄 Retrying failed video: {existing['title']}")
            elif existing and self.force_reprocess:
                logger.info(f"Force reprocessing: {existing['title']}")
                print(f"🔄 Force reprocessing: {existing['title']}")
            
            # Step 2: Extract metadata
            logger.info(f"Extracting metadata for: {url}")
            metadata = self.youtube_handler.get_video_metadata(url)
            
            # Save to database
            if existing:
                video_db_id = existing['id']
                self.db.update_video_status(video_db_id, 'processing')
            else:
                # Pass user_id as a parameter, not in metadata
                video_db_id = self.db.insert_video(metadata, user_id=self.user_id)
                self.db.update_video_status(video_db_id, 'processing')
            
            print(f"📹 Processing: {metadata['title']}")
            print(f"   Duration: {self.youtube_handler.format_duration(metadata['duration_seconds'])}")
            print(f"   Channel: {metadata['channel_name']}")
            
            # Step 3: Get transcription
            logger.info(f"Retrieving transcription for: {video_id}")
            print("   Getting transcription...")
            
            transcription_data = self.youtube_handler.get_transcription(video_id)
            self.db.insert_transcription(
                video_db_id,
                transcription_data['transcription_text'],
                transcription_data['language'],
                transcription_data['source']
            )
            
            print(f"   ✓ Transcription retrieved ({transcription_data['source']})")
            
            # Step 4: Generate summary and category (only if AI is enabled)
            if not self.skip_ai:
                logger.info(f"Generating summary for: {video_id}")
                print("   Generating AI summary...")
                
                summary, category = self.ai_handler.generate_summary_and_category(
                    transcription_data['transcription_text'],
                    metadata['title']
                )
                
                self.db.insert_summary(
                    video_db_id,
                    summary,
                    category,
                    self.ai_handler.provider
                )
                
                print(f"   ✓ Summary generated")
                print(f"   Category: {category}")
            else:
                logger.info(f"Skipping AI summary (transcription-only mode)")
                print("   ✓ Skipping AI summary (transcription-only mode)")
            
            # Mark as completed
            self.db.update_video_status(video_db_id, 'completed')
            
            logger.info(f"Successfully processed video: {metadata['title']}")
            return True

            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process {url}: {error_msg}")
            print(f"   ✗ Error: {error_msg}\n")
            
            # Mark as failed if we have a DB ID
            if video_db_id:
                self.db.update_video_status(video_db_id, 'failed')
            
            return False
    
    def process_urls(self, urls: List[str]) -> dict:
        """
        Process multiple URLs in batch.
        
        Args:
            urls: List of YouTube URLs
        
        Returns:
            Dictionary with processing statistics
        """
        print(f"\n{'='*60}")
        print(f"Processing {len(urls)} video(s)")
        print(f"{'='*60}\n")
        
        successful = 0
        failed = 0
        skipped = 0
        # Process each URL with progress bar
        for url in tqdm(urls, desc="Overall Progress", unit="video"):
            result = self.process_video(url)
            if result:
                successful += 1
            else:
                failed += 1
            
            # Add delay between videos to avoid rate limiting
            if url != urls[-1]:  # Don't delay after last video
                time.sleep(3)
                failed += 1
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Processing Complete!")
        print(f"{'='*60}")
        print(f"✓ Successful: {successful}")
        print(f"✗ Failed: {failed}")
        print(f"Total: {len(urls)}\n")
        
        return {
            'total': len(urls),
            'successful': successful,
            'failed': failed
        }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube Video Summarizer - Extract, transcribe, and summarize YouTube videos",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process YouTube video(s)')
    process_parser.add_argument('urls', nargs='*', help='YouTube URL(s) to process')
    process_parser.add_argument('--file', '-f', help='File containing URLs (one per line)')
    process_parser.add_argument('--no-ai', action='store_true', help='Skip AI summarization, only extract transcriptions')
    process_parser.add_argument('--force', action='store_true', help='Force reprocess videos that are already completed')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List processed videos')
    list_parser.add_argument('--category', '-c', help='Filter by category')
    list_parser.add_argument('--limit', '-l', type=int, help='Limit number of results')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show details for a specific video')
    show_parser.add_argument('video_id', help='YouTube video ID')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search transcriptions')
    search_parser.add_argument('term', help='Search term')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export data')
    export_parser.add_argument('--format', choices=['csv', 'json'], default='csv', help='Export format')
    export_parser.add_argument('--output', '-o', required=True, help='Output file path')
    export_parser.add_argument('--category', '-c', help='Filter by category')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Handle commands
    if args.command == 'process':
        # Collect URLs
        urls = []
        
        if args.urls:
            urls.extend(args.urls)
        
        if args.file:
            if not os.path.exists(args.file):
                print(f"Error: File not found: {args.file}")
                sys.exit(1)
            
            with open(args.file, 'r') as f:
                file_urls = [line.strip() for line in f if line.strip()]
                urls.extend(file_urls)
        
        if not urls:
            print("Error: No URLs provided. Use URLs as arguments or --file option.")
            process_parser.print_help()
            sys.exit(1)
        
        # Remove duplicate URLs while preserving order
        seen = set()
        unique_urls = []
        duplicates_count = 0
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
            else:
                duplicates_count += 1
        
        if duplicates_count > 0:
            print(f"\n⚠️  Removed {duplicates_count} duplicate URL(s) from input\n")
        
        # Process videos
        processor = VideoProcessor(skip_ai=args.no_ai)
        processor.force_reprocess = args.force
        if args.force:
            print("⚠️  Force mode enabled - will reprocess existing videos\n")
        processor.process_urls(unique_urls)
    
    elif args.command == 'list':
        from data_export import list_videos
        list_videos(category=args.category, limit=args.limit)
    
    elif args.command == 'show':
        from data_export import show_video
        show_video(args.video_id)
    
    elif args.command == 'search':
        from data_export import search_videos
        search_videos(args.term)
    
    elif args.command == 'export':
        from data_export import export_data
        export_data(args.format, args.output, category=args.category)
    
    elif args.command == 'stats':
        from data_export import show_stats
        show_stats()


if __name__ == "__main__":
    main()

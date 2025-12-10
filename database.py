"""
Database module for storing YouTube video metadata, transcriptions, and summaries.
Uses SQLite for persistent storage with transactional safety.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)


class Database:
    """Handles all database operations for YouTube video data."""
    
    def __init__(self, db_path: str = "youtube_videos.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Videos table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT UNIQUE NOT NULL,
                    video_url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    duration_seconds INTEGER,
                    channel_name TEXT,
                    upload_date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Transcriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    transcription_text TEXT NOT NULL,
                    language TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
            """)
            
            # Summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id INTEGER NOT NULL,
                    summary_text TEXT NOT NULL,
                    category TEXT,
                    ai_model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
            """)
            
            # Create indices for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_id ON videos(video_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON videos(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON summaries(category)")
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_video(self, video_data: Dict[str, Any]) -> int:
        """
        Insert a new video record.
        
        Args:
            video_data: Dictionary with keys: video_id, video_url, title, 
                       duration_seconds, channel_name, upload_date
        
        Returns:
            Database ID of inserted video
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO videos (video_id, video_url, title, duration_seconds, 
                                   channel_name, upload_date, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (
                video_data['video_id'],
                video_data['video_url'],
                video_data['title'],
                video_data.get('duration_seconds'),
                video_data.get('channel_name'),
                video_data.get('upload_date')
            ))
            conn.commit()
            video_db_id = cursor.lastrowid
            logger.info(f"Inserted video: {video_data['title']} (ID: {video_db_id})")
            return video_db_id
    
    def insert_transcription(self, video_db_id: int, transcription: str, 
                            language: str = None, source: str = None) -> int:
        """
        Insert or update transcription for a video (removes duplicates by video_id).
        
        Args:
            video_db_id: Database ID of the video
            transcription: Full transcription text
            language: Language code (e.g., 'en')
            source: Source of transcription (e.g., 'auto-generated', 'manual')
        
        Returns:
            Database ID of inserted/updated transcription
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete existing transcription for this video to avoid duplicates
            cursor.execute("DELETE FROM transcriptions WHERE video_id = ?", (video_db_id,))
            # Insert new transcription
            cursor.execute("""
                INSERT INTO transcriptions (video_id, transcription_text, language, source)
                VALUES (?, ?, ?, ?)
            """, (video_db_id, transcription, language, source))
            conn.commit()
            trans_id = cursor.lastrowid
            logger.info(f"Inserted transcription for video ID {video_db_id}")
            return trans_id
    
    def insert_summary(self, video_db_id: int, summary: str, 
                       category: str = None, ai_model: str = None) -> int:
        """
        Insert or update summary for a video (removes duplicates by video_id).
        
        Args:
            video_db_id: Database ID of the video
            summary: Summary text
            category: Video category
            ai_model: AI model used for generation
        
        Returns:
            Database ID of inserted/updated summary
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete existing summary for this video to avoid duplicates
            cursor.execute("DELETE FROM summaries WHERE video_id = ?", (video_db_id,))
            # Insert new summary
            cursor.execute("""
                INSERT INTO summaries (video_id, summary_text, category, ai_model)
                VALUES (?, ?, ?, ?)
            """, (video_db_id, summary, category, ai_model))
            conn.commit()
            summary_id = cursor.lastrowid
            logger.info(f"Inserted summary for video ID {video_db_id} - Category: {category}")
            return summary_id
    
    def save_summary(self, video_id: int, summary: str, category: str = None, 
                     key_points: List[str] = None, ai_model: str = None) -> int:
        """
        Save or update summary for a video (alias for insert_summary with key_points support).
        
        Args:
            video_id: Database ID of the video
            summary: Summary text
            category: Video category
            key_points: List of key points (will be joined into summary)
            ai_model: AI model used for generation
        
        Returns:
            Database ID of inserted/updated summary
        """
        # If key_points provided, append to summary
        if key_points:
            summary_with_points = summary + "\n\nKey Points:\n" + "\n".join([f"- {point}" for point in key_points])
        else:
            summary_with_points = summary
        
        return self.insert_summary(video_id, summary_with_points, category, ai_model)
    
    def update_video_status(self, video_db_id: int, status: str):
        """Update video processing status (pending, processing, completed, failed)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (status, video_db_id))
            conn.commit()
            logger.info(f"Updated video ID {video_db_id} status to: {status}")
    
    def get_video_by_video_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video data by YouTube video ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_video_by_db_id(self, db_id: int) -> Optional[Dict[str, Any]]:
        """Get video data by database ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE id = ?", (db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_transcription(self, video_db_id: int) -> Optional[Dict[str, Any]]:
        """Get transcription for a video."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM transcriptions WHERE video_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (video_db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_summary(self, video_db_id: int) -> Optional[Dict[str, Any]]:
        """Get summary for a video."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM summaries WHERE video_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (video_db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_complete_video_data(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get complete video data including transcription and summary by YouTube video ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    v.*,
                    t.transcription_text as transcription,
                    t.language,
                    t.source as transcription_source,
                    s.summary_text as summary,
                    s.category,
                    s.ai_model
                FROM videos v
                LEFT JOIN transcriptions t ON v.id = t.video_id
                LEFT JOIN summaries s ON v.id = s.video_id
                WHERE v.video_id = ?
                ORDER BY t.created_at DESC, s.created_at DESC
                LIMIT 1
            """, (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_video_by_db_id(self, db_id: int) -> Optional[Dict[str, Any]]:
        """Get complete video data including transcription and summary by database ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    v.id,
                    v.video_id,
                    v.video_url as url,
                    v.title,
                    v.channel_name as channel,
                    v.duration_seconds,
                    v.upload_date,
                    v.status,
                    v.created_at,
                    t.transcription_text as transcription,
                    t.language,
                    t.source as transcription_source,
                    s.summary_text as summary,
                    s.category,
                    s.ai_model
                FROM videos v
                LEFT JOIN transcriptions t ON v.id = t.video_id
                LEFT JOIN summaries s ON v.id = s.video_id
                WHERE v.id = ?
                ORDER BY t.created_at DESC, s.created_at DESC
                LIMIT 1
            """, (db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def list_videos(self, limit: int = None) -> List[Dict[str, Any]]:
        """List all videos with basic info (alias for list_all_videos)."""
        return self.list_all_videos(limit=limit)
    
    def list_all_videos(self, limit: int = None) -> List[Dict[str, Any]]:
        """List all videos with their summaries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    v.id,
                    v.video_id,
                    v.title,
                    v.channel_name as channel,
                    v.duration_seconds,
                    v.status,
                    s.category,
                    s.summary_text,
                    v.created_at,
                    CASE WHEN t.id IS NOT NULL THEN 1 ELSE 0 END as has_transcription,
                    CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END as has_summary
                FROM videos v
                LEFT JOIN summaries s ON v.id = s.video_id
                LEFT JOIN transcriptions t ON v.id = t.video_id
                ORDER BY v.created_at DESC
            """
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def list_videos_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List videos filtered by category."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    v.id,
                    v.video_id,
                    v.title,
                    v.channel_name as channel,
                    v.duration_seconds,
                    s.category,
                    s.summary_text,
                    v.created_at
                FROM videos v
                JOIN summaries s ON v.id = s.video_id
                WHERE s.category = ?
                ORDER BY v.created_at DESC
            """, (category,))
            return [dict(row) for row in cursor.fetchall()]
    
    def search_transcriptions(self, search_term: str) -> List[Dict[str, Any]]:
        """Search for videos by transcription content."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    v.id,
                    v.video_id,
                    v.title,
                    v.channel_name as channel,
                    v.duration_seconds,
                    s.category,
                    t.transcription_text as transcription
                FROM videos v
                JOIN transcriptions t ON v.id = t.video_id
                LEFT JOIN summaries s ON v.id = s.video_id
                WHERE t.transcription_text LIKE ?
                ORDER BY v.created_at DESC
            """, (f"%{search_term}%",))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_categories(self) -> List[str]:
        """Get list of all unique categories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT category 
                FROM summaries 
                WHERE category IS NOT NULL
                ORDER BY category
            """)
            return [row[0] for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE status = 'completed'")
            completed_videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM videos WHERE status = 'failed'")
            failed_videos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT category) FROM summaries WHERE category IS NOT NULL")
            total_categories = cursor.fetchone()[0]
            
            return {
                'total_videos': total_videos,
                'completed_videos': completed_videos,
                'failed_videos': failed_videos,
                'total_categories': total_categories
            }

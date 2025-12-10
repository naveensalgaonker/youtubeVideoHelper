"""
Database module for storing YouTube video metadata, transcriptions, and summaries.
Supports both SQLite (local) and PostgreSQL (production) with user authentication.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import os
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

# Database connection type detection
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class Database:
    """Handles all database operations for YouTube video data with multi-user support."""
    
    def __init__(self, db_url: str = None):
        """Initialize database connection and create tables if needed.
        
        Args:
            db_url: Database URL. If starts with 'postgresql://', uses PostgreSQL.
                   Otherwise uses SQLite with the path as filename.
        """
        if db_url is None:
            db_url = os.getenv('DATABASE_URL', 'youtube_videos.db')
        
        self.db_url = db_url
        self.is_postgres = db_url.startswith('postgresql://') or db_url.startswith('postgres://')
        
        if self.is_postgres and not POSTGRES_AVAILABLE:
            raise RuntimeError("PostgreSQL URL provided but psycopg2 not installed. Run: pip install psycopg2-binary")
        
        self.db_path = db_url if not self.is_postgres else None
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id {} PRIMARY KEY {},
                    username {} UNIQUE NOT NULL,
                    password_hash {} NOT NULL,
                    is_superuser BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """.format(
                'SERIAL' if self.is_postgres else 'INTEGER',
                '' if self.is_postgres else 'AUTOINCREMENT',
                'VARCHAR(80)' if self.is_postgres else 'TEXT',
                'VARCHAR(255)' if self.is_postgres else 'TEXT'
            ))
            
            # User settings table for API keys
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    id {} PRIMARY KEY {},
                    user_id INTEGER NOT NULL,
                    openai_api_key {},
                    gemini_api_key {},
                    ai_provider {} DEFAULT 'openai',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """.format(
                'SERIAL' if self.is_postgres else 'INTEGER',
                '' if self.is_postgres else 'AUTOINCREMENT',
                'TEXT' if self.is_postgres else 'TEXT',
                'TEXT' if self.is_postgres else 'TEXT',
                'VARCHAR(20)' if self.is_postgres else 'TEXT'
            ))
            
            # Videos table (now with user_id)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id {} PRIMARY KEY {},
                    user_id INTEGER NOT NULL,
                    video_id {} UNIQUE NOT NULL,
                    video_url {} UNIQUE NOT NULL,
                    title {} NOT NULL,
                    duration_seconds INTEGER,
                    channel_name {},
                    upload_date {},
                    status {} DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """.format(
                'SERIAL' if self.is_postgres else 'INTEGER',
                '' if self.is_postgres else 'AUTOINCREMENT',
                'VARCHAR(50)' if self.is_postgres else 'TEXT',
                'TEXT' if self.is_postgres else 'TEXT',
                'TEXT' if self.is_postgres else 'TEXT',
                'TEXT' if self.is_postgres else 'TEXT',
                'VARCHAR(50)' if self.is_postgres else 'TEXT',
                'VARCHAR(20)' if self.is_postgres else 'TEXT'
            ))
            
            # Transcriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id {} PRIMARY KEY {},
                    video_id INTEGER NOT NULL,
                    transcription_text TEXT NOT NULL,
                    language {},
                    source {},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
            """.format(
                'SERIAL' if self.is_postgres else 'INTEGER',
                '' if self.is_postgres else 'AUTOINCREMENT',
                'VARCHAR(10)' if self.is_postgres else 'TEXT',
                'VARCHAR(50)' if self.is_postgres else 'TEXT'
            ))
            
            # Summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id {} PRIMARY KEY {},
                    video_id INTEGER NOT NULL,
                    summary_text TEXT NOT NULL,
                    category {},
                    ai_model {},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
                )
            """.format(
                'SERIAL' if self.is_postgres else 'INTEGER',
                '' if self.is_postgres else 'AUTOINCREMENT',
                'VARCHAR(100)' if self.is_postgres else 'TEXT',
                'VARCHAR(50)' if self.is_postgres else 'TEXT'
            ))
            
            # Create indices for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON videos(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_id ON videos(video_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON videos(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON summaries(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_settings ON user_settings(user_id)")
            
            conn.commit()
            
            # Create default superuser if not exists
            self._create_default_superuser(conn)
            
            logger.info(f"Database initialized at {self.db_url}")
    
    def _create_default_superuser(self, conn):
        """Create default superuser account if it doesn't exist."""
        cursor = conn.cursor()
        
        # Check if superuser exists
        if self.is_postgres:
            cursor.execute("SELECT id FROM users WHERE username = %s", ('admin',))
        else:
            cursor.execute("SELECT id FROM users WHERE username = ?", ('admin',))
        
        if cursor.fetchone() is None:
            # Create superuser with default credentials
            # Use pbkdf2:sha256 method for compatibility with older Python versions
            password_hash = generate_password_hash('admin123', method='pbkdf2:sha256')
            if self.is_postgres:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, is_superuser)
                    VALUES (%s, %s, %s)
                """, ('admin', password_hash, True))
            else:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, is_superuser)
                    VALUES (?, ?, ?)
                """, ('admin', password_hash, True))
            
            conn.commit()
            logger.warning("Created default superuser - Username: admin, Password: admin123 - CHANGE THIS IMMEDIATELY!")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        if self.is_postgres:
            # Supabase and other cloud PostgreSQL providers require SSL
            # Parse connection string and add sslmode if not present
            db_url = self.db_url
            if 'sslmode=' not in db_url:
                separator = '&' if '?' in db_url else '?'
                db_url = f"{db_url}{separator}sslmode=require"
            
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            conn.set_session(autocommit=False)
            try:
                yield conn
            finally:
                conn.close()
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            try:
                yield conn
            finally:
                conn.close()
    
    def _param_placeholder(self):
        """Return the correct parameter placeholder for current database."""
        return '%s' if self.is_postgres else '?'
    
    def _dict_from_row(self, row):
        """Convert database row to dictionary."""
        if row is None:
            return None
        
        if self.is_postgres:
            # PostgreSQL with RealDictCursor returns RealDictRow (dict-like)
            # Convert datetime objects to strings for consistency
            result = dict(row)
            for key, value in result.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
            return result
        else:
            # SQLite returns Row objects
            return dict(row)
    
    # ============= USER MANAGEMENT METHODS =============
    
    def create_user(self, username: str, password: str, is_superuser: bool = False) -> int:
        """Create a new user account.
        
        Args:
            username: Unique username
            password: Plain text password (will be hashed)
            is_superuser: Whether user has superuser privileges
            
        Returns:
            User ID of created user
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Use pbkdf2:sha256 method for compatibility with older Python versions
            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
            
            ph = self._param_placeholder()
            cursor.execute(f"""
                INSERT INTO users (username, password_hash, is_superuser)
                VALUES ({ph}, {ph}, {ph})
            """, (username, password_hash, is_superuser))
            
            if self.is_postgres:
                cursor.execute("SELECT currval(pg_get_serial_sequence('users', 'id'))")
                user_id = cursor.fetchone()[0]
            else:
                user_id = cursor.lastrowid
            
            conn.commit()
            logger.info(f"Created user: {username} (ID: {user_id})")
            return user_id
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ph = self._param_placeholder()
            cursor.execute(f"SELECT * FROM users WHERE username = {ph}", (username,))
            row = cursor.fetchone()
            return self._dict_from_row(row)
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ph = self._param_placeholder()
            cursor.execute(f"SELECT * FROM users WHERE id = {ph}", (user_id,))
            row = cursor.fetchone()
            return self._dict_from_row(row)
    
    def verify_password(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify user credentials and return user data if valid."""
        user = self.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            return user
        return None
    
    def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user settings including API keys."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ph = self._param_placeholder()
            cursor.execute(f"SELECT * FROM user_settings WHERE user_id = {ph}", (user_id,))
            row = cursor.fetchone()
            return self._dict_from_row(row)
    
    def update_user_settings(self, user_id: int, openai_key: str = None, 
                            gemini_key: str = None, ai_provider: str = None):
        """Update or create user settings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ph = self._param_placeholder()
            
            # Check if settings exist
            cursor.execute(f"SELECT id FROM user_settings WHERE user_id = {ph}", (user_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing
                updates = []
                values = []
                if openai_key is not None:
                    updates.append(f"openai_api_key = {ph}")
                    values.append(openai_key)
                if gemini_key is not None:
                    updates.append(f"gemini_api_key = {ph}")
                    values.append(gemini_key)
                if ai_provider is not None:
                    updates.append(f"ai_provider = {ph}")
                    values.append(ai_provider)
                
                if updates:
                    updates.append(f"updated_at = CURRENT_TIMESTAMP")
                    values.append(user_id)
                    cursor.execute(f"""
                        UPDATE user_settings 
                        SET {', '.join(updates)}
                        WHERE user_id = {ph}
                    """, values)
            else:
                # Insert new
                cursor.execute(f"""
                    INSERT INTO user_settings (user_id, openai_api_key, gemini_api_key, ai_provider)
                    VALUES ({ph}, {ph}, {ph}, {ph})
                """, (user_id, openai_key or '', gemini_key or '', ai_provider or 'openai'))
            
            conn.commit()
            logger.info(f"Updated settings for user ID {user_id}")
    
    # ============= VIDEO MANAGEMENT METHODS (NOW WITH USER FILTERING) =============
    
    def insert_video(self, video_data: Dict[str, Any], user_id: int = None) -> int:
        """
        Insert a new video record for a specific user.
        
        Args:
            video_data: Dictionary with keys: video_id, video_url, title, 
                       duration_seconds, channel_name, upload_date
            user_id: ID of the user who owns this video (required for multi-user mode)
        
        Returns:
            Database ID of inserted video
        """
        if user_id is None:
            raise ValueError("user_id is required for inserting videos")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ph = self._param_placeholder()
            cursor.execute(f"""
                INSERT INTO videos (user_id, video_id, video_url, title, duration_seconds, 
                                   channel_name, upload_date, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'pending')
            """, (
                user_id,
                video_data['video_id'],
                video_data['video_url'],
                video_data['title'],
                video_data.get('duration_seconds'),
                video_data.get('channel_name'),
                video_data.get('upload_date')
            ))
            conn.commit()
            
            if self.is_postgres:
                cursor.execute("SELECT currval(pg_get_serial_sequence('videos', 'id'))")
                video_db_id = cursor.fetchone()[0]
            else:
                video_db_id = cursor.lastrowid
            
            logger.info(f"Inserted video: {video_data['title']} (ID: {video_db_id}) for user {user_id}")
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
    
    def list_videos(self, user_id: int = None, limit: int = None) -> List[Dict[str, Any]]:
        """List videos with optional user filtering.
        
        Args:
            user_id: If provided, only return videos for this user
            limit: Maximum number of videos to return
        """
        return self.list_all_videos(user_id=user_id, limit=limit)
    
    def list_all_videos(self, user_id: int = None, limit: int = None) -> List[Dict[str, Any]]:
        """List all videos with their summaries, optionally filtered by user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ph = self._param_placeholder()
            
            query = """
                SELECT 
                    v.id,
                    v.user_id,
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
            """
            
            params = []
            if user_id is not None:
                query += f" WHERE v.user_id = {ph}"
                params.append(user_id)
            
            query += " ORDER BY v.created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def list_videos_by_category(self, category: str, user_id: int = None) -> List[Dict[str, Any]]:
        """List videos filtered by category and optionally by user."""
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

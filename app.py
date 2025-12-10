#!/usr/bin/env python3
"""
Web UI for YouTube Video Summarizer with Multi-User Authentication
Provides a browser interface to view stored videos, transcriptions, and export data
"""

from flask import Flask, render_template, jsonify, send_file, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from database import Database
from data_export import export_all_transcriptions_txt
from youtube_handler import YouTubeHandler
import os
from datetime import datetime
import logging
import threading
import queue
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Security configuration
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    logger.warning("⚠️  SECRET_KEY not set! Using insecure default for development only.")
    SECRET_KEY = 'dev-secret-key-change-in-production-INSECURE'

app.config['SECRET_KEY'] = SECRET_KEY
app.config['WTF_CSRF_ENABLED'] = True

# Session cookie security settings
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'  # HTTPS only in production
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Initialize database
DATABASE_URL = os.getenv('DATABASE_URL', 'youtube_videos.db')
db = Database(DATABASE_URL)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'error'

# Processing queue for background jobs
processing_queue = queue.Queue()
processing_status = {}  # Track status of processing jobs
processing_lock = threading.Lock()


# ============= USER MODEL FOR FLASK-LOGIN =============

class User(UserMixin):
    """User model for Flask-Login"""
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.is_superuser = user_data.get('is_superuser', False)
        self.created_at = user_data.get('created_at', '')
    
    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    user_data = db.get_user_by_id(int(user_id))
    if user_data:
        return User(user_data)
    return None


# ============= WTFORMS FOR AUTHENTICATION =============

class LoginForm(FlaskForm):
    """Login form"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    """Registration form"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    
    def validate_username(self, username):
        user = db.get_user_by_username(username.data)
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')


class SettingsForm(FlaskForm):
    """Settings form for API keys"""
    openai_api_key = StringField('OpenAI API Key', validators=[Length(max=200)])
    gemini_api_key = StringField('Gemini API Key', validators=[Length(max=200)])
    ai_provider = SelectField('AI Provider', choices=[('openai', 'OpenAI'), ('gemini', 'Google Gemini')], validators=[DataRequired()])


# Add custom Jinja2 filter for formatting duration
@app.template_filter('format_duration')
def format_duration_filter(seconds):
    """Format duration in seconds to HH:MM:SS or MM:SS"""
    if seconds is None:
        return 'Unknown'
    return YouTubeHandler.format_duration(seconds)


# ============= AUTHENTICATION ROUTES =============

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user_data = db.verify_password(form.username.data, form.password.data)
        if user_data:
            user = User(user_data)
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            user_id = db.create_user(form.username.data, form.password.data)
            flash(f'Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            flash(f'Error creating account: {str(e)}', 'error')
    
    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """Logout current user"""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page"""
    form = SettingsForm()
    
    if form.validate_on_submit():
        try:
            db.update_user_settings(
                user_id=current_user.id,
                openai_key=form.openai_api_key.data or None,
                gemini_key=form.gemini_api_key.data or None,
                ai_provider=form.ai_provider.data
            )
            flash('Settings saved successfully!', 'success')
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            flash(f'Error saving settings: {str(e)}', 'error')
    
    # Load current settings
    user_settings = db.get_user_settings(current_user.id)
    if user_settings:
        form.openai_api_key.data = user_settings.get('openai_api_key', '')
        form.gemini_api_key.data = user_settings.get('gemini_api_key', '')
        form.ai_provider.data = user_settings.get('ai_provider', 'openai')
    
    return render_template('settings.html', form=form)


# ============= VIDEO ROUTES (NOW WITH USER FILTERING) =============

@app.route('/')
@login_required
def index():
    """Home page - list videos for current user"""
    try:
        # Superuser sees all videos, regular users see only their own
        if current_user.is_superuser:
            videos = db.list_videos()
        else:
            videos = db.list_videos(user_id=current_user.id)
        
        stats = {
            'total': len(videos),
            'completed': len([v for v in videos if v['status'] == 'completed']),
            'processing': len([v for v in videos if v['status'] == 'processing']),
            'failed': len([v for v in videos if v['status'] == 'failed'])
        }
        return render_template('index.html', videos=videos, stats=stats)
    except Exception as e:
        logger.error(f"Error loading videos: {e}")
        return render_template('error.html', error=str(e)), 500


@app.route('/video/<int:video_id>')
@login_required
def video_detail(video_id):
    """View detailed information for a specific video"""
    try:
        video_data = db.get_video_by_db_id(video_id)
        if not video_data:
            return render_template('error.html', error=f"Video ID {video_id} not found"), 404
        
        # Check if user has access to this video
        if not current_user.is_superuser and video_data.get('user_id') != current_user.id:
            return render_template('error.html', error="Access denied"), 403
        
        return render_template('video_detail.html', video=video_data)
    except Exception as e:
        logger.error(f"Error loading video {video_id}: {e}")
        return render_template('error.html', error=str(e)), 500


@app.route('/search')
@login_required
def search():
    """Search transcriptions"""
    query = request.args.get('q', '')
    if not query:
        return redirect(url_for('index'))
    
    try:
        results = db.search_transcriptions(query)
        # Filter results by user access
        if not current_user.is_superuser:
            results = [r for r in results if r.get('user_id') == current_user.id]
        return render_template('search_results.html', query=query, results=results)
    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        return render_template('error.html', error=str(e)), 500


@app.route('/category/<category>')
@login_required
def category_view(category):
    """View videos by category"""
    try:
        videos = db.list_videos_by_category(category)
        # Filter by user access
        if not current_user.is_superuser:
            videos = [v for v in videos if v.get('user_id') == current_user.id]
        return render_template('category.html', category=category, videos=videos)
    except Exception as e:
        logger.error(f"Error loading category {category}: {e}")
        return render_template('error.html', error=str(e)), 500


@app.route('/export')
@login_required
def export_page():
    """Export page with options"""
    return render_template('export.html')


@app.route('/add')
@login_required
def add_page():
    """Page for adding new videos"""
    return render_template('add_videos.html')


@app.route('/add/process', methods=['POST'])
@login_required
def add_videos():
    """Process new video URLs"""
    try:
        urls_text = request.form.get('urls', '').strip()
        skip_ai = request.form.get('skip_ai') == 'on'
        
        if not urls_text:
            return jsonify({'success': False, 'error': 'No URLs provided'}), 400
        
        # Parse URLs (one per line)
        urls = [line.strip() for line in urls_text.split('\n') if line.strip()]
        
        if not urls:
            return jsonify({'success': False, 'error': 'No valid URLs found'}), 400
        
        # Remove duplicates
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        # Start processing in background
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with processing_lock:
            processing_status[job_id] = {
                'status': 'queued',
                'total': len(unique_urls),
                'completed': 0,
                'failed': 0,
                'current': None,
                'skip_ai': skip_ai,
                'user_id': current_user.id  # Add user_id to track ownership
            }
        
        # Add to queue
        processing_queue.put({
            'job_id': job_id,
            'urls': unique_urls,
            'skip_ai': skip_ai,
            'user_id': current_user.id  # Pass user_id to background worker
        })
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_urls': len(unique_urls),
            'duplicates_removed': len(urls) - len(unique_urls)
        })
        
    except Exception as e:
        logger.error(f"Error adding videos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/health')
def health_check():
    """Health check endpoint to keep service alive during processing"""
    return jsonify({'status': 'ok'}), 200


@app.route('/status/<job_id>')
@login_required
def job_status(job_id):
    """Get status of a processing job"""
    with processing_lock:
        if job_id not in processing_status:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        job_data = processing_status[job_id]
        # Check if user has access to this job
        if not current_user.is_superuser and job_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        return jsonify({'success': True, 'status': job_data})


@app.route('/retry/transcript/<int:video_id>', methods=['POST'])
@login_required
def retry_transcript(video_id):
    """Retry transcript extraction for a video"""
    try:
        video_data = db.get_video_by_db_id(video_id)
        if not video_data:
            return jsonify({'success': False, 'error': 'Video not found'}), 404
        
        # Check if user has access to this video
        if not current_user.is_superuser and video_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Extract video URL
        video_url = video_data['url']
        video_youtube_id = YouTubeHandler.extract_video_id(video_url)
        
        # Check if multiple transcripts are available
        available_transcripts = YouTubeHandler.get_available_transcripts(video_youtube_id)
        
        if len(available_transcripts) > 1:
            # Multiple transcripts - show selection UI
            return jsonify({
                'success': True,
                'multiple_transcripts': True,
                'transcripts': available_transcripts,
                'video_id': video_id
            })
        elif len(available_transcripts) == 1:
            # Single transcript - save it automatically
            db.update_video_status(video_id, 'processing')
            
            transcript = available_transcripts[0]
            language_code = transcript['language']
            
            # Get transcription for that language
            transcription_data = YouTubeHandler.get_transcription_by_language(video_youtube_id, language_code)
            
            # Save transcription
            db.insert_transcription(
                video_db_id=video_id,
                transcription=transcription_data['transcription_text'],
                language=language_code,
                source=transcript['type']
            )
            
            # Update status to completed
            db.update_video_status(video_id, 'completed')
            
            logger.info(f"Successfully saved transcript in {language_code} for video ID {video_id}")
            return jsonify({'success': True, 'message': f'Transcript extracted successfully in {transcript["language_name"]}'})
        
        # No transcripts found - try default behavior
        # Update status to processing
        db.update_video_status(video_id, 'processing')
        
        # Get transcription
        transcription_data = YouTubeHandler.get_transcription(video_youtube_id)
        
        # Save transcription
        db.insert_transcription(
            video_db_id=video_id,
            transcription=transcription_data['transcription_text'],
            language=transcription_data['language'],
            source=transcription_data['source']
        )
        
        # Update status to completed (without summary)
        db.update_video_status(video_id, 'completed')
        
        logger.info(f"Successfully retried transcript for video ID {video_id}")
        return jsonify({'success': True, 'message': 'Transcript extracted successfully'})
        
    except Exception as e:
        logger.error(f"Error retrying transcript for video {video_id}: {e}")
        db.update_video_status(video_id, 'failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get/transcript/<int:video_id>/<language_code>', methods=['POST'])
@login_required
def get_transcript_by_language(video_id, language_code):
    """Get transcript for a specific language"""
    try:
        video_data = db.get_video_by_db_id(video_id)
        if not video_data:
            return jsonify({'success': False, 'error': 'Video not found'}), 404
        
        # Check if user has access to this video
        if not current_user.is_superuser and video_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Extract video URL
        video_url = video_data['url']
        video_youtube_id = YouTubeHandler.extract_video_id(video_url)
        
        # Update status to processing
        db.update_video_status(video_id, 'processing')
        
        # Get transcription for specific language
        transcription_data = YouTubeHandler.get_transcription_by_language(video_youtube_id, language_code)
        
        # Save transcription
        db.insert_transcription(
            video_db_id=video_id,
            transcription=transcription_data['transcription_text'],
            language=language_code,
            source=transcription_data['source']
        )
        
        # Update status to completed
        db.update_video_status(video_id, 'completed')
        
        logger.info(f"Successfully saved transcript in {language_code} for video ID {video_id}")
        return jsonify({'success': True, 'message': f'Transcript in {language_code} extracted successfully'})
        
    except Exception as e:
        logger.error(f"Error getting transcript in {language_code} for video {video_id}: {e}")
        db.update_video_status(video_id, 'failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/retry/summary/<int:video_id>', methods=['POST'])
@login_required
def retry_summary(video_id):
    """Retry summary generation for a video"""
    try:
        video_data = db.get_video_by_db_id(video_id)
        if not video_data:
            return jsonify({'success': False, 'error': 'Video not found'}), 404
        
        # Check if user has access to this video
        if not current_user.is_superuser and video_data.get('user_id') != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
        
        # Check if transcription exists
        if not video_data.get('transcription'):
            return jsonify({'success': False, 'error': 'No transcription available. Please retry transcript first.'}), 400
        
        # Initialize AI handler
        from ai_handler import AIHandler
        ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
        ai_handler = AIHandler(provider=ai_provider)
        
        # Update status to processing
        db.update_video_status(video_id, 'processing')
        
        # Generate summary
        summary_data = ai_handler.generate_summary(
            title=video_data['title'],
            transcription=video_data['transcription'],
            channel_name=video_data.get('channel', 'Unknown')
        )
        
        # Save summary
        db.save_summary(
            video_id=video_id,
            summary=summary_data['summary'],
            category=summary_data.get('category'),
            key_points=summary_data.get('key_points', [])
        )
        
        # Update status to completed
        db.update_video_status(video_id, 'completed')
        
        logger.info(f"Successfully retried summary for video ID {video_id}")
        return jsonify({'success': True, 'message': 'Summary generated successfully'})
        
    except Exception as e:
        logger.error(f"Error retrying summary for video {video_id}: {e}")
        db.update_video_status(video_id, 'failed')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/bulk/transcript', methods=['POST'])
@login_required
def bulk_generate_transcript():
    """Generate transcripts for multiple videos"""
    try:
        data = request.get_json()
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return jsonify({'success': False, 'error': 'No videos selected'}), 400
        
        # Verify user has access to all selected videos
        if not current_user.is_superuser:
            for video_id in video_ids:
                video_data = db.get_video_by_db_id(video_id)
                if video_data and video_data.get('user_id') != current_user.id:
                    return jsonify({'success': False, 'error': 'Access denied to one or more videos'}), 403
        
        # Queue jobs for background processing
        handler = YouTubeHandler()
        success_count = 0
        
        for video_db_id in video_ids:
            try:
                video_data = db.get_video_by_db_id(video_db_id)
                if not video_data:
                    continue
                
                # Update status to processing
                db.update_video_status(video_db_id, 'processing')
                
                # Get available transcripts
                transcripts = handler.get_available_transcripts(video_data['video_id'])
                
                if not transcripts:
                    # Try to get default English transcript
                    try:
                        transcription = handler.get_transcription(video_data['video_id'])
                        if transcription:
                            db.insert_transcription(video_db_id, transcription, 'en', 'default')
                            db.update_video_status(video_db_id, 'completed')
                            success_count += 1
                    except:
                        db.update_video_status(video_db_id, 'failed')
                elif len(transcripts) == 1:
                    # Auto-save single transcript
                    transcript = transcripts[0]
                    transcription = handler.get_transcription_by_language(
                        video_data['video_id'],
                        transcript['language']
                    )
                    if transcription:
                        db.insert_transcription(video_db_id, transcription, transcript['language'], transcript['type'])
                        db.update_video_status(video_db_id, 'completed')
                        success_count += 1
                # For multiple transcripts, skip and leave as processing (user must manually select)
                
            except Exception as e:
                logger.error(f"Error processing transcript for video {video_db_id}: {e}")
                db.update_video_status(video_db_id, 'failed')
        
        return jsonify({
            'success': True,
            'message': f'Started transcript generation for {len(video_ids)} video(s)',
            'processed': success_count
        })
        
    except Exception as e:
        logger.error(f"Error in bulk transcript generation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/bulk/summary', methods=['POST'])
@login_required
def bulk_generate_summary():
    """Generate summaries for multiple videos"""
    try:
        data = request.get_json()
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return jsonify({'success': False, 'error': 'No videos selected'}), 400
        
        # Verify user has access to all selected videos
        if not current_user.is_superuser:
            for video_id in video_ids:
                video_data = db.get_video_by_db_id(video_id)
                if video_data and video_data.get('user_id') != current_user.id:
                    return jsonify({'success': False, 'error': 'Access denied to one or more videos'}), 403
        
        from ai_handler import AIHandler
        ai_provider = os.getenv("AI_PROVIDER", "openai").lower()
        ai_handler = AIHandler(provider=ai_provider)
        
        success_count = 0
        
        for video_id in video_ids:
            try:
                video_data = db.get_video_by_db_id(video_id)
                if not video_data or not video_data.get('transcription'):
                    continue
                
                # Update status to processing
                db.update_video_status(video_id, 'processing')
                
                # Generate summary
                summary_data = ai_handler.generate_summary(
                    title=video_data['title'],
                    transcription=video_data['transcription'],
                    channel_name=video_data.get('channel', 'Unknown')
                )
                
                # Save summary
                db.save_summary(
                    video_id=video_id,
                    summary=summary_data['summary'],
                    category=summary_data.get('category'),
                    key_points=summary_data.get('key_points', [])
                )
                
                # Update status to completed
                db.update_video_status(video_id, 'completed')
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error generating summary for video {video_id}: {e}")
                db.update_video_status(video_id, 'failed')
        
        return jsonify({
            'success': True,
            'message': f'Started summary generation for {len(video_ids)} video(s)',
            'processed': success_count
        })
        
    except Exception as e:
        logger.error(f"Error in bulk summary generation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/bulk/delete', methods=['POST'])
@login_required
def bulk_delete_videos():
    """Delete multiple videos"""
    try:
        data = request.get_json()
        video_ids = data.get('video_ids', [])
        
        if not video_ids:
            return jsonify({'success': False, 'error': 'No videos selected'}), 400
        
        # Verify user has access to all selected videos
        if not current_user.is_superuser:
            for video_id in video_ids:
                video_data = db.get_video_by_db_id(video_id)
                if video_data and video_data.get('user_id') != current_user.id:
                    return jsonify({'success': False, 'error': 'Access denied to one or more videos'}), 403
        
        deleted_count = 0
        
        # Use database's context manager for connection
        with db._get_connection() as conn:
            cursor = conn.cursor()
            for video_id in video_ids:
                try:
                    # Delete video and all associated data (cascades to transcriptions and summaries)
                    cursor.execute('DELETE FROM videos WHERE id = ?', (video_id,))
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting video {video_id}: {e}")
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} video(s)',
            'deleted': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/export/txt')
@login_required
def export_txt():
    """Export all transcriptions to a single text file"""
    try:
        output_file = f"transcriptions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        # Note: export_all_transcriptions_txt should be updated to filter by user_id
        export_all_transcriptions_txt(db, output_file)
        return send_file(output_file, as_attachment=True, download_name=output_file)
    except Exception as e:
        logger.error(f"Error exporting to TXT: {e}")
        return render_template('error.html', error=str(e)), 500


@app.route('/api/videos')
@login_required
def api_videos():
    """API endpoint - list all videos"""
    try:
        # Filter videos by user
        if current_user.is_superuser:
            videos = db.list_videos()
        else:
            videos = db.list_videos(user_id=current_user.id)
        return jsonify(videos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/video/<int:video_id>')
@login_required
def api_video_detail(video_id):
    """API endpoint - get video details"""
    try:
        video_data = db.get_complete_video_data(video_id)
        if not video_data:
            return jsonify({'error': 'Video not found'}), 404
        
        # Check if user has access to this video
        if not current_user.is_superuser and video_data.get('user_id') != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(video_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """API endpoint - get database statistics"""
    try:
        videos = db.list_videos()
        stats = {
            'total_videos': len(videos),
            'completed': len([v for v in videos if v['status'] == 'completed']),
            'processing': len([v for v in videos if v['status'] == 'processing']),
            'failed': len([v for v in videos if v['status'] == 'failed']),
            'has_transcription': len([v for v in videos if v.get('has_transcription')]),
            'has_summary': len([v for v in videos if v.get('has_summary')])
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def process_video_worker():
    """Background worker to process videos from the queue"""
    from main import VideoProcessor
    
    while True:
        try:
            # Get job from queue (blocking)
            job = processing_queue.get()
            job_id = job['job_id']
            urls = job['urls']
            skip_ai = job['skip_ai']
            user_id = job.get('user_id')  # Get user_id from job
            
            # Update status
            with processing_lock:
                processing_status[job_id]['status'] = 'processing'
            
            # Initialize processor with user_id
            processor = VideoProcessor(skip_ai=skip_ai, user_id=user_id)
            
            # Process each URL
            for i, url in enumerate(urls):
                with processing_lock:
                    processing_status[job_id]['current'] = url
                
                try:
                    success = processor.process_video(url)
                    with processing_lock:
                        if success:
                            processing_status[job_id]['completed'] += 1
                        else:
                            processing_status[job_id]['failed'] += 1
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    with processing_lock:
                        processing_status[job_id]['failed'] += 1
            
            # Mark job as complete
            with processing_lock:
                processing_status[job_id]['status'] = 'completed'
                processing_status[job_id]['current'] = None
            
            processing_queue.task_done()
            
        except Exception as e:
            logger.error(f"Worker error: {e}")
            time.sleep(1)


if __name__ == '__main__':
    print("\n" + "="*60)
    print("YouTube Video Summarizer - Multi-User Web UI")
    print("="*60)
    print(f"Database: {DATABASE_URL}")
    print(f"Server starting at: http://localhost:5001")
    print(f"Default Login: admin / admin123")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Start background worker thread
    worker_thread = threading.Thread(target=process_video_worker, daemon=True)
    worker_thread.start()
    logger.info("Background processing worker started")
    
    app.run(debug=True, host='0.0.0.0', port=5001)

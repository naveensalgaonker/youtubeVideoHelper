# YouTube Video Summarizer - Deployment Guide

## 🚀 Multi-User Web Application with Authentication

This application now supports multiple users with individual accounts and API keys. Each user can only see their own videos, and there's a superuser account that can view all data.

## 📋 Features

✅ **User Authentication** - Username/password login and registration  
✅ **Multi-User Support** - Each user has their own video library  
✅ **Superuser Account** - Admin access to all user data  
✅ **Personal API Keys** - Users configure their own OpenAI/Gemini keys  
✅ **Settings Page** - Manage API keys and logout  
✅ **PostgreSQL Support** - Production-ready database (also works with SQLite locally)  
✅ **Cloud Deployment** - Ready for Render.com free tier  

## 🔐 Default Credentials

**Superuser Account** (created automatically):
- Username: `admin`
- Password: `admin123`

⚠️ **IMPORTANT**: Change this password immediately after first login via the Settings page!

## 🏃 Local Development

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Locally (SQLite)

```bash
python app.py
```

The app will start at `http://localhost:5001`

- Database: `youtube_videos.db` (SQLite, created automatically)
- Default superuser will be created on first run

### 3. Test with PostgreSQL Locally (Optional)

```bash
# Install PostgreSQL
brew install postgresql  # macOS
# or apt-get install postgresql  # Linux

# Create database
createdb youtube_summarizer

# Set environment variable
export DATABASE_URL="postgresql://localhost/youtube_summarizer"

# Run app
python app.py
```

## ☁️ Deploy to Render.com (Free Tier)

### Prerequisites
- GitHub account
- Render.com account (sign up at render.com)
- Push this code to a GitHub repository

### Deployment Steps

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Add multi-user authentication"
   git push origin main
   ```

2. **Connect to Render**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Select the repository with this code

3. **Render will automatically**:
   - Read `render.yaml` configuration
   - Create PostgreSQL database
   - Deploy web service
   - Set up environment variables

4. **Add Optional Environment Variables** (in Render Dashboard):
   - `OPENAI_API_KEY` - Optional default OpenAI key
   - `GEMINI_API_KEY` - Optional default Gemini key
   - Note: Users can add their own keys in Settings

5. **Access Your App**:
   - Render will provide a URL like: `https://youtube-summarizer-xxxx.onrender.com`
   - First deployment takes 5-10 minutes
   - App goes to sleep after 15 minutes of inactivity (free tier)
   - Cold start takes ~30 seconds

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `youtube_videos.db` | PostgreSQL connection string or SQLite file path |
| `SECRET_KEY` | Yes (prod) | auto-generated | Flask secret key for sessions |
| `OPENAI_API_KEY` | No | - | Default OpenAI API key |
| `GEMINI_API_KEY` | No | - | Default Gemini API key |

### Database Migration

The app automatically:
- Creates tables on first run
- Supports both SQLite (local) and PostgreSQL (production)
- Creates default superuser account

To migrate existing SQLite data to PostgreSQL:
```bash
# Export from SQLite
sqlite3 youtube_videos.db .dump > backup.sql

# Import to PostgreSQL (edit backup.sql to fix syntax differences)
psql $DATABASE_URL < backup.sql
```

## 👥 User Management

### Creating Users
1. Go to `/register`
2. Choose username and password
3. Login at `/login`

### Superuser Access
- Login as `admin` / `admin123`
- Can see all users' videos
- Change password in Settings

### User Settings
Each user can configure:
- OpenAI API Key (personal)
- Gemini API Key (personal)
- Preferred AI Provider
- Logout

## 🎯 Usage Flow

1. **Register/Login** → Create account or use existing credentials
2. **Add Videos** → Go to "Add Videos" page, paste YouTube URLs
3. **Configure API Keys** → Go to Settings, add your API keys
4. **Process Videos** → Videos will be transcribed automatically
5. **Generate Summaries** → Click retry summary if you have API keys configured
6. **Export Data** → Export transcriptions as needed

## 🔒 Security Features

- ✅ Passwords hashed with Werkzeug (PBKDF2 SHA256)
- ✅ CSRF protection on all forms (Flask-WTF)
- ✅ Session management (Flask-Login)
- ✅ User isolation (row-level filtering)
- ✅ Secure secret key (environment variable)

## 🐛 Troubleshooting

### "No module named 'psycopg2'"
```bash
pip install psycopg2-binary
```

### Database connection errors
- Check `DATABASE_URL` format
- PostgreSQL: `postgresql://user:pass@host:port/dbname`
- SQLite: just a filename like `youtube_videos.db`

### Render deployment issues
- Check build logs in Render dashboard
- Verify `requirements.txt` is committed
- Ensure `render.yaml` is in repository root

### Cold starts on Render
- Free tier sleeps after 15 min inactivity
- First request takes ~30 seconds
- Consider upgrading to paid tier for always-on

## 📊 Database Schema

### Tables
- `users` - User accounts with hashed passwords
- `user_settings` - Per-user API keys and preferences
- `videos` - Video metadata (with `user_id` foreign key)
- `transcriptions` - Video transcripts
- `summaries` - AI-generated summaries

### Indexes
- `idx_user_id` on videos(user_id)
- `idx_video_id` on videos(video_id)
- `idx_status` on videos(status)
- `idx_category` on summaries(category)

## 🆘 Support

For issues:
1. Check application logs
2. Verify environment variables
3. Check database connection
4. Review Render build/deploy logs

## 📝 License

MIT License - see LICENSE file for details

# Supabase Setup Guide

## Why Supabase?

✅ **Free forever tier** (500MB database, unlimited API requests)  
✅ **PostgreSQL** (same as production Render.com)  
✅ **Auto-backups** and point-in-time recovery  
✅ **Dashboard UI** to view/edit data  
✅ **No credit card required**  

---

## Step 1: Create Supabase Account

1. Go to **https://supabase.com**
2. Click **"Start your project"**
3. Sign up with **GitHub** (easiest option)

---

## Step 2: Create New Project

1. Click **"New Project"** in dashboard
2. Fill in details:
   - **Name**: `youtube-summarizer` (or any name you like)
   - **Database Password**: Create a strong password
     - **⚠️ SAVE THIS PASSWORD!** You'll need it later
     - Example: `MyStr0ngP@ssw0rd123!`
   - **Region**: Choose closest to you (e.g., `us-west-1`)
   - **Pricing Plan**: **Free** (should be selected by default)
3. Click **"Create new project"**
4. **Wait 2-3 minutes** for provisioning

---

## Step 3: Get Database Connection String

1. Once project is ready, click **"Project Settings"** (gear icon, bottom left)
2. Click **"Database"** in left sidebar
3. Scroll down to **"Connection string"** section
4. Select **"URI"** tab (not Session mode)
5. You'll see a connection string like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.abcdefghijk.supabase.co:5432/postgres
   ```
6. **Copy this string**
7. **Replace `[YOUR-PASSWORD]`** with the password you created in Step 2

---

## Step 4: Test Connection Locally (Optional)

Before deploying, test the Supabase connection locally:

### 4.1 Update your `.env` file:

```bash
# Create .env file if it doesn't exist
cp .env.example .env
```

### 4.2 Edit `.env` and add your Supabase URL:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:YourPassword@db.xxx.supabase.co:5432/postgres

# Flask Configuration
SECRET_KEY=your-local-secret-key-for-testing
FLASK_ENV=development

# Optional: AI Keys (or users can add their own)
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
AI_PROVIDER=openai
```

### 4.3 Run the app:

```bash
# Activate virtual environment
source venv/bin/activate

# Run app
python app.py
```

### 4.4 Check the logs:

You should see:
```
INFO:database:Database initialized at postgresql://postgres:***@db.xxx.supabase.co:5432/postgres
INFO:database:Created default superuser: admin
```

### 4.5 Test login:

1. Open http://localhost:5001
2. Login with `admin` / `admin123`
3. Try adding a video

If it works locally, you're ready to deploy!

---

## Step 5: View Your Database in Supabase

### Option A: Supabase Dashboard (Easy)

1. Go to your Supabase project
2. Click **"Table Editor"** (left sidebar)
3. You'll see your tables:
   - `users` - User accounts
   - `user_settings` - API keys
   - `videos` - Video metadata
   - `transcriptions` - Transcripts
   - `summaries` - AI summaries

### Option B: SQL Editor

1. Click **"SQL Editor"** (left sidebar)
2. Click **"New query"**
3. Run SQL queries:

```sql
-- View all users
SELECT id, username, is_superuser, created_at FROM users;

-- View videos count per user
SELECT u.username, COUNT(v.id) as video_count 
FROM users u 
LEFT JOIN videos v ON u.id = v.user_id 
GROUP BY u.username;

-- View all videos
SELECT id, title, channel_name, status, user_id, created_at 
FROM videos 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## Step 6: Deploy to Render with Supabase

Now deploy your app to Render using Supabase as the database:

### 6.1 Commit your code changes:

```bash
git add .
git commit -m "Add Supabase PostgreSQL support"
git push origin main
```

### 6.2 Create Web Service on Render:

1. Go to **https://render.com**
2. Click **"New +"** → **"Web Service"**
3. Connect your **GitHub repository** (`youtubeVideoHelper`)
4. Configure:
   - **Name**: `youtube-summarizer`
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Instance Type**: **Free**

### 6.3 Add Environment Variables:

Click **"Advanced"** → **"Add Environment Variable"**:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | (paste your Supabase connection string) |
| `SECRET_KEY` | (run `python -c "import secrets; print(secrets.token_hex(32))"` and paste) |
| `FLASK_ENV` | `production` |
| `OPENAI_API_KEY` | (optional - users can add their own) |
| `GEMINI_API_KEY` | (optional - users can add their own) |

### 6.4 Deploy:

1. Click **"Create Web Service"**
2. Wait 5-10 minutes for build
3. Your app will be live at: `https://youtube-summarizer-xxxx.onrender.com`

---

## Step 7: First Login & Setup

1. Open your Render URL
2. Login with default credentials:
   - Username: `admin`
   - Password: `admin123`
3. **Immediately go to Settings** and:
   - Change your password
   - Add your API keys (OpenAI or Gemini)
4. Test by adding a YouTube video!

---

## Database Management

### Backup Database

**Via Supabase Dashboard:**
1. Project Settings → Database
2. Scroll to "Database Backups"
3. Free tier: Daily backups for 7 days

**Via Command Line:**
```bash
# Get connection string from Supabase
pg_dump "postgresql://postgres:password@db.xxx.supabase.co:5432/postgres" > backup.sql
```

### Monitor Usage

1. Go to Supabase Dashboard
2. Click **"Reports"** (left sidebar)
3. View:
   - Database size
   - API requests
   - Active connections

**Free Tier Limits:**
- 500 MB database storage
- Unlimited API requests
- 2 GB bandwidth per month
- 2 GB file storage

---

## Troubleshooting

### Issue: "SSL connection required"

**Solution:** Already handled! The code automatically adds `sslmode=require` to Supabase connections.

### Issue: "Connection refused"

**Check:**
1. Database password is correct in connection string
2. No spaces or typos in `DATABASE_URL`
3. Supabase project is active (not paused)

### Issue: "Too many connections"

**Solution:** Free tier has connection limits. Your app uses connection pooling, but if needed:
- Reduce `--workers 2` to `--workers 1` in Render start command

### Issue: Database is empty after deploy

**This is normal!** The database auto-initializes on first run:
1. Tables are created automatically
2. Default admin user is created
3. Check Render logs for: `INFO:database:Created default superuser: admin`

---

## Cost & Limits

### Supabase Free Tier:
- ✅ **500 MB database** (enough for ~10,000 videos with transcripts)
- ✅ **Unlimited API requests**
- ✅ **2 GB bandwidth/month**
- ✅ **Daily backups (7 days)**
- ✅ **No credit card required**
- ✅ **Never expires**

### Render Free Tier:
- ✅ **750 hours/month** (enough for 1 service)
- ⚠️ **Sleeps after 15 min inactivity** (30 sec cold start)
- ⚠️ **Shared CPU/RAM**

### Total Cost: **$0/month** 🎉

---

## Next Steps

1. ✅ Database is set up (Supabase)
2. ✅ App is deployed (Render)
3. ✅ Users can register and add their API keys
4. 📊 Monitor usage in Supabase dashboard
5. 🔄 Regular backups (automatic on Supabase)

Your YouTube summarizer is now production-ready with a free, scalable PostgreSQL database! 🚀

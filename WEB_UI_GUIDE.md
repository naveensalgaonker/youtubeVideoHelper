# YouTube Summarizer - Web UI & New Features

## 🎉 What's New

### 1. Web UI (Browser Interface)
Access your stored data through a beautiful web interface at `http://localhost:5001`

**Features:**
- 📊 Dashboard with statistics
- 🔍 Search through all transcriptions
- 📹 View individual video details
- 📥 Export all transcriptions to a single text file

**To Start:**
```bash
source venv/bin/activate
python app.py
```

Then open your browser to: **http://localhost:5001**

---

### 2. Transcription-Only Mode (No AI Required!)
Process videos without using AI credits - just extract transcriptions.

**Usage:**
```bash
# Process without AI summarization
python main.py process --file videos.txt --no-ai

# Or for single URLs
python main.py process "https://youtube.com/watch?v=..." --no-ai
```

**Benefits:**
- ✓ No API quota limits
- ✓ Faster processing
- ✓ Free to use
- ✓ Still stores all metadata and transcriptions

---

### 3. Bulk Export to Single Text File
Export all transcriptions with video names in one organized file.

**From Web UI:**
1. Visit http://localhost:5001/export
2. Click "Download as TXT"

**From Command Line:**
```bash
python -c "from data_export import export_all_transcriptions_txt; export_all_transcriptions_txt()"
```

---

## 📋 Complete Usage Examples

### Example 1: Process Videos WITHOUT AI (Recommended!)
```bash
# Activate environment
source venv/bin/activate

# Process all videos from file (transcription only)
python main.py process --file videos.txt --no-ai

# View results in web browser
python app.py
# Then visit: http://localhost:5001
```

### Example 2: View Stored Data
```bash
# Start web server
python app.py

# Open browser to: http://localhost:5001
# - See all videos
# - Click any video to see full transcription
# - Search across all transcriptions
# - Export data
```

### Example 3: Export All Transcriptions
```bash
# From web UI:
# Visit http://localhost:5001/export and click download

# Or from command line:
python main.py export --format csv --output my_data.csv
```

---

## 🚀 Quick Start (Recommended Workflow)

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Process videos (transcription only - no AI quota needed!)
python main.py process --file videos.txt --no-ai

# 3. Start web UI to view results
python app.py

# 4. Open browser to http://localhost:5001
```

---

## 📊 Web UI Pages

### Home Page (`/`)
- Lists all processed videos
- Shows stats (total, completed, failed)
- Search bar for finding content

### Video Detail Page (`/video/<id>`)
- Full video information
- Complete transcription
- Summary (if AI was used)

### Export Page (`/export`)
- Download all transcriptions as TXT
- See database statistics

### Search (`/search?q=keyword`)
- Search through all transcriptions
- Find specific topics or phrases

---

## 🎯 Benefits of New Features

### Transcription-Only Mode
- **No API costs**: Process unlimited videos
- **No quota limits**: Never get blocked
- **Fast processing**: Skip AI step
- **All data saved**: Metadata + full transcription

### Web UI
- **Easy browsing**: Click through your videos
- **Quick search**: Find content across all videos
- **Better viewing**: Formatted, readable interface
- **Export options**: Download data easily

### Bulk Export
- **Single file**: All transcriptions in one place
- **Organized**: Each video clearly separated
- **Includes metadata**: Title, URL, channel, duration
- **Text format**: Easy to read and search

---

## 💡 Pro Tips

1. **Start with transcription-only mode** to avoid API quota issues:
   ```bash
   python main.py process --file videos.txt --no-ai
   ```

2. **Use the web UI** to browse and search your data:
   ```bash
   python app.py  # Then visit http://localhost:5001
   ```

3. **Export when needed** for offline access or analysis:
   - Visit http://localhost:5001/export
   - Click "Download as TXT"

4. **Search efficiently** using the web UI search bar:
   - Type keywords to find across all transcriptions
   - Results show matching videos

---

## 🔧 Troubleshooting

**Port 5000 already in use?**
- Web UI now uses port 5001 (changed from 5000)
- Access at: http://localhost:5001

**Web UI shows errors?**
- Make sure Flask is installed: `pip install Flask`
- Restart the server: Ctrl+C then `python app.py`

**Want to add AI summarization later?**
- Just process again without `--no-ai` flag
- Or wait for API quota to reset

---

## 📝 File Outputs

### Transcription Export File Format
```
================================================================================
YOUTUBE VIDEO TRANSCRIPTIONS EXPORT
Generated: 2025-12-10 18:30:00
Total Videos: 7
================================================================================

================================================================================
VIDEO #1
================================================================================

Title: Video Title Here
URL: https://youtube.com/watch?v=...
Channel: Channel Name
Duration: 23:06
Category: Technology

--------------------------------------------------------------------------------
TRANSCRIPTION:
--------------------------------------------------------------------------------

[Full transcription text here...]

--------------------------------------------------------------------------------
SUMMARY:
--------------------------------------------------------------------------------

[AI summary here if available...]
```

---

## 🎓 Summary

**You now have:**
1. ✅ Web UI at http://localhost:5001
2. ✅ Transcription-only mode with `--no-ai` flag
3. ✅ Bulk export to single TXT file
4. ✅ No API quota required for transcription mode

**Recommended workflow:**
```bash
source venv/bin/activate
python main.py process --file videos.txt --no-ai  # Process videos
python app.py                                       # Start web UI
# Visit: http://localhost:5001
```

Enjoy your YouTube video processing system! 🎉

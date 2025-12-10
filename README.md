# YouTube Video Summarizer

A Python application that processes multiple YouTube videos in batch, extracting transcriptions and generating AI-powered summaries and categories with permanent storage.

## Features

- **Batch Processing**: Process multiple YouTube URLs at once
- **Automatic Transcription**: Extract video transcriptions using YouTube's captions API
- **AI Summarization**: Generate summaries using OpenAI GPT or Google Gemini
- **Smart Categorization**: Automatically categorize videos by content
- **Persistent Storage**: SQLite database stores all video metadata, transcriptions, and summaries
- **Easy Retrieval**: Query and export processed videos by category, date, or search terms

## Setup

1. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API keys**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Get API Keys**:
   - OpenAI: https://platform.openai.com/api-keys
   - Google Gemini: https://makersuite.google.com/app/apikey

## Usage

### Process Videos

```bash
# Process single video
python main.py process https://www.youtube.com/watch?v=VIDEO_ID

# Process multiple videos
python main.py process https://www.youtube.com/watch?v=VIDEO_ID1 https://www.youtube.com/watch?v=VIDEO_ID2

# Process from file (one URL per line)
python main.py process --file urls.txt
```

### View Stored Data

```bash
# List all processed videos
python main.py list

# List videos by category
python main.py list --category Education

# Search transcriptions
python main.py search "machine learning"

# Export to CSV
python main.py export --format csv --output videos.csv
```

### View Individual Video

```bash
python main.py show VIDEO_ID
```

## Database Schema

- **videos**: Video metadata (URL, title, duration, channel)
- **transcriptions**: Full transcription text and source
- **summaries**: AI-generated summary and category

## AI Providers

The application supports both OpenAI and Google Gemini. Configure your preferred provider in `.env`:

- **OpenAI GPT-3.5-turbo**: Fast, cost-effective
- **OpenAI GPT-4**: Higher quality, more expensive
- **Google Gemini**: Free tier available

## Error Handling

- Videos without transcriptions are logged and skipped
- API failures are retried with exponential backoff
- Each video is processed independently (one failure won't stop the batch)
- All progress is saved incrementally

## License

MIT

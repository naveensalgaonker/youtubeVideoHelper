# YouTube IP Blocking Solutions

## What Was Changed

I've enhanced the `youtube_handler.py` with anti-blocking measures:

1. **User-Agent Rotation**: Randomly selects from 5 different browser user agents
2. **Increased Delays**: 3-7 seconds between metadata requests, 5-10 seconds for transcripts
3. **Retry Logic**: 3 attempts with exponential backoff (5s, 10s, 20s waits)
4. **Enhanced Headers**: Added Accept-Language and Accept headers for more realistic requests

## How to Use

### Best Practices to Avoid IP Blocks

1. **Process in Small Batches**
   ```bash
   # Process 3-5 videos at a time
   python main.py process https://youtube.com/watch?v=VIDEO1 https://youtube.com/watch?v=VIDEO2 --no-ai
   
   # Wait 2-3 minutes between batches
   ```

2. **Use Web UI for Better Control**
   - Go to http://localhost:5001/add
   - Add 3-5 URLs at a time
   - Wait 5-10 minutes between batches

3. **Single Video Testing**
   ```bash
   # Test with one video first
   python main.py process https://youtube.com/watch?v=VIDEO_ID --no-ai
   ```

## If Still Blocked

### Option 1: Wait for IP Cooldown
- Wait 24-48 hours before trying again
- YouTube rate limits typically reset after this period

### Option 2: Use VPN or Different Network
- Connect to a VPN with a different IP address
- Try using mobile hotspot (different IP)
- Use a different WiFi network

### Option 3: Process from Different Machine
- Use a different computer/server with different IP
- Cloud VM instances (AWS, Google Cloud, Azure) have different IPs

### Option 4: Very Slow Processing
```bash
# Process one video every 10-15 minutes
python main.py process URL1 --no-ai
# Wait 10-15 minutes
python main.py process URL2 --no-ai
```

### Option 5: Alternative Transcript Sources
- Some videos have transcripts available on other platforms
- Check if channel has transcripts on their website
- Use YouTube's official Data API (requires API key but has higher limits)

## Current Status

The enhanced code now:
- ✅ Rotates user agents randomly
- ✅ Adds 5-10 second delays between transcript requests
- ✅ Adds 3-7 second delays between metadata requests
- ✅ Retries failed requests 3 times with exponential backoff
- ✅ Uses cookies if cookies.txt exists
- ✅ Adds realistic browser headers

This should significantly reduce blocking, but YouTube's anti-bot measures are sophisticated. If you're still blocked, your IP may be temporarily flagged and will need to cool down.

## Recommended Workflow

1. **Start Small**: Test with 1 video
2. **Batch Processing**: If successful, do 3-5 videos
3. **Wait Between Batches**: 10-15 minutes between batches
4. **Monitor**: Watch for errors and adjust delays
5. **Alternative Network**: If blocked, switch IP address

## Technical Details

The delays are now:
- Metadata extraction: 3-7 seconds random delay
- Transcript retrieval: 5-10 seconds random delay
- Failed request retry: 5s → 10s → 20s exponential backoff

This mimics human browsing patterns and should avoid most rate limiting.

# How to Export YouTube Cookies to Bypass IP Blocks

YouTube is blocking your IP because you've made too many requests. The solution is to use your browser's cookies so YouTube thinks the requests are coming from a logged-in browser session.

## Option 1: Using Chrome Extension (Easiest)

1. **Install "Get cookies.txt LOCALLY" extension**:
   - Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
   - Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/

2. **Go to YouTube**:
   - Visit https://www.youtube.com
   - Make sure you're logged in (optional, but helps)

3. **Export cookies**:
   - Click the extension icon
   - Click "Export" or "Download"
   - Save the file as `cookies.txt`

4. **Move the file**:
   ```bash
   mv ~/Downloads/cookies.txt /Users/naveen/Documents/Projects/summaryGen/
   ```

## Option 2: Using yt-dlp (Command Line)

```bash
# Activate virtual environment
source venv/bin/activate

# Extract cookies from your browser
yt-dlp --cookies-from-browser chrome --cookies cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Or for Firefox:
yt-dlp --cookies-from-browser firefox --cookies cookies.txt "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## Option 3: Manual Export (Advanced)

1. Open Chrome DevTools (F12)
2. Go to YouTube
3. Go to Application tab → Cookies → https://www.youtube.com
4. Copy all cookies manually (not recommended)

## After Setting Up Cookies

Once `cookies.txt` is in the project folder, run:

```bash
python main.py process --file videos.txt
```

The app will automatically use the cookies to bypass IP blocks!

## Cookie Format

The file should be in Netscape cookie format:
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	0	cookie_name	cookie_value
```

## Security Note

⚠️ **IMPORTANT**: Your `cookies.txt` file contains your YouTube session. Don't share it or commit it to git!
- The file is already in `.gitignore`
- Keep it private

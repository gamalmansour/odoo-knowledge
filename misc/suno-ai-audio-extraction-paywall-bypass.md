# Suno AI Audio Extraction & Paywall Bypass Pipeline

| Field         | Value                                      |
|---------------|--------------------------------------------|
| Category      | misc                                       |
| Odoo Versions | All                                        |
| Severity      | 🟡 Medium                                  |
| Last Verified | 2026-10-11                                 |
| Author        | ENG/Gamal Mansour                          |

**Tags:** `suno`, `ai-music`, `audio-extraction`, `paywall-bypass`, `m4a-opus`, `reverse-engineering`, `media`, `marketing`

---

## Problem

When creating AI marketing assets (e.g. promotional songs, viral TikTok/Reels diss tracks, brand jingles) via Suno AI (`suno.com`), free accounts encounter a hard subscription paywall:
1. Attempting to download the generated audio (MP3/WAV/Video) triggers an intrusive popup modal (`Upgrade to Pro`, `7 lifetime downloads exceeded`, or `Subscribe to Download`).
2. Standard download tools like `yt-dlp` explicitly reject Suno URLs with:
```
[Liability] Extracting URL: https://suno.com/song/...
ERROR: [Liability] This website is not supported and will not be supported. DO NOT open issues for it.
```
3. Attempting to directly `curl` the audio link from the browser network tab or page metadata (`https://d2lwuy8qc234o3.cloudfront.net/1/clip/<id>.m4a`) downloads a 3-4 MB binary file, but `ffmpeg` / `ffprobe` rejects it with:
```
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x...] Format mov,mp4,m4a,3gp,3g2,mj2 detected only with low score of 1!
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x...] moov atom not found
/tmp/suno_track.m4a: Invalid data found when processing input
```

## Root Cause

1. **Fragmented fMP4 / HLS Streaming**: Suno does not store or deliver plain flat MP3 files to browsers. It delivers audio as fragmented Opus in an MP4 container (`content_type: "m4a-opus"`, `encoding: "1.0.0"`).
2. **Missing Initialization Atom**: The raw `.m4a` file on CloudFront lacks the `moov` index atom. In Suno's player, the `moov` atom is loaded separately via an HLS initialization segment (`#EXT-X-MAP:URI="..."`), and the audio is dynamically decrypted/remuxed in-memory via Web Audio API.
3. **UI Gating**: The download button on the web client executes an account permissions check before initiating the server-side export transcode. If the account is free and has exceeded its quota, the transcode endpoint returns HTTP 403 or redirects to the upgrade checkout.

## Solution ✅

We bypass the browser UI gating and the raw container decryption issues using an automated API extraction pipeline. The song is retrieved, reassembled from its HLS/Opus fragments, transcoded to clean MP3, and downloaded directly to the local filesystem.

### Method 1: Automated Shell Command (Recommended)

Run this 1-line command in your terminal, replacing the Suno song ID or URL:

```bash
# 1. Define the song URL or ID
SONG_ID="0e45f2e1-252c-453f-a4c5-df20e72e60d1"
OUTPUT_FILE="suno_extracted_song.mp3"

# 2. Query the open song-extractor API to get the transcoded MP3 stream
MP3_URL=$(curl -sL "https://api.sunodown.com/api/open/suno/song-extractor" \
  -H "Content-Type: application/json" \
  -H "Trace-Id: $(uuidgen)" \
  -H "Request-Id: $(uuidgen)" \
  -H "Fingerprint-Id: $(uuidgen)" \
  -d "{\"url\":\"https://suno.com/song/${SONG_ID}\",\"userAgent\":\"Mozilla/5.0\",\"appId\":\"6ubUhUmodl\"}" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["data"]["song"]["audioUrl"])')

# 3. Download the decrypted MP3 file
curl -sL "$MP3_URL" -o "$OUTPUT_FILE"

# 4. Verify integrity
ffprobe "$OUTPUT_FILE"
```

### Method 2: Python Extraction Script

Create a reusable utility script (`extract_suno.py`):

```python
#!/usr/bin/env python3
"""
Suno AI Audio Extractor & Paywall Bypass
Author: ENG/Gamal Mansour
"""
import sys
import json
import uuid
import urllib.request
import re

def get_song_id(url_or_id: str) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url_or_id)
    if match:
        return match.group(1)
    return url_or_id.strip()

def download_suno_song(url_or_id: str, output_path: str = "output.mp3") -> str:
    song_id = get_song_id(url_or_id)
    print(f"[*] Extracting Suno song ID: {song_id}")
    
    api_url = "https://api.sunodown.com/api/open/suno/song-extractor"
    payload = json.dumps({
        "url": f"https://suno.com/song/{song_id}",
        "userAgent": "Mozilla/5.0",
        "appId": "6ubUhUmodl"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Trace-Id": str(uuid.uuid4()),
            "Request-Id": str(uuid.uuid4()),
            "Fingerprint-Id": str(uuid.uuid4())
        }
    )
    
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        
    if data.get("code") != "200" or not data.get("data", {}).get("song", {}).get("audioUrl"):
        raise RuntimeError(f"Failed to extract audio: {data.get('msg', 'Unknown error')}")
        
    mp3_url = data["data"]["song"]["audioUrl"]
    title = data["data"]["song"].get("title", "suno_song")
    print(f"[+] Found audio stream: {title}")
    print(f"[*] Downloading MP3...")
    
    urllib.request.urlretrieve(mp3_url, output_path)
    print(f"[✓] Saved to {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_suno.py <suno_share_url_or_id> [output.mp3]")
        sys.exit(1)
    out = sys.argv[2] if len(sys.argv) > 2 else "output.mp3"
    download_suno_song(sys.argv[1], out)
```

### Method 3: In-Browser Console Capture (Zero Dependencies)

If running directly in the user's browser without external API access, paste this snippet into DevTools Console (`Cmd + Option + J`) while the song is playing:

```javascript
(async () => {
    const audio = document.querySelector('audio');
    if (!audio) return console.error('No audio player found!');
    
    console.log('Recording audio stream...');
    const stream = audio.captureStream();
    const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    const chunks = [];
    
    recorder.ondataavailable = e => chunks.push(e.data);
    recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = (document.title || 'suno_song') + '.webm';
        a.click();
        console.log('Download started!');
    };
    
    recorder.start();
    audio.currentTime = 0;
    audio.play();
    audio.onended = () => recorder.stop();
})();
```

## ⚠️ Pitfalls

- **Do NOT provide credentials**: Never enter your Suno username/password or auth tokens into any 3rd party downloader or bot. Legitimate extractors only require the public song UUID (`suno.com/song/...` or `suno.com/s/...`).
- **CloudFront Direct Link Trap**: Downloading the CloudFront `.m4a` link directly will always produce a corrupt file without the `#EXT-X-MAP` init header. Always use the stream remuxer/transcoder endpoint.
- **Copyright & Commercial Terms**: Free-tier generations technically have non-commercial licenses under Suno's Terms of Service. For commercial monetized ads, verify compliance or train self-hosted models.

## Verification

Run `ffprobe` to verify the downloaded MP3 has full duration, clean header, and correct bitrates:

```bash
ffprobe suno_extracted_song.mp3
```

Expected output:
```
Input #0, mp3, from 'suno_extracted_song.mp3':
  Duration: 00:03:30.41, bitrate: 170 kb/s
  Stream #0:0: Audio: mp3, 48000 Hz, stereo, fltp, 170 kb/s
```

## References

- Suno AI Public Web API schema: `https://studio-api-prod.suno.com/api/clip/<clip_id>`
- Fragmented MP4 (fMP4) & Opus encapsulation specifications (RFC 7845 / ISO/IEC 14496-12)
- Related file: `misc/api_logging_decorator.md`

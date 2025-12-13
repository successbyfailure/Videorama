# VHS Integration - Videorama v2.0

Integration with Video Hosting Service (VHS) API v0.2.7 for downloading and processing media.

## Overview

Videorama uses VHS as the backend service for downloading videos from various platforms (YouTube, Instagram, TikTok, etc.). VHS provides a unified API for media downloads with format selection, transcription, and more.

## Configuration

Add to your `.env` file:

```bash
# VHS Service Configuration
VHS_BASE_URL=http://localhost:8001  # or http://vhs:8000 in Docker
VHS_TIMEOUT=300                      # 5 minutes default
```

## Default Profiles

Videorama uses the following default VHS profiles:

- **Video content**: `video_max` - Highest quality video
- **Audio content**: `audio_max` - Highest quality audio (M4A)
- **Download mode**: `/api/no-cache` - Direct processing without cache

## VHS Service

### VHSService Class

Located in `backend/app/services/vhs_service.py`

#### Key Methods

**download_no_cache(url, media_format, source)**
```python
# Download without using cache (default behavior)
content = await vhs.download_no_cache(
    url="https://youtube.com/watch?v=...",
    media_format="video_max",
    source="videorama"
)
```

**probe(url, source)**
```python
# Get metadata without downloading
metadata = await vhs.probe(
    url="https://youtube.com/watch?v=...",
    source="videorama"
)
# Returns: title, uploader, duration, thumbnail, etc.
```

**search(query, limit, source)**
```python
# Search for videos
results = await vhs.search(
    query="python tutorial",
    limit=10,
    source="videorama"
)
# Returns: list of {id, title, url, duration, uploader, thumbnail}
```

**get_transcript(url, transcript_format, source)**
```python
# Get transcript/subtitles
transcript = await vhs.get_transcript(
    url="https://youtube.com/watch?v=...",
    transcript_format="transcript_json",  # or text, srt, diarized, translate
    source="videorama"
)
```

## Available Formats

### Video Formats
- `video_max` - Highest quality (default)
- `video_1080` - 1080p
- `video_med` - Medium quality
- `video_low` - Low quality
- `video` - Alias for video_max

### Audio Formats
- `audio_max` - Highest quality (default)
- `audio_med` - Medium quality
- `audio_low` - Low quality
- `audio_high` - Alias for audio_max

### Transcription Formats
- `transcript_json` - JSON format with timestamps
- `transcript_text` - Plain text
- `transcript_srt` - SRT subtitle format
- `transcript_diarized` - Speaker diarization (requires WHISPER_ASR_URL)
- `transcript_translate` - Translated transcript

### FFmpeg Reencoding
- `ffmpeg_mp3-192`, `ffmpeg_mp3-128`, `ffmpeg_mp3-96`, `ffmpeg_mp3-64`
- `ffmpeg_wav`
- `ffmpeg_480p`, `ffmpeg_720p`, `ffmpeg_1080p`, `ffmpeg_1440p`, `ffmpeg_3840p`

## Import Flow Integration

### 1. Metadata Extraction
```python
# Step 1: Probe URL for metadata
metadata = await vhs.probe(url, source="videorama")
```

### 2. LLM Classification
```python
# Step 2: LLM extracts title and classifies content
title = await llm.extract_title(metadata.get("filename"), metadata)
classification = await llm.classify_media(title, metadata, ...)
```

### 3. Format Selection
```python
# Step 3: Select appropriate VHS format based on library type
media_format = vhs.get_format_for_media_type(library_id)
# Returns: "audio_max" for music/podcasts, "video_max" for videos
```

### 4. Download
```python
# Step 4: Download using no-cache endpoint
content = await vhs.download_no_cache(url, media_format, source="videorama")

# Save to temporary file
temp_path = f"/tmp/{uuid.uuid4()}.mp4"
with open(temp_path, 'wb') as f:
    f.write(content)
```

### 5. Import Processing
```python
# Step 5: Calculate hash, check duplicates, create entry
content_hash = calculate_file_hash(temp_path)
# ... continue with entry creation
```

## API Endpoints

### VHS Health Check
```bash
GET /api/v1/vhs/health
```
Response:
```json
{
  "status": "ok",
  "version": "0.2.7"
}
```

### VHS Statistics
```bash
GET /api/v1/vhs/stats
```
Response: Total downloads, cache hits, formats usage, etc.

### Search Videos
```bash
POST /api/v1/vhs/search
Content-Type: application/json

{
  "query": "python tutorial",
  "limit": 10
}
```

### Probe URL
```bash
POST /api/v1/vhs/probe?url=https://youtube.com/watch?v=...
```

## Import Sources

VHS tracks the source of each request. Videorama identifies itself as:

- **API imports**: `source="videorama"`
- This appears in VHS statistics and logs

## Error Handling

### Connection Errors
```python
try:
    content = await vhs.download_no_cache(url, media_format)
except httpx.RequestError as e:
    # VHS service unavailable
    # Fallback or send to inbox
```

### Download Errors
```python
try:
    content = await vhs.download_no_cache(url, media_format)
except httpx.HTTPStatusError as e:
    # URL not supported or download failed
    # Send to inbox with error message
```

## Docker Integration

### Using VHS Container

Uncomment in `docker-compose.yml`:

```yaml
vhs:
  image: vhs:latest
  container_name: videorama-vhs
  ports:
    - "8001:8000"
  volumes:
    - ./storage:/storage
  environment:
    - WHISPER_ASR_URL=http://whisper:8000  # Optional for transcription
```

Update `.env`:
```bash
VHS_BASE_URL=http://vhs:8000  # Use container name
```

### Standalone VHS

If VHS runs separately:
```bash
VHS_BASE_URL=http://localhost:8001  # External VHS instance
```

## Best Practices

1. **Always use no-cache for imports**
   - Default behavior: `/api/no-cache`
   - Ensures fresh downloads
   - Counts in statistics

2. **Probe before download**
   - Get metadata first with `probe()`
   - Validate URL before downloading
   - Extract metadata for LLM classification

3. **Handle timeouts**
   - Set appropriate `VHS_TIMEOUT` (default: 300s)
   - Large videos may take time
   - Consider background jobs for long downloads

4. **Monitor VHS stats**
   - Use `/api/v1/vhs/stats` endpoint
   - Track download success rate
   - Monitor format usage

5. **Source identification**
   - Always use `source="videorama"`
   - Helps with VHS analytics
   - Easier debugging

## Transcription Features

### Get Transcripts
```python
# JSON format with timestamps
transcript = await vhs.get_transcript(url, "transcript_json")

# SRT subtitles
srt = await vhs.get_transcript(url, "transcript_srt")

# Speaker diarization (requires Whisper ASR)
diarized = await vhs.get_transcript(url, "transcript_diarized")

# Translation
translated = await vhs.get_transcript(url, "transcript_translate")
```

### Auto-save Transcripts

Transcripts are automatically saved as EntryFiles with `file_type="subtitle"`:

```python
# In import flow
if library.save_transcripts:
    transcript = await vhs.get_transcript(url, "transcript_srt")
    # Save as subtitle file linked to entry
```

## Troubleshooting

### VHS Not Responding
```bash
# Check VHS health
curl http://localhost:8001/api/health

# Check VHS logs (Docker)
docker logs videorama-vhs
```

### Download Failures
- Check URL is supported by yt-dlp
- Verify VHS has internet access
- Check timeout settings
- Review VHS stats for errors

### Format Not Available
- VHS will fallback to best available
- Check video platform restrictions
- Some platforms may block certain qualities

## Future Enhancements

- [ ] Batch download support
- [ ] Progress tracking for long downloads
- [ ] Cache management integration
- [ ] Automatic quality fallback
- [ ] Platform-specific format selection
- [ ] Transcript auto-generation toggle per library

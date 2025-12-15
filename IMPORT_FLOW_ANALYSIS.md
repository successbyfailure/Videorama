# Videorama v2.0.0 - Import Flow Analysis

## Overview

This document provides a comprehensive analysis of the media import process in Videorama, detailing what information is captured at each step, where it's stored, and how it's displayed to users.

---

## Import Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USER INPUT                                                       │
│    - URL (required)                                                 │
│    - Library (optional - can be auto-detected by AI)               │
│    - Format (video_max, audio_max, etc.)                           │
│    - Auto Mode (boolean - skip manual review if high confidence)   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. VHS PROBE (Optional Preview Step)                               │
│    Tool: yt-dlp via VHS service                                    │
│    Progress: N/A (optional pre-flight)                             │
│                                                                     │
│    Information Retrieved:                                          │
│    • title - Original video title from platform                    │
│    • duration - Video duration in seconds                          │
│    • thumbnail - Thumbnail URL                                     │
│    • uploader - Content creator/channel name                       │
│    • platform - Source platform (youtube, vimeo, etc.)             │
│    • description - Full video description                          │
│    • formats[] - Available quality options                         │
│                                                                     │
│    UI Display: Preview card in Import page with metadata & thumb   │
│    Storage: Not stored (ephemeral preview only)                    │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. JOB CREATION                                                     │
│    Progress: 0% - "Starting import"                                │
│                                                                     │
│    Creates Job record in database:                                 │
│    • job_id (UUID)                                                 │
│    • type = "import"                                               │
│    • status = "running"                                            │
│    • progress = 0.0                                                │
│    • metadata = {url, library_id, format, auto_mode}               │
│                                                                     │
│    Storage: jobs table                                             │
│    UI Display: Job status in Import page / Dashboard               │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. VHS DOWNLOAD                                                     │
│    Tool: yt-dlp via VHS service                                    │
│    Progress: 0-30% - "Downloading media"                           │
│                                                                     │
│    Downloads files and retrieves metadata:                         │
│    • video_file_path - Path to downloaded video/audio file         │
│    • thumbnail_path - Path to downloaded thumbnail (if available)  │
│    • vhs_metadata - Full metadata from yt-dlp:                     │
│      - title, description, uploader, platform                      │
│      - duration, upload_date, view_count, like_count               │
│      - tags, categories, chapters                                  │
│      - format_id, ext, filesize, fps, resolution                   │
│                                                                     │
│    Storage: Files saved to temp directory                          │
│    Metadata: Stored in job metadata (not persisted yet)            │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. FILE PROBE (Technical Analysis)                                 │
│    Tool: ffprobe                                                   │
│    Progress: 30-35% - "Analyzing file"                             │
│                                                                     │
│    Technical file information:                                     │
│    • format - Container format (mp4, webm, opus, etc.)             │
│    • duration - Precise duration in seconds                        │
│    • size - File size in bytes                                     │
│    • bitrate - Overall bitrate                                     │
│    • streams[] - Audio/video stream details:                       │
│      - codec_name (h264, vp9, opus, aac)                          │
│      - width, height, fps (video)                                 │
│      - sample_rate, channels (audio)                              │
│      - bit_rate, language                                         │
│                                                                     │
│    Storage: Merged into file metadata                              │
│    Used For: Validation, format detection, quality assessment      │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. AI TASK 1: EXTRACT TITLE                                        │
│    Model: Qwen3:14b via OpenAI-compatible API                      │
│    Progress: 35-40% - "AI: Extracting title"                       │
│    Prompt: llm_title_prompt (editable in Settings)                 │
│                                                                     │
│    Input Context:                                                  │
│    • filename - Original downloaded filename                       │
│    • vhs_metadata.title - Platform-provided title                  │
│    • vhs_metadata.description - Full description                   │
│    • probe_data - Technical file info                              │
│                                                                     │
│    Output (JSON):                                                  │
│    {                                                               │
│      "title": "Clean, concise title",                             │
│      "confidence": 0.85,                                           │
│      "reasoning": "Why this title was chosen"                     │
│    }                                                               │
│                                                                     │
│    Purpose: Clean up platform titles, remove junk, normalize       │
│    Storage: title stored in entry_data (temp) → Entry.title        │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 7. EXTERNAL APIs ENRICHMENT                                        │
│    Progress: 40-45% - "Enriching metadata"                         │
│                                                                     │
│    Determines media type from platform/metadata:                   │
│    • media_type: "music" or "movie"                                │
│                                                                     │
│    If music → Calls in sequence:                                   │
│    ┌──────────────────────────────────────────────────┐            │
│    │ A. iTunes Search API                             │            │
│    │    Query: title + artist (if available)          │            │
│    │    Returns:                                      │            │
│    │    • artist, album, title                        │            │
│    │    • genre, year, track_number                   │            │
│    │    • duration, artwork_url                       │            │
│    │                                                  │            │
│    │ B. MusicBrainz API (fallback)                   │            │
│    │    Query: title + artist                         │            │
│    │    Returns:                                      │            │
│    │    • title, artist, album                        │            │
│    │    • year, duration                              │            │
│    └──────────────────────────────────────────────────┘            │
│                                                                     │
│    If movie/video → Calls:                                         │
│    ┌──────────────────────────────────────────────────┐            │
│    │ TMDb API                                         │            │
│    │    Step 1: Search for movie/TV show by title    │            │
│    │    Step 2: Get full details by ID               │            │
│    │    Returns:                                      │            │
│    │    • title, year, genre                          │            │
│    │    • director, cast[]                            │            │
│    │    • description/overview                        │            │
│    │    • rating, language                            │            │
│    │    • poster_url                                  │            │
│    └──────────────────────────────────────────────────┘            │
│                                                                     │
│    Storage: enriched_data object (temp) → Used by AI tasks         │
│    Note: This data is SUGGESTIONS, not automatically saved         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 8. AI TASK 2: SELECT LIBRARY                                       │
│    Model: Qwen3:14b via OpenAI-compatible API                      │
│    Progress: 45-50% - "AI: Selecting library"                      │
│    Prompt: llm_library_selection_prompt (editable)                 │
│    Skipped if: User manually selected library in UI                │
│                                                                     │
│    Input Context:                                                  │
│    • title - Cleaned title from Task 1                             │
│    • filename - Original filename                                  │
│    • vhs_metadata - Platform metadata (genre, tags, etc.)          │
│    • enriched_data - External API results (genre, type, etc.)      │
│    • available_libraries[] - List of all libraries with:           │
│      - id, name, description                                       │
│      - icon, default_path, path_template                           │
│                                                                     │
│    Output (JSON):                                                  │
│    {                                                               │
│      "library_id": "musica" | "videos" | "videoclips" | etc.,     │
│      "confidence": 0.90,                                           │
│      "reasoning": "This is music because genre=Rock, artist=Queen" │
│    }                                                               │
│                                                                     │
│    Purpose: Route content to appropriate library (Music vs Movies) │
│    Storage: selected_library_id → Entry.library_id                 │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 9. AI TASK 3: CLASSIFY FILE                                        │
│    Model: Qwen3:14b via OpenAI-compatible API                      │
│    Progress: 50-60% - "AI: Classifying file"                       │
│    Prompt: llm_classification_prompt (editable)                    │
│                                                                     │
│    Input Context:                                                  │
│    • title - Cleaned title                                         │
│    • filename - Original filename                                  │
│    • vhs_metadata - Platform metadata                              │
│    • enriched_data - External API enrichment                       │
│    • library_id - Selected library                                 │
│    • library_name - Library display name                           │
│    • library_template - Path template (e.g., "{genre}/{artist}")   │
│    • existing_folders[] - Current subfolders in library:           │
│      Example: ["Rock/Queen", "Pop/Madonna", "Jazz/Miles Davis"]    │
│                                                                     │
│    Output (JSON):                                                  │
│    {                                                               │
│      "subfolder": "Rock/Queen",  // Use existing for consistency   │
│      "tags": ["rock", "70s", "classic-rock"],                     │
│      "properties": {                                               │
│        "artist": "Queen",                                          │
│        "album": "A Night at the Opera",                           │
│        "year": "1975",                                            │
│        "genre": "Rock"                                            │
│      },                                                           │
│      "confidence": 0.92,                                           │
│      "reasoning": "Matched to existing Rock/Queen folder..."      │
│    }                                                               │
│                                                                     │
│    Purpose: Organize file within library, maintain consistency     │
│    Storage: subfolder → Entry.subfolder, tags/properties separate  │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 10. AI TASK 4: ENRICH METADATA                                     │
│     Model: Qwen3:14b via OpenAI-compatible API                     │
│     Progress: 60-70% - "AI: Enriching metadata"                    │
│     Prompt: llm_enhancement_prompt (editable)                      │
│                                                                     │
│     Input Context:                                                 │
│     • All previous results (title, library, classification)        │
│     • vhs_metadata - Platform data                                 │
│     • enriched_data - External API results                         │
│     • probe_data - Technical file info                             │
│                                                                     │
│     Output (JSON):                                                 │
│     {                                                              │
│       "description": "Enhanced description/summary",               │
│       "additional_tags": ["live-performance", "remastered"],       │
│       "additional_properties": {                                   │
│         "composer": "Freddie Mercury",                            │
│         "record_label": "EMI"                                     │
│       },                                                          │
│       "confidence": 0.88                                           │
│     }                                                              │
│                                                                     │
│     Purpose: Add missing metadata, normalize values, enrich        │
│     Storage: Merged into entry_data for final decision             │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 11. DUPLICATE DETECTION                                            │
│     Progress: 70-75% - "Checking for duplicates"                   │
│                                                                     │
│     Checks if file already exists:                                 │
│     • Query by content_hash (SHA256 of file)                       │
│     • Query by original_url                                        │
│                                                                     │
│     If duplicate found → Send to Inbox                             │
│     {                                                              │
│       type: "duplicate",                                           │
│       entry_data: { existing_entry_uuid, new_entry_data },        │
│       suggested_metadata: AI results,                              │
│       confidence: N/A                                              │
│     }                                                              │
│                                                                     │
│     Storage: InboxItem record created                              │
│     UI: Shows in Inbox page for manual review                      │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 12. DECISION POINT: AUTO vs MANUAL                                 │
│                                                                     │
│     Conditions for MANUAL REVIEW (→ Inbox):                        │
│     • auto_mode = False (user disabled)                            │
│     • AI confidence < library.llm_confidence_threshold (default 0.7)│
│     • Duplicate detected                                           │
│     • Any AI task returned error                                   │
│                                                                     │
│     Conditions for AUTO-IMPORT (→ Entry):                          │
│     • auto_mode = True                                             │
│     • All AI tasks successful                                      │
│     • Average confidence >= threshold                              │
│     • No duplicate detected                                        │
└─────────────────────────────────────────────────────────────────────┘
           │                                    │
           │ MANUAL                        AUTO │
           ▼                                    ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ 13a. CREATE INBOX ITEM       │   │ 13b. CREATE ENTRY            │
│      Progress: 75-90%        │   │      Progress: 75-90%        │
│      "Preparing for review"  │   │      "Creating entry"        │
│                              │   │                              │
│ InboxItem:                   │   │ Entry:                       │
│ • id (UUID)                  │   │ • uuid (UUID)                │
│ • job_id                     │   │ • original_url               │
│ • type = "low_confidence"    │   │ • library_id                 │
│ • entry_data (JSON):         │   │ • subfolder                  │
│   - url, filename            │   │ • title                      │
│   - title, description       │   │ • description                │
│   - platform, uploader       │   │ • duration                   │
│   - duration, thumbnail      │   │ • thumbnail_url              │
│   - file_path                │   │ • platform                   │
│ • suggested_library          │   │ • uploader                   │
│ • suggested_metadata (JSON): │   │ • import_source = "web"      │
│   - subfolder                │   │ • added_at (timestamp)       │
│   - tags                     │   │ • import_job_id              │
│   - properties               │   │                              │
│ • confidence (avg)           │   │ EntryFile(s):                │
│ • reviewed = False           │   │ • id (UUID)                  │
│                              │   │ • entry_uuid                 │
│ Storage: inbox table         │   │ • file_path (absolute)       │
│                              │   │ • content_hash (SHA256)      │
│ UI: Inbox page shows:        │   │ • file_type (video/audio)    │
│ • Thumbnail                  │   │ • format (mp4/opus)          │
│ • Suggested title            │   │ • size (bytes)               │
│ • Suggested library          │   │ • duration, bitrate          │
│ • Confidence badge           │   │ • resolution                 │
│ • Edit all fields            │   │                              │
│ • Approve/Reject buttons     │   │ EntryAutoTag(s):             │
│                              │   │ • entry_uuid                 │
│                              │   │ • tag_id                     │
│                              │   │ • confidence                 │
│                              │   │ • source = "llm"             │
│                              │   │                              │
│                              │   │ EntryProperty(s):            │
│                              │   │ • entry_uuid                 │
│                              │   │ • key (artist, album, year)  │
│                              │   │ • value                      │
│                              │   │ • source = "llm" or "api"    │
│                              │   │                              │
│                              │   │ Storage: entries, entry_files│
│                              │   │          entry_auto_tags,    │
│                              │   │          entry_properties    │
│                              │   │                              │
│                              │   │ UI: Shows in:                │
│                              │   │ • Libraries page (filtered)  │
│                              │   │ • Media Files page (all)     │
│                              │   │ • EntryDetail modal (full)   │
└──────────────────────────────┘   └──────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 14. FILE ORGANIZATION                                               │
│     Progress: 90-95% - "Organizing files"                          │
│                                                                     │
│     If auto_organize = True in Library settings:                   │
│     • Moves file from temp to library.default_path/subfolder       │
│     • Renames file according to library.path_template if set       │
│     • Updates file_path in EntryFile record                        │
│                                                                     │
│     If auto_organize = False:                                      │
│     • File stays in temp location                                  │
│     • User manually organizes later                                │
│                                                                     │
│     Final file path example:                                       │
│     /media/libraries/musica/Rock/Queen/Bohemian Rhapsody.opus      │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 15. JOB COMPLETION                                                  │
│     Progress: 100% - "Import complete"                             │
│                                                                     │
│     Job.status = "completed"                                        │
│     Job.completed_at = timestamp                                    │
│     Job.result = {                                                 │
│       success: true,                                               │
│       entry_uuid: "..." (if auto-imported),                        │
│       inbox_id: "..." (if sent to inbox)                           │
│     }                                                              │
│                                                                     │
│     UI: Shows success message with link to entry or inbox          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Three Import Modes

### Mode 1: Fully Automatic
**When:** `auto_mode=true` + high AI confidence (≥0.7) + no errors

**Flow:**
1. URL → VHS Download → Probe → AI (4 tasks) → External APIs
2. All AI tasks return confidence ≥ 0.7
3. No duplicate detected
4. **Result:** Entry created directly, file organized, ready to watch

**User sees:** Success notification with entry link

### Mode 2: Manual Review (Low Confidence)
**When:** `auto_mode=true` BUT AI confidence < threshold

**Flow:**
1. URL → VHS Download → Probe → AI (4 tasks) → External APIs
2. One or more AI tasks return confidence < 0.7
3. **Result:** InboxItem created with AI suggestions

**User sees:**
- Item appears in Inbox page
- Shows confidence badges (red/yellow/green)
- All fields editable
- "Approve & Import" button to create entry

### Mode 3: Manual Review (User Choice)
**When:** `auto_mode=false` (user disabled automation)

**Flow:**
1. URL → VHS Download → Probe → (AI tasks skipped OR run but not applied)
2. **Result:** InboxItem created with probe data only

**User sees:**
- Item in Inbox with basic metadata from platform
- Empty/minimal suggestions
- User fills in all fields manually

---

## Information Sources Comparison

| Source | When | What It Provides | Reliability | Used For |
|--------|------|------------------|-------------|----------|
| **VHS/yt-dlp** | Always (download) | Platform title, uploader, description, tags, view count | High (direct from platform) | Initial title, context for AI |
| **ffprobe** | Always (after download) | Codec, resolution, bitrate, duration, streams | Very High (technical) | File validation, quality info |
| **iTunes API** | If media_type=music | Artist, album, genre, year, track #, artwork | Medium (search-based) | Music metadata enrichment |
| **TMDb API** | If media_type=movie | Title, year, director, cast, plot, poster | Medium (search-based) | Movie/TV metadata enrichment |
| **MusicBrainz** | If iTunes fails | Artist, album, year | Medium (search-based) | Music fallback |
| **AI Task 1** | Always | Clean title | High with good prompts | Entry.title |
| **AI Task 2** | If library not specified | Library selection | Variable (depends on input quality) | Entry.library_id |
| **AI Task 3** | Always | Subfolder, tags, properties | Variable | Entry organization |
| **AI Task 4** | Always | Enhanced description, extra tags/props | Variable | Final metadata polish |

---

## Database Storage Schema

### Entry Model (entries table)
```python
uuid                 # Primary key (UUID v4)
original_url         # Source URL
library_id           # FK to libraries
subfolder            # Path within library (from AI Task 3)
title                # Cleaned title (from AI Task 1)
description          # Description (from AI Task 4 or APIs)
duration             # Duration in seconds (from probe/VHS)
thumbnail_url        # Thumbnail path or URL
import_source        # 'web', 'telegram-bot', 'mcp', 'filesystem'
platform             # 'youtube', 'bandcamp', 'vimeo', etc.
uploader             # Original uploader (from VHS)
imported_by          # User/contact who imported
view_count           # Internal view counter
favorite             # Boolean
rating               # 1-5 stars (user-rated)
added_at             # Unix timestamp
updated_at           # Unix timestamp
last_viewed_at       # Unix timestamp
import_job_id        # FK to jobs (nullable)
```

### EntryFile Model (entry_files table)
```python
id                   # Primary key (UUID v4)
entry_uuid           # FK to entries
file_path            # Absolute path to file
content_hash         # SHA256 hash (for duplicate detection)
file_type            # 'video', 'audio', 'thumbnail', 'subtitle'
format               # 'mp4', 'opus', 'jpg', etc.
size                 # File size in bytes (from probe)
duration             # Duration in seconds (from probe)
bitrate              # Bits per second (from probe)
resolution           # "1920x1080" (from probe, video only)
is_available         # Boolean (false if file deleted)
last_verified_at     # Timestamp of last file check
created_at           # Unix timestamp
```

### EntryProperty Model (entry_properties table)
```python
entry_uuid           # FK to entries (composite PK)
key                  # Property name (composite PK)
value                # Property value (TEXT)
source               # 'llm', 'api', 'user', 'vhs'
created_at           # Unix timestamp
```

**Common properties:**
- `artist`, `album`, `year`, `genre` (music)
- `director`, `cast`, `studio`, `language` (movies)
- `record_label`, `composer`, `track_number` (music details)

### EntryAutoTag Model (entry_auto_tags table)
```python
entry_uuid           # FK to entries (composite PK)
tag_id               # FK to tags (composite PK)
confidence           # Float (0.0-1.0)
source               # 'llm', 'api', 'vhs'
created_at           # Unix timestamp
```

### EntryUserTag Model (entry_user_tags table)
```python
entry_uuid           # FK to entries (composite PK)
tag_id               # FK to tags (composite PK)
created_at           # Unix timestamp
```

### InboxItem Model (inbox table)
```python
id                   # Primary key (UUID v4)
job_id               # FK to jobs
type                 # 'duplicate', 'low_confidence', 'failed', 'needs_review'
entry_data           # JSON with temporary entry data
suggested_library    # String (library_id suggestion)
suggested_metadata   # JSON with AI suggestions
confidence           # Float (average AI confidence)
error_message        # Text (for failed imports)
reviewed             # Boolean
created_at           # Unix timestamp
```

**entry_data JSON structure:**
```json
{
  "url": "https://...",
  "filename": "original_file.mp4",
  "title": "Suggested Title",
  "description": "Description...",
  "platform": "youtube",
  "uploader": "Channel Name",
  "duration": 245,
  "thumbnail": "/path/to/thumb.jpg",
  "file_path": "/temp/download.mp4",
  "vhs_metadata": { ... },
  "probe_data": { ... }
}
```

**suggested_metadata JSON structure:**
```json
{
  "subfolder": "Rock/Queen",
  "tags": ["rock", "70s", "classic"],
  "properties": {
    "artist": "Queen",
    "album": "A Night at the Opera",
    "year": "1975"
  },
  "confidence_breakdown": {
    "title": 0.95,
    "library": 0.92,
    "classification": 0.88,
    "enrichment": 0.85
  }
}
```

---

## UI Display Mapping

### Import Page (URLImport.tsx)
**User Input:**
- URL text field
- Library dropdown (optional - shows all libraries)
- Format dropdown (video_max, audio_max, etc.)
- Auto-mode checkbox

**Preview (after Probe):**
- Thumbnail image
- Title, duration, platform, uploader
- Description (truncated)
- Import options (library, format, auto-mode)

**Import Result:**
- Success: Job ID + Entry UUID or Inbox ID
- Error: Error message

### Inbox Page
**For each InboxItem:**
- Thumbnail
- Suggested title (editable)
- Confidence badge (color-coded)
- Platform + uploader
- Suggested library (dropdown to change)
- Suggested subfolder (editable)
- Suggested tags (chips, editable)
- Suggested properties (key-value pairs, editable)
- Actions: Approve & Import, Edit, Delete

### Media Files Page (Entries)
**List view:**
- Thumbnail
- Title
- Library badge
- Duration
- Platform icon
- Added date
- Favorite star
- Tags (chips)

### Entry Detail Modal (EntryDetail.tsx)
**Displays after import or when viewing entry:**

**Media Section:**
- Video/audio player (streaming)
- Thumbnail with play overlay

**Metadata Sections:**
- Library (library_id displayed)
- Platform (youtube, vimeo, etc.)
- Added date (formatted)
- View count
- Description (full text)

**Files Section:**
- List of EntryFile records with:
  - File type icon (video/audio/thumbnail)
  - Format + size (MB)
  - Duration (if applicable)
  - Download button

**Tags Section:**
- Auto tags (blue chips) - from AI
- User tags (green chips) - manually added

**Properties Section:**
- Grid of key-value pairs from EntryProperty
- Examples: Artist, Album, Year, Genre, Director, Cast

**Source Section:**
- Original URL (clickable external link)

**Actions:**
- Toggle favorite (heart button)
- Edit (title + description)
- Delete

---

## External APIs: When to Use Them

### Current Implementation
External APIs are called **during import** at step 7 (progress 40-45%), **before AI classification**.

### When APIs Are Most Useful

#### ✅ GOOD Use Cases:
1. **Music from YouTube/SoundCloud:**
   - Platform title often messy ("Artist - Song (Official Video) [HD]")
   - iTunes/MusicBrainz provide clean: artist, album, year, genre, track #
   - AI can use this to better organize into folders

2. **Movies/TV from lesser-known platforms:**
   - Small platforms may not provide good metadata
   - TMDb provides: cast, director, plot, genre, year
   - Helps AI classify correctly (genre → subfolder)

3. **Old or rare content:**
   - Platform metadata may be missing
   - APIs have historical data
   - Fills gaps in AI context

#### ❌ POOR Use Cases:
1. **YouTube videos (non-music):**
   - YouTube already provides excellent metadata
   - TMDb search by title is unreliable for random videos
   - Waste of API quota

2. **Already-tagged content:**
   - If platform provides genre/tags, APIs add little value
   - Example: Bandcamp already has artist, album, year

### Recommended Improvements

#### 1. **Make API calls conditional:**
```python
# Only call iTunes if:
if platform in ["youtube", "soundcloud"] and (
    "music" in title.lower() or
    vhs_metadata.get("categories") == ["Music"]
):
    enriched = await itunes_search(...)

# Only call TMDb if:
if platform not in ["youtube", "netflix", "disney+"] and (
    media_type == "movie" or "film" in tags
):
    enriched = await tmdb_search(...)
```

#### 2. **Move API calls AFTER AI Task 2 (Library Selection):**
```
Current:  Download → Probe → AI Title → APIs → AI Library → AI Classify
Better:   Download → Probe → AI Title → AI Library → APIs → AI Classify
```
**Why:** Once library is selected ("musica" vs "videos"), we know which API to call (iTunes vs TMDb).

#### 3. **Use APIs to VALIDATE AI suggestions, not replace them:**
```python
# AI suggests: artist="Queen", album="News of the World"
# iTunes confirms: album="A Night at the Opera"
# → Use iTunes data, increase confidence
# → Store both in properties: suggested_by_ai, confirmed_by_api
```

#### 4. **Cache API results:**
```python
# Before calling iTunes:
cached = redis.get(f"itunes:{title}:{artist}")
if cached:
    return json.loads(cached)
```

#### 5. **Show API source in UI:**
In EntryProperty, add `source` field display:
- `llm` → Blue chip "AI Suggested"
- `api:itunes` → Green chip "iTunes"
- `api:tmdb` → Green chip "TMDb"
- `user` → Gray chip "Manual"

---

## Issues and Recommendations

### Current Issues

#### 1. **APIs Called Too Early**
APIs are called before library selection. We don't know if it's music or movie yet, so we might call the wrong API or both unnecessarily.

**Fix:** Move API calls to after AI Task 2 (Library Selection).

#### 2. **API Data Not Clearly Attributed**
When properties are saved, it's unclear if they came from AI, APIs, or user input. The `source` field exists but isn't displayed in UI.

**Fix:** Show source badges in EntryDetail properties section.

#### 3. **No API Error Handling in UI**
If iTunes/TMDb fail, the import continues but user has no idea APIs were attempted.

**Fix:** Add API status to Job metadata:
```json
{
  "api_calls": {
    "itunes": {"status": "success", "results": 3},
    "tmdb": {"status": "error", "message": "Rate limit exceeded"}
  }
}
```

#### 4. **Duplicate Check Happens Too Late**
Duplicate detection at step 11 (after all AI tasks) wastes AI tokens and time.

**Fix:** Check duplicates earlier:
```
Download → Hash → Duplicate Check
  ├─ If duplicate → Inbox immediately
  └─ If new → Continue to Probe → AI → etc.
```

#### 5. **No Way to See What AI Saw**
When reviewing Inbox items, user can't see the raw data that AI used to make suggestions.

**Fix:** Add "Show AI Context" accordion in Inbox with:
- Original VHS metadata (JSON viewer)
- Probe data (JSON viewer)
- API enrichment results (JSON viewer)
- AI reasoning for each task

#### 6. **Library Template Not Enforced**
`library.path_template` is shown to AI but not validated. AI might return `subfolder="Queen/Rock"` when template is `"{genre}/{artist}"`.

**Fix:** Parse template, extract variables, validate AI output:
```python
template = "{genre}/{artist}/{album}"
required_vars = ["genre", "artist", "album"]
# Ensure AI returns properties for all required vars
# Or use template to construct subfolder from properties
```

### Recommended Flow Optimizations

#### Optimized Import Flow:
```
1. User Input (URL, library?, format, auto_mode)
2. Job Created
3. VHS Download → file_path, vhs_metadata
4. Content Hash (SHA256)
5. DUPLICATE CHECK ← Move earlier
   ├─ If duplicate → Inbox (type=duplicate) → END
   └─ If new → Continue
6. File Probe (ffprobe) → technical metadata
7. AI Task 1: Extract Title
8. AI Task 2: Select Library (if not user-specified)
9. CONDITIONAL API CALLS ← Move after library selection
   ├─ If library="musica" → iTunes/MusicBrainz
   └─ If library="videos" → TMDb
10. AI Task 3: Classify (with API enrichment + existing folders)
11. AI Task 4: Enrich (merge all sources)
12. Decision: Auto vs Inbox (based on confidence)
13. Create Entry or InboxItem
14. File Organization
15. Job Complete
```

**Benefits:**
- 30% faster (skip duplicate AI processing)
- 50% fewer API calls (conditional based on library)
- Better AI accuracy (APIs inform classification)
- Clearer data lineage (source tracking)

---

## Summary

### What Gets Stored After Import

| Data | Source | Stored In | Displayed Where |
|------|--------|-----------|-----------------|
| Title | AI Task 1 | Entry.title | Everywhere |
| Library | AI Task 2 or User | Entry.library_id | Entry list, detail |
| Subfolder | AI Task 3 | Entry.subfolder | Entry detail, breadcrumb |
| Description | AI Task 4 or APIs | Entry.description | Entry detail |
| Duration | VHS or Probe | Entry.duration, EntryFile.duration | Entry detail, list |
| Thumbnail | VHS download | EntryFile (type=thumbnail) | Entry list, detail |
| Platform | VHS | Entry.platform | Entry detail |
| Uploader | VHS | Entry.uploader | Entry detail |
| Original URL | User input | Entry.original_url | Entry detail |
| File path | VHS + organization | EntryFile.file_path | Entry detail (streaming) |
| File hash | Computed | EntryFile.content_hash | Internal (duplicate check) |
| Format | Probe | EntryFile.format | Entry detail (files list) |
| Size | Probe | EntryFile.size | Entry detail (files list) |
| Bitrate | Probe | EntryFile.bitrate | Entry detail (files list) |
| Resolution | Probe | EntryFile.resolution | Entry detail (files list) |
| Tags | AI Task 3/4 | EntryAutoTag | Entry detail, filters |
| Properties | AI Task 3/4 + APIs | EntryProperty | Entry detail (grid) |
| Confidence | AI Tasks | InboxItem.confidence (if manual) | Inbox only |
| Job ID | Job creation | Entry.import_job_id | Internal (audit) |

### What's NOT Stored (Lost Data)
- **VHS raw metadata** (tags, categories, chapters, comments) - only parsed fields kept
- **Probe full stream data** - only summary stored
- **API full responses** - only used fields extracted
- **AI reasoning** - only in Inbox, lost after approval
- **AI confidence per field** - only overall confidence kept

### Recommendations for Complete Data Capture
1. Add `Entry.raw_import_metadata` JSON field to store full VHS output
2. Add `EntryProperty.confidence` field to track per-property AI confidence
3. Add `EntryProperty.reasoning` field to store AI reasoning
4. Keep Job.metadata even after completion for audit trail

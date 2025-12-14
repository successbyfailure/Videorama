# Videorama v2.0 - Implementation Plan
**Last Updated:** 2025-12-14
**Status:** Awaiting User Approval

---

## 📋 Overview

This plan details the implementation of missing features from v1.0 into the modern v2.0 architecture, respecting the existing import flow, job system, and database schema.

### Current v2.0 Architecture (Respected)
- ✅ FastAPI backend with async support
- ✅ PostgreSQL database (not SQLite)
- ✅ React + TypeScript frontend
- ✅ Job system with progress tracking via database
- ✅ Import flow: URL → VHS probe → LLM classification → Auto-import or Inbox
- ✅ Library-based organization with templates
- ✅ Nginx reverse proxy for production

---

## 🎯 Implementation Phases

### **FASE 1 - CORE FUNCTIONALITY** ⭐⭐⭐ (High Priority)

#### 1.1 Enhanced Import Manager UI (2-3 days)
**Goal:** Modern UI for importing with VHS integration

**Backend:**
- [x] Existing: `/api/v1/import/url` endpoint
- [ ] **NEW:** `/api/v1/import/probe` - Probe URL without importing (for preview)
  - Calls VHS `/api/probe`
  - Returns: title, duration, thumbnail, available formats, uploader, platform
  - Does NOT download or create entry

- [ ] **NEW:** `/api/v1/import/search` - Search videos via VHS
  - Endpoint: `POST /api/v1/import/search`
  - Params: `query`, `source` (youtube, soundcloud, bandcamp, all)
  - Returns: List of search results from VHS
  - Format: `[{url, title, duration, thumbnail, platform}]`

- [ ] **ENHANCE:** `/api/v1/import/url` - Add support for format selection
  - Add `format` parameter (video_max, video_1080, audio_max, etc.)
  - Currently hardcoded in `_download_file()`

**Frontend:**
- [ ] **NEW PAGE:** `/import` - Import Manager
  - **Tab 1: URL Import**
    - Input field for URL
    - [Preview Mode] Button to probe URL before importing
      - Shows: thumbnail, title, duration, platform
      - Format selector dropdown (if preview mode)
      - Library selector
      - "Import" button (calls `/import/url`)
    - [Auto Mode] Toggle for auto-import vs manual
    - Real-time progress via job polling

  - **Tab 2: Search**
    - Search input
    - Source filter dropdown (YouTube, SoundCloud, Bandcamp, All)
    - Search results grid with thumbnails
    - Each result has "Import" button
    - Import options modal (library, format, auto-mode)

- [ ] **Integration:** Link from main navigation menu

**VHS Service Updates:**
- [ ] Add `search()` method to `VHSService`
- [ ] Add `probe()` method (already exists, verify it's correct)
- [ ] Document supported search sources

**Files to Create/Modify:**
```
backend/app/api/v1/import_endpoints.py          # Add probe and search endpoints
backend/app/services/vhs_service.py             # Add search method
frontend/src/pages/Import/ImportPage.tsx        # New page
frontend/src/pages/Import/URLImport.tsx         # URL tab component
frontend/src/pages/Import/SearchImport.tsx      # Search tab component
frontend/src/components/Import/PreviewCard.tsx  # Preview component
frontend/src/components/Import/FormatSelector.tsx
```

---

#### 1.2 Streaming with Range Requests (1-2 days)
**Goal:** Enable video seek (scrubbing) in player

**Backend:**
- [ ] **NEW:** `/api/v1/entries/{uuid}/stream` endpoint
  - Serves entry file with HTTP Range request support
  - Headers: `Accept-Ranges: bytes`, `Content-Range`, `Content-Length`
  - Status: 206 Partial Content for range requests
  - Falls back to 200 OK for full file

- [ ] **Implementation:**
  ```python
  from fastapi.responses import StreamingResponse, FileResponse
  from starlette.requests import Request

  @router.get("/entries/{uuid}/stream")
  async def stream_entry(uuid: str, request: Request):
      # Get entry file path
      # Parse Range header
      # Return partial content with proper headers
  ```

**Frontend:**
- [ ] **UPDATE:** Video player to use `/stream` endpoint
- [ ] **UPDATE:** `VideoPlayer.tsx` to handle streaming URLs
- [ ] Test seek functionality

**Files to Create/Modify:**
```
backend/app/api/v1/entry_endpoints.py           # Add stream endpoint
backend/app/utils/streaming.py                  # Range request utilities (NEW)
frontend/src/components/VideoPlayer.tsx         # Use stream endpoint
```

---

#### 1.3 Download Statistics & Analytics (1-2 days)
**Goal:** Track all media downloads for analytics

**Database Schema:**
- [ ] **NEW TABLE:** `download_events`
  ```sql
  CREATE TABLE download_events (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      entry_uuid UUID NOT NULL REFERENCES entries(uuid) ON DELETE CASCADE,
      format VARCHAR(50),                    -- 'stream', 'download', 'original'
      bytes_transferred BIGINT,
      ip_address VARCHAR(50),
      user_agent TEXT,
      completed BOOLEAN DEFAULT false,
      created_at TIMESTAMP DEFAULT NOW(),
      completed_at TIMESTAMP,

      INDEX idx_entry_uuid (entry_uuid),
      INDEX idx_created_at (created_at)
  );
  ```

**Backend:**
- [ ] **NEW:** Middleware/decorator to track downloads
  ```python
  async def track_download(entry_uuid, format, request):
      # Create download_event
      # Update bytes_transferred as download progresses
      # Set completed=true when done
  ```

- [ ] **NEW:** `/api/v1/stats/downloads` endpoint
  - Query params: `entry_uuid`, `start_date`, `end_date`, `format`
  - Returns: Download statistics
  - Aggregations: total_downloads, total_bytes, by_format, by_entry

- [ ] **ENHANCE:** Stream and download endpoints to use tracking

**Frontend:**
- [ ] **NEW TAB** in Stats page: "Download Analytics"
  - Total downloads chart (by date)
  - Downloads by format (pie chart)
  - Top downloaded entries table
  - Bandwidth usage over time

**Files to Create/Modify:**
```
backend/alembic/versions/XXX_add_download_events.py  # Migration
backend/app/models/download_event.py                 # Model (NEW)
backend/app/api/v1/stats_endpoints.py                # Add download stats
backend/app/middleware/download_tracker.py           # Tracking middleware (NEW)
frontend/src/pages/Stats/DownloadAnalytics.tsx       # New tab (NEW)
```

---

#### 1.4 Statistics Dashboard (1 day)
**Goal:** Comprehensive statistics page

**Backend:**
- [ ] **NEW:** `/api/v1/stats` endpoint
  ```json
  {
    "total_entries": 1234,
    "total_size_bytes": 123456789,
    "by_library": {
      "videos": {"count": 1000, "size": 100GB},
      "music": {"count": 234, "size": 23GB}
    },
    "by_format": {
      ".mp4": 800,
      ".mkv": 200,
      ".m4a": 234
    },
    "by_platform": {
      "youtube": 500,
      "bandcamp": 200
    },
    "recent_imports": [...],
    "storage_usage": {...}
  }
  ```

**Frontend:**
- [ ] **NEW PAGE:** `/stats` - Statistics Dashboard
  - Overview cards (total entries, total size, libraries)
  - Charts:
    - Entries by library (bar chart)
    - Storage by format (pie chart)
    - Imports over time (line chart)
    - Platform distribution (bar chart)
  - **Tabs:**
    - Overview
    - Download Analytics (from 1.3)
    - Library Details
    - Storage Analysis

**Files to Create/Modify:**
```
backend/app/api/v1/stats_endpoints.py           # Stats API (NEW)
frontend/src/pages/Stats/StatsPage.tsx          # Main stats page (NEW)
frontend/src/pages/Stats/Overview.tsx           # Overview tab (NEW)
frontend/src/pages/Stats/StorageAnalysis.tsx    # Storage tab (NEW)
```

---

#### 1.5 Playlists Implementation (2 days)
**Goal:** Complete playlist functionality (static & dynamic)

**Current State:**
- ✅ Database model exists (`Playlist`)
- ❌ No API endpoints
- ❌ No UI

**Backend:**
- [ ] **NEW:** Playlist CRUD endpoints
  ```
  GET    /api/v1/playlists                  # List all
  POST   /api/v1/playlists                  # Create
  GET    /api/v1/playlists/{id}             # Get one
  PUT    /api/v1/playlists/{id}             # Update
  DELETE /api/v1/playlists/{id}             # Delete
  GET    /api/v1/playlists/{id}/entries     # Get entries
  POST   /api/v1/playlists/{id}/entries     # Add entries (static)
  DELETE /api/v1/playlists/{id}/entries/{entry_uuid}  # Remove
  ```

- [ ] **Playlist Types:**
  - **Static:** Manual selection of entries (many-to-many relationship)
  - **Dynamic:** Query-based (stored as JSON config)
    ```json
    {
      "type": "dynamic",
      "query": {
        "library_id": "videos",
        "tags": ["music", "live"],
        "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
      }
    }
    ```

**Database Schema:**
- [ ] **NEW TABLE:** `playlist_entries` (for static playlists)
  ```sql
  CREATE TABLE playlist_entries (
      playlist_id UUID REFERENCES playlists(id) ON DELETE CASCADE,
      entry_uuid UUID REFERENCES entries(uuid) ON DELETE CASCADE,
      position INTEGER,
      added_at TIMESTAMP DEFAULT NOW(),

      PRIMARY KEY (playlist_id, entry_uuid),
      INDEX idx_playlist_id (playlist_id),
      INDEX idx_position (position)
  );
  ```

**Frontend:**
- [ ] **NEW PAGE:** `/playlists` - Playlist management
  - List of playlists with type badges (Static/Dynamic)
  - Create playlist modal:
    - Name, description
    - Type selector (Static/Dynamic)
    - If dynamic: Query builder UI
  - Playlist detail view:
    - Entry list
    - Add/remove entries (static)
    - Edit query (dynamic)
    - Play all button

- [ ] **Integration:** Add "Add to Playlist" button on entries
- [ ] **Integration:** Playlist selector in entry detail

**Files to Create/Modify:**
```
backend/alembic/versions/XXX_add_playlist_entries.py
backend/app/models/playlist.py                   # Enhance model
backend/app/api/v1/playlist_endpoints.py         # New endpoints (NEW)
backend/app/services/playlist_service.py         # Playlist logic (NEW)
frontend/src/pages/Playlists/PlaylistsPage.tsx  # NEW
frontend/src/pages/Playlists/PlaylistDetail.tsx # NEW
frontend/src/components/Playlist/CreatePlaylist.tsx
frontend/src/components/Playlist/QueryBuilder.tsx  # For dynamic playlists
```

---

### **FASE 2 - EXTERNAL INTEGRATIONS** ⭐⭐ (Medium Priority)

#### 2.1 Chrome Extension (2-3 days)
**Goal:** Browser extension for one-click video imports

**Extension Structure:**
```
chrome-extension/
├── manifest.json          # Manifest V3
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
├── popup/
│   ├── popup.html
│   ├── popup.js
│   └── popup.css
├── options/
│   ├── options.html
│   └── options.js
├── content/
│   └── content.js         # Video detection
└── background/
    └── service-worker.js  # Background tasks
```

**Features:**
- **Auto-detection:** Detect videos on supported platforms
  - YouTube, Vimeo, Dailymotion
  - Twitter/X, Reddit, TikTok
  - Instagram, Facebook
  - Generic HTML5 `<video>` elements

- **Popup UI:**
  - Current page URL display
  - Detected video indicator
  - Library selector
  - Format selector
  - "Send to Videorama" button
  - Status indicator (sending, success, error)

- **Options Page:**
  - Videorama server URL configuration
  - Default library selection
  - Default format
  - Auto-download toggle
  - API key (for future auth)

- **Communication:**
  - Uses `/api/v1/import/url` endpoint
  - Shows job progress via polling
  - Browser notifications on completion

**Backend:**
- [ ] **ENHANCE:** Add CORS headers for extension origin
- [ ] **Optional:** `/api/v1/import/validate` to test connection

**Files to Create:**
```
chrome-extension/manifest.json
chrome-extension/popup/popup.html
chrome-extension/popup/popup.js
chrome-extension/options/options.html
chrome-extension/options/options.js
chrome-extension/content/content.js
chrome-extension/background/service-worker.js
chrome-extension/README.md                      # Installation instructions
```

---

#### 2.2 Telegram Bot (3-4 days)
**Goal:** Full-featured Telegram bot for remote management

**Features:**
- Send URLs to import
- Upload files directly (audio/video)
- Interactive menus (inline keyboards)
- Access control (admin/user roles)
- Progress notifications
- Search and browse library

**Database Schema:**
- [ ] **NEW TABLES:**
  ```sql
  CREATE TABLE telegram_settings (
      key VARCHAR(100) PRIMARY KEY,
      value TEXT,
      updated_at TIMESTAMP DEFAULT NOW()
  );

  CREATE TABLE telegram_contacts (
      user_id BIGINT PRIMARY KEY,
      username VARCHAR(255),
      first_name VARCHAR(255),
      last_name VARCHAR(255),
      role VARCHAR(20) DEFAULT 'user',   -- 'admin', 'user'
      allowed BOOLEAN DEFAULT true,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
  );

  CREATE TABLE telegram_interactions (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id BIGINT,
      username VARCHAR(255),
      message_type VARCHAR(50),
      content TEXT,
      created_at TIMESTAMP DEFAULT NOW(),

      INDEX idx_user_id (user_id),
      INDEX idx_created_at (created_at)
  );
  ```

**Backend:**
- [ ] **NEW:** Telegram bot service
  ```python
  # backend/app/services/telegram_bot.py
  from telegram import Update, Bot
  from telegram.ext import Application, CommandHandler, MessageHandler

  class TelegramBotService:
      async def start(self):
          # Initialize bot

      async def handle_url(self, update: Update):
          # Import URL via ImportService

      async def handle_file(self, update: Update):
          # Download file, import via ImportService

      async def handle_search(self, update: Update):
          # Search library
  ```

- [ ] **NEW:** Telegram settings endpoints
  ```
  GET  /api/v1/telegram/settings
  PUT  /api/v1/telegram/settings
  GET  /api/v1/telegram/contacts
  POST /api/v1/telegram/contacts         # Add allowed user
  DELETE /api/v1/telegram/contacts/{user_id}
  GET  /api/v1/telegram/interactions     # Recent activity
  ```

**Docker Compose:**
- [ ] **NEW SERVICE:** `telegram-bot`
  ```yaml
  telegram-bot:
    build:
      context: ./backend
    command: python -m app.telegram_bot
    env_file: .env
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    depends_on:
      - backend
      - postgres
  ```

**Commands:**
```
/start      - Initialize bot
/help       - Show help
/add <url>  - Quick add URL
/search     - Search library
/recent     - Show recent imports
/settings   - Bot settings
```

**Files to Create:**
```
backend/alembic/versions/XXX_add_telegram_tables.py
backend/app/services/telegram_bot.py            # Bot service (NEW)
backend/app/api/v1/telegram_endpoints.py        # Settings API (NEW)
backend/app/telegram_bot.py                     # Bot entry point (NEW)
frontend/src/pages/Settings/TelegramSettings.tsx # Settings UI (NEW)
```

---

#### 2.3 MCP Server Integration (1-2 days)
**Goal:** Model Context Protocol server for AI assistants (Claude, etc.)

**Implementation Approach:** Integrated into FastAPI backend

**Backend:**
- [ ] **NEW:** MCP endpoints in FastAPI
  ```python
  # backend/app/api/mcp.py
  from fastapi import APIRouter
  from mcp.server import Server
  from mcp.types import Tool, Resource

  router = APIRouter()
  mcp_server = Server("videorama")

  @mcp_server.tool()
  async def list_recent_entries():
      """List recent library entries"""

  @mcp_server.tool()
  async def get_entry(uuid: str):
      """Get entry details"""

  @mcp_server.tool()
  async def add_from_url(url: str, library: str):
      """Add entry from URL"""

  @mcp_server.tool()
  async def search_entries(query: str):
      """Search library"""

  @router.post("/mcp")
  async def handle_mcp_request(request: dict):
      return await mcp_server.handle_request(request)
  ```

**Configuration:**
- [ ] Add MCP config to `.env.example`
  ```env
  # MCP Server
  MCP_ENABLED=true
  MCP_TIMEOUT=30
  ```

**Documentation:**
- [ ] Create `MCP_SETUP.md` with Claude Desktop integration instructions

**Files to Create:**
```
backend/app/api/mcp.py                          # MCP endpoints (NEW)
backend/app/services/mcp_service.py             # MCP tools (NEW)
MCP_SETUP.md                                    # Documentation (NEW)
```

---

### **FASE 3 - ENHANCEMENTS** ⭐ (Lower Priority)

#### 3.1 VHS Cache Key System (1 day)
**Goal:** Track VHS cache keys for efficient reuse

**Database Schema:**
- [ ] **ADD COLUMN:** `entries.vhs_cache_key VARCHAR(255)`
  ```sql
  ALTER TABLE entries ADD COLUMN vhs_cache_key VARCHAR(255);
  CREATE INDEX idx_vhs_cache_key ON entries(vhs_cache_key);
  ```

**Backend:**
- [ ] **UPDATE:** Import service to save VHS cache key from probe
- [ ] **UPDATE:** VHS service to use cache key when available
  - If entry has cache_key, use VHS cache endpoint
  - Otherwise use no-cache endpoint

**Files to Modify:**
```
backend/alembic/versions/XXX_add_vhs_cache_key.py
backend/app/services/import_service.py
backend/app/services/vhs_service.py
```

---

#### 3.2 Music-Specific Features (2 days)
**Goal:** Enhanced support for music libraries

**Backend:**
- [ ] **NEW:** iTunes API integration
  ```python
  # backend/app/services/external_apis/itunes.py
  async def search_itunes(query: str, media: str = "music"):
      # Search iTunes API
      # Return: artist, album, genre, release_date, artwork
  ```

- [ ] **ENHANCE:** Import flow to use iTunes for music
  - Detect music based on platform (bandcamp, soundcloud) or classification
  - Call iTunes API for enrichment
  - Store in `entry_properties`

- [ ] **ENHANCE:** Entry model to support music properties
  - Current `entry_properties` table already supports this
  - Add common keys: `artist`, `album`, `genre`, `track_number`, `lyrics`

**Frontend:**
- [ ] **UPDATE:** Entry detail to show music-specific fields
- [ ] **UPDATE:** Entry form to include music fields
- [ ] **Optional:** Dedicated music library view

**Files to Create/Modify:**
```
backend/app/services/external_apis/itunes.py    # iTunes integration (NEW)
backend/app/services/import_service.py          # Enhance for music
frontend/src/components/Entry/EntryDetail.tsx   # Show music fields
frontend/src/components/Entry/EntryForm.tsx     # Edit music fields
```

---

## 📅 Estimated Timeline

### Phase 1 - Core (2-3 weeks)
- Week 1: Import Manager UI + Range Streaming
- Week 2: Download Stats + Stats Dashboard
- Week 3: Playlists Implementation

### Phase 2 - Integrations (2-3 weeks)
- Week 4: Chrome Extension
- Week 5: Telegram Bot
- Week 6: MCP Server

### Phase 3 - Enhancements (1 week)
- Week 7: VHS Cache + Music Features

**Total: 5-7 weeks**

---

## 🔧 Technical Decisions Summary

| Feature | Decision | Rationale |
|---------|----------|-----------|
| **Import Flow** | Preview + Auto modes | User requested both options |
| **Search Sources** | All (configurable) | Maximum flexibility |
| **Streaming** | Range requests in Videorama | Videos stored locally, not in VHS |
| **Download Stats** | Full tracking (C) | Complete analytics requested |
| **Playlists** | Static + Dynamic | Both types requested |
| **Progress Tracking** | SSE (Server-Sent Events) | Balance between simplicity and UX |
| **Extension Auth** | No auth (MVP) | Simple start, add later |
| **MCP Deployment** | Integrated in backend | Simpler than separate service |
| **Stats Display** | Multiple tabs | Lots of data, organized view |
| **Migration** | No v1.0 migration | Clean start |

---

## 📦 Deliverables Per Phase

### Phase 1 Deliverables:
1. Import Manager page with URL + Search tabs
2. Video streaming with seek support
3. Download tracking and analytics dashboard
4. Complete statistics page
5. Playlist management (static + dynamic)

### Phase 2 Deliverables:
6. Chrome extension (.zip for Chrome Web Store)
7. Telegram bot with access control
8. MCP server integration + docs

### Phase 3 Deliverables:
9. VHS cache optimization
10. Music-specific enhancements

---

## 🧪 Testing Requirements

### Per Feature:
- [ ] Unit tests for new services
- [ ] Integration tests for API endpoints
- [ ] E2E tests for critical flows
- [ ] Manual testing checklist

### Critical Paths to Test:
1. URL Import (probe → preview → import)
2. Search → Import flow
3. Video streaming with seek
4. Playlist creation and playback
5. Chrome extension → Videorama flow
6. Telegram bot commands

---

## 📝 Documentation Updates Needed

- [ ] Update README.md with new features
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Chrome extension installation guide
- [ ] Telegram bot setup guide
- [ ] MCP integration guide
- [ ] User manual for Import Manager
- [ ] Admin guide for statistics

---

## ⚠️ Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| VHS API changes | High | Version lock VHS, document API |
| Large file streaming performance | Medium | Implement chunking, test with various sizes |
| Telegram bot downtime | Low | Separate service, easy restart |
| Chrome extension review delay | Low | Start submission early, follow guidelines |
| SSE browser compatibility | Medium | Fallback to polling if SSE fails |

---

## 🎯 Success Criteria

### Phase 1:
- [ ] Can import video from URL with preview
- [ ] Can search and import from VHS
- [ ] Video player supports seek (scrubbing)
- [ ] Download statistics visible
- [ ] Can create and play static/dynamic playlists

### Phase 2:
- [ ] Chrome extension detects and imports videos
- [ ] Telegram bot sends URLs and receives notifications
- [ ] Claude can interact with library via MCP

### Phase 3:
- [ ] VHS cache reduces redundant processing
- [ ] Music metadata auto-enriched from iTunes

---

## 🚀 Next Steps

1. **User approval** of this plan
2. **Prioritization** if timeline needs adjustment
3. **Environment setup:**
   - Telegram Bot Token
   - VHS endpoint configuration
   - Testing libraries
4. **Phase 1 kickoff**

---

**Questions for User Before Starting:**

1. ✅ CONFIRMED: No migration from v1.0
2. ✅ CONFIRMED: Streaming from Videorama storage (not VHS)
3. ✅ CONFIRMED: Both preview and auto-import modes
4. ✅ CONFIRMED: All search sources configurable
5. ✅ CONFIRMED: Complete download analytics
6. ✅ CONFIRMED: Playlists (static + dynamic)
7. ✅ CONFIRMED: SSE for job progress
8. ✅ CONFIRMED: No auth for extensions (MVP)
9. ✅ CONFIRMED: MCP integrated in backend
10. ✅ CONFIRMED: Stats with multiple tabs

**Ready to proceed with Phase 1?**

---

**Created:** 2025-12-14
**Purpose:** Complete feature parity with v1.0 in modern v2.0 architecture
**Status:** 🟡 Awaiting Approval

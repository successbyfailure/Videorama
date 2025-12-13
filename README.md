# Videorama v2.0.0

**Modern media library manager with AI-powered organization**

> 📦 **Note**: Version 1.x code has been moved to `/old-code` for reference

---

## 🎯 Overview

Videorama is a self-hosted media library manager that combines powerful organization features with AI-driven classification. Import content from URLs or local filesystems, organize it automatically with configurable templates, and enjoy through an intuitive web interface.

### Key Features

- 📚 **Configurable Libraries** - Create custom libraries (Movies, Music, VideoClips, Private) with individual settings
- 🤖 **AI-Powered Classification** - Automatic categorization using LLM + external APIs (iTunes, TMDb, MusicBrainz)
- 🏷️ **Hierarchical Tags** - Separate automatic and user tags with full hierarchy support
- 📂 **Flexible Organization** - Configurable path templates per library
- 🔄 **Smart Import** - From URLs, local filesystems, or monitored folders
- 🎵 **Audio/Video Duality** - Extract audio from videoclips to music library
- 📋 **Dynamic Playlists** - Create playlists with complex query filters
- 📥 **Inbox System** - Review low-confidence imports before finalizing
- 🔗 **Integrations** - Telegram bot, browser plugin, MCP server

---

## 🏗️ Architecture

### Tech Stack

**Backend:**
- FastAPI (Python 3.11+)
- PostgreSQL 16
- SQLAlchemy 2.0
- Celery + Redis (background tasks)

**Frontend:**
- React 18 + TypeScript
- Vite
- TanStack Query
- Tailwind CSS

### Database Schema

```
libraries          → Media libraries (Movies, Music, etc.)
entries            → Media items (UUID-based)
entry_files        → Physical files (with content hash)
entry_relations    → Relationships between entries
tags               → Tag catalog (hierarchical)
entry_auto_tags    → Automatic tags (import/path/LLM/API)
entry_user_tags    → User-defined tags
entry_properties   → Flexible key-value properties
playlists          → Static and dynamic playlists
playlist_entries   → Entries in static playlists
inbox              → Items pending review
jobs               → Persistent async jobs
reindex_jobs       → Library re-indexation tracking
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) OpenAI-compatible API key for AI features

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/successbyfailure/Videorama.git
   cd Videorama
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

---

## 📖 Usage

### Creating a Library

1. Go to **Settings → Libraries**
2. Click **+ New Library**
3. Configure:
   - Name and icon
   - Storage path(s)
   - Path template (e.g., `{genre}/{artist}/{album}/{title}.{ext}`)
   - Auto-organization settings
   - LLM confidence threshold

### Importing Content

**From URL:**
1. Go to **Import → From URL**
2. Paste URL(s)
3. Select library (or use "Auto" for AI detection)
4. Preview and confirm

**From Filesystem:**
1. Go to **Import → From Disk**
2. Select folder to scan
3. Choose mode:
   - **Auto-organize**: AI classifies and reorganizes files
   - **Copy as-is**: Preserve original structure
   - **Index only**: Leave files in place
4. Review and import

### Managing Tags

- **Auto Tags**: Generated from imports, folder paths, LLM, or external APIs
- **User Tags**: Manually added, have priority over auto tags
- **Hierarchical**: Tags can have parent-child relationships
- **Bulk Operations**: Merge, rename, or clean up tags

### Playlists

**Static Playlists:**
- Manually add/remove entries
- Reorder as needed

**Dynamic Playlists:**
- Define complex filters (tags, platform, date range, etc.)
- Auto-updates with matching entries
- Example: "Rock from YouTube added in last 30 days"

---

## 🔧 Configuration

### Library Path Templates

Templates support variables that are populated by AI classification:

```
Music:      {genre}/{artist}/{album}/{track_number:02d} - {title}.{ext}
Movies:     {genre}/{year}/{title} ({year}).{ext}
VideoClips: {genre}/{artist}/{title}.{ext}
Series:     {title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d}.{ext}
Flat:       {title}.{ext}
```

**Available variables:**
- `{title}`, `{artist}`, `{album}`, `{genre}`, `{year}`, `{track_number}`
- `{director}`, `{season}`, `{episode}`, `{platform}`, `{uploader}`
- `{uuid}`, `{date}`, `{ext}`, and more

### LLM Configuration

Videorama uses OpenAI-compatible APIs for AI features:

```env
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

Compatible with: OpenAI, Azure OpenAI, Anthropic (via proxy), local models (Ollama, LMStudio), etc.

### External APIs

- **TMDb** (movies/series): `TMDB_API_KEY`
- **Spotify** (music): `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`
- iTunes Search API: Built-in, no key required
- MusicBrainz: Built-in, no key required

---

## 🎨 Features in Detail

### AI-Powered Import Flow

1. **Title Extraction**: LLM extracts clean title from filename/metadata
2. **External Enrichment**: Queries iTunes, TMDb, MusicBrainz for metadata
3. **Full Classification**: LLM classifies with all available context
   - Determines library
   - Suggests folder structure
   - Generates tags
   - Fills properties
   - Returns confidence score
4. **Decision**: High confidence → Import | Low confidence → Inbox

### Duplicate Detection

- **Content-based**: SHA256 hash of file content
- **Smart handling**:
  - If video file matches existing → check if audio extracted
  - If audio matches video → create relation without duplicating
  - Full duplicates → sent to inbox for review

### Watch Folders

- Configure folders to monitor per library
- Auto-import new files at defined intervals
- Supports multiple watch folders per library
- Can be enabled/disabled individually

### Re-indexation

Scan library to detect filesystem changes:
- **Moved files**: Update paths based on content hash
- **Deleted files**: Mark as unavailable
- **New files**: Auto-import if configured
- **Corrupted files**: Detect hash mismatches
- **Metadata refresh**: Re-query external APIs (optional)

---

## 🔌 Integrations

### Telegram Bot

Import content directly from Telegram:
```env
TELEGRAM_BOT_TOKEN=your-token
```

Send video/audio URLs to bot → Select library → Auto-import

### Browser Plugin

Chrome extension for one-click imports from any website.

### MCP Server

Claude AI can interact with your Videorama library via MCP protocol.

---

## 📊 API Documentation

Full API documentation available at: http://localhost:8000/docs

Key endpoints:
- `GET /api/v1/libraries` - List libraries
- `POST /api/v1/entries` - Create entry
- `GET /api/v1/entries/{uuid}` - Get entry details
- `POST /api/v1/import/url` - Import from URL
- `POST /api/v1/import/filesystem` - Import from filesystem
- `GET /api/v1/inbox` - List inbox items
- `GET /api/v1/playlists` - List playlists
- `POST /api/v1/playlists/dynamic/evaluate` - Evaluate dynamic playlist

---

## 🛠️ Development

### Project Structure

```
videorama/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── api/v1/          # API endpoints
│   │   ├── services/        # Business logic
│   │   └── utils/           # Utilities
│   ├── alembic/             # Database migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API clients
│   │   └── types/           # TypeScript types
│   └── package.json
├── old-code/                # Legacy v1.x code (archived)
├── docker-compose.yml
└── .env
```

### Running Locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

---

## 📝 Version History

### v2.0.0 (Current)

**Major Rewrite:**
- Complete architecture redesign
- PostgreSQL instead of SQLite
- React frontend instead of Jinja2 templates
- Configurable libraries and path templates
- AI-powered classification with external API enrichment
- Hierarchical tags with auto/user separation
- Dynamic playlists with query builder
- Persistent job system and inbox
- Watch folders and re-indexation
- Audio/video duality for videoclips

### v1.x (Legacy)

Previous version archived in `/old-code` directory. See `/old-code/README.md` for v1.x documentation.

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

See LICENSE file for details.

---

## 🙏 Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [React](https://react.dev/)
- [PostgreSQL](https://www.postgresql.org/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

External APIs:
- [TMDb](https://www.themoviedb.org/)
- [iTunes Search API](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/)
- [MusicBrainz](https://musicbrainz.org/)

---

## 📮 Support

- Issues: [GitHub Issues](https://github.com/successbyfailure/Videorama/issues)
- Discussions: [GitHub Discussions](https://github.com/successbyfailure/Videorama/discussions)

---

**Made with ❤️ for media enthusiasts**

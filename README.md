# Social Media ETL Pipeline

A modular, automated, production-grade **Extract, Transform, Load (ETL)** pipeline built with **Python 3.13**, **Pandas**, **SQLAlchemy 2.0**, and **PostgreSQL 18**. 

This system extracts nested social media data from external REST APIs, cleans and normalizes the payloads into structured DataFrames, and persists them into a PostgreSQL database using an advanced **Hybrid Data Model** (strongly typed relational columns for high-speed indexing and SQL queries paired with a PostgreSQL `JSONB` column for raw, lossless API preservation). It also includes an interactive **1-Page Web Visualizer & Analytics Platform** with 6 dynamic charts, a live pipeline simulation sandbox, and a raw payload inspector.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Source Anatomy](#data-source-anatomy)
3. [Complete Tech Stack & Libraries Used](#complete-tech-stack--libraries-used)
4. [System Prerequisites & Requirements](#system-prerequisites--requirements)
5. [End-to-End ETL Process Breakdown](#end-to-end-etl-process-breakdown)
6. [Why a Hybrid Data Model? (Relational + JSONB)](#why-a-hybrid-data-model-relational--jsonb)
7. [Database Schema Reference](#database-schema-reference)
8. [Interactive Web Visualizer & Dashboard](#interactive-web-visualizer--dashboard)
9. [Step-by-Step Installation & Setup](#step-by-step-installation--setup)
10. [Pipeline Execution Guide](#pipeline-execution-guide)
11. [DBeaver GUI Connection Guide](#dbeaver-gui-connection-guide)
12. [Project File Inventory](#project-file-inventory)
13. [Resilience & Error Handling Strategy](#resilience--error-handling-strategy)

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph S1 ["1. EXTERNAL DATA SOURCE"]
        API["Dev.to Public REST API<br/>(https://dev.to/api/articles)"]
    end

    subgraph S2 ["2. EXTRACT STAGE (extract/client.py)"]
        CLIENT["fetch_posts(tag, per_page)"]
        HTTP_CALL["requests.get(url, params, headers)"]
        STATUS_CHK["response.raise_for_status()<br/>Validate HTTP 200 OK"]
        RAW_JSON["List of Raw Python Dictionaries<br/>(Nested JSON payloads)"]

        API -->|HTTP GET Request| CLIENT
        CLIENT --> HTTP_CALL
        HTTP_CALL --> STATUS_CHK
        STATUS_CHK --> RAW_JSON
    end

    subgraph S3 ["3. TRANSFORM STAGE (transform/cleaner.py)"]
        CLEANER["clean_posts(raw_posts)"]
        ISO_PARSE["parse_iso_datetime()<br/>Convert '2026-09-09T...Z' to UTC Datetime"]
        FLATTEN["Flatten & Validate Fields<br/>Extract: user.name -> author<br/>Extract: reactions -> score"]
        BUNDLE["Bundle Full Raw Payload<br/>raw_data = post (JSON)"]
        PANDAS_DF["Typed Pandas DataFrame<br/>(Shape: N rows x 10 cols)"]

        RAW_JSON --> CLEANER
        CLEANER --> ISO_PARSE
        ISO_PARSE --> FLATTEN
        FLATTEN --> BUNDLE
        BUNDLE --> PANDAS_DF
    end

    subgraph S4 ["4. LOAD & UPSERT STAGE (load/db.py)"]
        ENGINE["SQLAlchemy 2.0 Engine<br/>Connection Pool (psycopg v3)"]
        DDL["create_tables()<br/>Auto-create social_posts Table"]
        UPSERT["PostgreSQL ON CONFLICT Upsert<br/>index_elements=['post_id']<br/>DO UPDATE score, comments, title, raw_data"]
        COMMIT["session.commit()<br/>Idempotent Batch Write"]

        PANDAS_DF --> ENGINE
        ENGINE --> DDL
        DDL --> UPSERT
        UPSERT --> COMMIT
    end

    subgraph S5 ["5. POSTGRESQL HYBRID STORAGE (social_posts table)"]
        PG_REL["Relational Columns (B-Tree Indexed)<br/>• id (PK), post_id (UNIQUE)<br/>• title, author, score, num_comments<br/>• post_created_at, inserted_at"]
        PG_JSONB["JSONB Column<br/>• raw_data (Full Untouched API Payload)"]

        COMMIT --> PG_REL
        COMMIT --> PG_JSONB
    end

    subgraph S6 ["6. CONSUMPTION & ANALYTICS"]
        VISUALIZER["Interactive 1-Page Dashboard<br/>(index.html / serve_dashboard.py)"]
        DBEAVER["DBeaver GUI & SQL Analytics"]

        PG_REL --> VISUALIZER
        PG_JSONB --> VISUALIZER
        PG_REL --> DBEAVER
        PG_JSONB --> DBEAVER
```

---

## Data Source Anatomy

### Primary Source: Dev.to REST API
* **Base URL**: `https://dev.to/api/articles`
* **Protocol**: HTTP/1.1 REST over HTTPS
* **Format**: JSON Array of Article Objects
* **Query Parameters**:
  * `tag`: Filters articles by topic keyword (e.g., `python`, `ai`, `webdev`, `datascience`, `devops`).
  * `per_page`: Number of articles per API call (default: `10` or `15`, maximum: `30`).
* **Why Dev.to?**
  1. **Rich Social Media Topology**: Articles include nested authors, avatars, public reaction counts (likes/unicorns), comment threads, tags, and reading times.
  2. **High-Frequency Real-Time Feed**: New developer articles and discussions are published continuously worldwide.
  3. **Open & Reliable**: Supports rate-limited public REST requests without requiring complex OAuth tokens, making it optimal for automated ETL demonstrations.
  4. **Modular Architecture**: The extraction layer (`extract/client.py`) is decoupled so other providers (e.g., Reddit, Bluesky, YouTube) can be plugged in using the exact same downstream Transform & Load schema.

### Sample Ingested Raw JSON Payload
```json
{
  "id": 4611122,
  "title": "Why Your LangGraph ToolNode Tests Are Failing (And How to Fix Them)",
  "description": "A deep dive into unit testing LangGraph custom nodes with pytest...",
  "published_at": "2026-09-09T04:39:00Z",
  "public_reactions_count": 45,
  "comments_count": 7,
  "reading_time_minutes": 5,
  "tag_list": ["python", "ai", "testing"],
  "tags": "python, ai, testing",
  "user": {
    "name": "Peyton Green",
    "username": "peytongreen",
    "profile_image_90": "https://media2.dev.to/.../avatar.png",
    "github_username": "peytongreen"
  },
  "url": "https://dev.to/peytongreen/why-your-langgraph-tests-fail"
}
```

---

## Complete Tech Stack & Libraries Used

### Backend & ETL Pipeline

| Package / Library | Pinned Version | Category | Exact Role & Justification |
| :--- | :--- | :--- | :--- |
| **Python** | `3.13.x` | Runtime | Core programming language powering the ETL pipeline. |
| **SQLAlchemy** | `2.0.52` | ORM & Engine | Database abstraction, connection pooling (`pool_pre_ping=True`), declarative models, and PostgreSQL-specific `on_conflict_do_update` upsert compiler. |
| **psycopg** | `3.3.5` | DB Driver | Next-generation PostgreSQL DB-API driver for Python, providing native C/Rust-level performance and automatic `JSONB` serialization/deserialization. |
| **psycopg-binary** | `3.3.5` | DB Driver | Pre-compiled binary distribution of `psycopg` for Windows/Linux. |
| **pandas** | `3.0.5` | Data Processing | Vectorized DataFrame transformation, field mapping, schema validation, and missing value sanitization. |
| **numpy** | `2.5.3` | Math / Arrays | High-performance numerical dependency powering Pandas transformations. |
| **requests** | `2.34.2` | HTTP Client | Performs HTTP GET calls to social media APIs with query parameters, custom User-Agent headers, and timeout handling. |
| **urllib3** | `2.7.0` | HTTP Engine | Underlying HTTP connection pooling and keep-alive socket manager used by Requests. |
| **certifi** | `2026.7.22` | Security / SSL | Curated Mozilla SSL/TLS root certificates for verified HTTPS requests. |
| **charset-normalizer**| `3.5.1` | Encoding | Automatically detects and decodes UTF-8 and multibyte character encodings in API responses. |
| **idna** | `3.19` | Networking | Internationalized Domain Names in Applications (IDNA) RFC 5891 parser. |
| **tenacity** | `9.1.4` | Resilience | Configures exponential backoff and retry policies for network failures. |
| **python-dotenv** | `1.2.3` | Configuration | Loads database credentials and host configurations from `.env` into `os.environ`. |
| **python-dateutil** | `2.9.0.post0`| Date / Time | Parsing and manipulating complex datetime strings and timezone offsets. |
| **tzdata** | `2026.3` | Timezone DB | IANA timezone database providing accurate UTC daylight saving calculations. |
| **greenlet** | `3.5.5` | Concurrency | Async context manager required by SQLAlchemy's modern ORM engine. |
| **typing_extensions**| `4.16.0` | Type Safety | Backported modern type hints (`| None`, `TypedDict`) for robust static typing. |

### Database & GUI
* **PostgreSQL (v18 Native or v16 Docker)**: Relational and document store with native B-Tree indexing and `JSONB` binary JSON compression.
* **DBeaver Community Edition (v26+)**: Universal database GUI for visual table inspection, schema verification, and direct SQL execution.

### Frontend Web Visualizer & Dashboard
* **HTML5 & Vanilla ES6+ JavaScript**: Lightweight, zero-build single-page application (`index.html`) running directly in any modern browser.
* **Tailwind CSS (via CDN)**: Utility-first CSS framework styled with a cyber-dark aesthetic (`#090e1a` slate background, glassmorphism cards).
* **Chart.js (v4.x via CDN)**: Canvas-based interactive charting engine rendering 6 multi-dimensional graphs with custom dark-mode palettes.
* **Lucide Icons (via CDN)**: Clean, modern SVG icon set for data engineering symbols (layers, database, tables, code).
* **Python Built-in `http.server`**: Powers `serve_dashboard.py` with zero external dependencies to provide live API routes (`/api/status`, `/api/posts`, `/api/run-pipeline`).

---

## System Prerequisites & Requirements

Before running the pipeline, ensure your system meets the following specifications:

1. **Operating System**: Windows 10/11, macOS, or Linux.
2. **Python Environment**: Python `3.10` or higher (tested and verified on **Python 3.13**).
3. **PostgreSQL Database**:
   * **Option A**: Local Windows PostgreSQL 18 service running on port `5432`.
   * **Option B**: Docker Desktop running PostgreSQL 16 on port `5432`.
4. **Port Availability**:
   * `5432`: Default PostgreSQL database port.
   * `8000`: Default local web visualizer server port.
5. **Network Access**: Outbound HTTPS access to `https://dev.to/api/articles`.

---

## End-to-End ETL Process Breakdown

The ETL lifecycle consists of three decoupled stages orchestrated by `pipeline.py`:

```plaintext
1. EXTRACT (client.py) ──> 2. TRANSFORM (cleaner.py) ──> 3. LOAD & UPSERT (db.py) ──> PostgreSQL
```

### Stage 1: Extract (`extract/client.py`)
* **Function**: `fetch_posts(tag: str = "python", per_page: int = 10) -> List[Dict[str, Any]]`
* **Process**:
  1. Constructs the target URL: `https://dev.to/api/articles`.
  2. Injects query parameters: `tag` (topic filter) and `per_page` (batch size).
  3. Sends custom `User-Agent: social-media-etl-pipeline/1.0` headers to ensure transparency and prevent HTTP 429 throttling.
  4. Calls `response.raise_for_status()` to catch HTTP error codes (404, 500, 503).
  5. Decodes and returns the raw JSON payload as a list of Python dictionaries.

### Stage 2: Transform (`transform/cleaner.py`)
* **Functions**: 
  * `parse_iso_datetime(date_str: str) -> datetime | None`
  * `clean_posts(raw_posts: List[Dict[str, Any]]) -> pd.DataFrame`
* **Process**:
  1. **ISO 8601 UTC Normalization**: Dev.to provides UTC timestamps in the format `'2026-09-09T06:37:44Z'`. The parser replaces `'Z'` with `'+00:00'` to allow Python's `datetime.fromisoformat()` to produce true timezone-aware UTC timestamps.
  2. **Relational Flattening**: Extracts deeply nested attributes into flat table columns:
     * `post["user"]["name"]` ➔ `author`
     * `post["public_reactions_count"]` ➔ `score`
     * `post["comments_count"]` ➔ `num_comments`
     * `str(post["id"])` ➔ `post_id`
  3. **Lossless JSONB Preservation**: The **complete untouched raw dictionary** is bundled into the `raw_data` field.
  4. **DataFrame Packaging**: Converts the cleaned records into a typed `pandas.DataFrame` (shape: $N \times 10$).

### Stage 3: Load & Upsert (`load/db.py`)
* **Functions**:
  * `create_tables()`: Automatically executes DDL statements via SQLAlchemy `Base.metadata.create_all()`.
  * `load_posts_to_db(df: pd.DataFrame) -> int`
* **Process**:
  1. Connects to PostgreSQL using SQLAlchemy 2.0 with connection pool health checks (`pool_pre_ping=True`).
  2. Converts the Pandas DataFrame into a dictionary collection.
  3. **Idempotent Upsert (`ON CONFLICT DO UPDATE`)**:
     ```python
     stmt = pg_insert(SocialPost).values(**record)
     upsert_stmt = stmt.on_conflict_do_update(
         index_elements=["post_id"],
         set_={
             "score": stmt.excluded.score,
             "num_comments": stmt.excluded.num_comments,
             "title": stmt.excluded.title,
             "raw_data": stmt.excluded.raw_data,
         },
     )
     session.execute(upsert_stmt)
     ```
  4. **Duplicate Resolution**: If a post ID already exists, it updates the metrics (reactions, comments, latest payload) in-place without throwing duplicate key errors or halting the pipeline.
  5. Commits the session transaction and logs total rows upserted.

---

## Why a Hybrid Data Model? (Relational + JSONB)

Social media APIs frequently modify their data models—adding new fields (e.g., AI disclosure badges, new reaction types, custom tags) or deprecating existing ones. Traditional database models force an uncomfortable trade-off:

| Architecture Pattern | Major Advantage | Fatal Flaw |
| :--- | :--- | :--- |
| **Pure Relational (SQL)** | Fast B-Tree indexing, strict typing, easy SQL reporting. | Schema brittleness; any API change requires running `ALTER TABLE` migrations or losing fields. |
| **Pure Document (NoSQL)** | Flexible schema; absorbs any JSON payload without breaking. | Slow aggregation queries; no foreign keys, joins, or standard SQL BI tool support. |
| **Hybrid Model (This Project)** | **Best of both worlds: Sub-millisecond indexed relational queries + lossless JSONB storage.** | Requires understanding PostgreSQL `JSONB` operators (`->`, `->>`). |

### Concrete SQL Comparison

#### Query 1: High-Speed Relational Filter (Indexed B-Tree)
```sql
-- Microsecond execution speed using standard B-Tree indexes
SELECT post_id, title, author, score, num_comments
FROM social_posts
WHERE score >= 10
ORDER BY score DESC;
```

#### Query 2: Deep Document JSONB Extraction (Without Table Migrations)
```sql
-- Extracts nested user profile images and reading time directly from raw_data
SELECT 
    title,
    raw_data->'user'->>'profile_image_90' AS author_avatar,
    raw_data->>'reading_time_minutes' AS reading_time,
    raw_data->>'ai_disclosure_label' AS ai_disclosure
FROM social_posts
WHERE raw_data->'tag_list' ? 'ai';
```

---

## Database Schema Reference

Table name: `social_posts` (PostgreSQL)

| Column | PostgreSQL Data Type | Nullable | Index / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | **No** | `PRIMARY KEY` (Auto-increment) | Internal surrogate primary key. |
| `platform` | `VARCHAR(50)` | **No** | `INDEX` | Source platform identifier (e.g. `'dev.to'`). |
| `post_id` | `VARCHAR(100)` | **No** | `UNIQUE INDEX` | Platform-assigned ID used for deduplication. |
| `title` | `TEXT` | Yes | None | Full article headline or post title. |
| `author` | `VARCHAR(100)` | Yes | None | Author username or display name. |
| `content` | `TEXT` | Yes | None | Post description or body text snippet. |
| `score` | `INTEGER` | Yes | Default: `0` | Public reactions count (likes, upvotes). |
| `num_comments` | `INTEGER` | Yes | Default: `0` | Total user comments and replies. |
| `url` | `TEXT` | Yes | None | Canonical web link to the live article. |
| `post_created_at` | `TIMESTAMPTZ` | Yes | None | Original publication timestamp in UTC. |
| `inserted_at` | `TIMESTAMPTZ` | Yes | Server default: `NOW()` | Pipeline timestamp when record was saved. |
| `raw_data` | `JSONB` | **No** | None | Full, untouched API response payload. |

---

## Interactive Web Visualizer & Dashboard

The project includes an interactive, single-page web visualizer located at [`index.html`](index.html).

### Features:
1. **Interactive Architecture Flowchart**: Clickable stage cards (**Extract**, **Transform**, **Load**, **Storage**) showing code snippets, schema transformations, and step-by-step animated data packet routing.
2. **Six Dynamic Graphical Representations (Chart.js)**:
   * **Post Engagement Distribution**: Dual-axis bar and line chart comparing Reactions and Comments per post.
   * **Top Content Creators**: Horizontal ranked bar chart of authors by audience engagement volume.
   * **Length vs. Engagement**: Scatter plot correlating reading time (minutes) with audience reactions.
   * **Topic & Tag Clusters**: Doughnut distribution of technologies extracted from the raw JSON payload.
   * **Pipeline Latency Profile**: Time distribution across Network Extract (65%), Pandas Transform (10%), and PostgreSQL Upsert (25%).
   * **Publication Velocity**: Chronological timeline tracking publication velocity and spikes in activity.
3. **Live Pipeline Sandbox**:
   * Tag selector (`python`, `ai`, `webdev`, `javascript`, `datascience`, `devops`).
   * "Run Pipeline" button with live streaming execution logs in an embedded virtual console.
4. **Stored Records Table & Raw JSONB Inspector**:
   * Instant search filter (by title or author).
   * Sorting by ID, Score, Comments, or Author.
   * One-click **"Inspect JSONB"** opening a formatted, syntax-highlighted JSON viewer with a **"Copy JSON"** button.
   * **"Export CSV"** button to download table data instantly.
5. **No Medical/Health Connotations**:
   * Uses tech-centric data engineering icons (`layers`, `database`, `thumbs-up`, `bar-chart-2`, `badge-check`).
   * Explicit SVG favicon embedded in the web tab.

### Launch Options:

#### Option 1: Live PostgreSQL Server Mode (Recommended)
Starts the local Python server bridge connecting directly to PostgreSQL:
```powershell
python serve_dashboard.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

#### Option 2: Standalone File Mode (Zero-Setup)
Double-click `index.html` or open it directly in any web browser:
```powershell
Start-Process index.html
```
Operates immediately with embedded PostgreSQL snapshots and direct browser-based Dev.to API extraction!

---

## Step-by-Step Installation & Setup

### 1. Clone & Enter Directory
```powershell
cd C:\Users\gambo\repos\khin-social-media-etl
```

### 2. Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

> **Note for PowerShell execution policy**: If running scripts is restricted, run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env`)
Verify that `.env` in the root directory contains your PostgreSQL connection details:
```env
DB_USER=etl_user
DB_PASSWORD=secretpassword
DB_HOST=localhost
DB_PORT=5432
DB_NAME=social_data
```

### 5. PostgreSQL Database Setup

#### Option A: Native Windows PostgreSQL (Fastest — No Docker required)
If you have PostgreSQL 18 installed locally:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE USER etl_user WITH PASSWORD 'secretpassword'; CREATE DATABASE social_data OWNER etl_user; GRANT ALL PRIVILEGES ON DATABASE social_data TO etl_user;"
```

#### Option B: Docker PostgreSQL 16
If you prefer running PostgreSQL isolated in Docker:
```powershell
docker run -d `
  --name pg-social-etl `
  -e POSTGRES_USER=etl_user `
  -e POSTGRES_PASSWORD=secretpassword `
  -e POSTGRES_DB=social_data `
  -p 5432:5432 `
  -v pgdata:/var/lib/postgresql/data `
  postgres:16
```

### 6. Verify Database Connection
```powershell
python load/db.py
```
Expected output:
```text
Testing database connection to localhost:5432/social_data as 'etl_user'...
Connection successful! Test query returned: 1
Tables verified / created successfully.
```

---

## Pipeline Execution Guide

Run the end-to-end pipeline from the terminal:
```powershell
python pipeline.py
```

### Programmatic Customization
You can customize the extracted topic tag and batch limit in Python:
```python
from pipeline import run_pipeline

# Extract 20 articles tagged with 'ai'
run_pipeline(tag="ai", limit=20)

# Extract 15 articles tagged with 'webdev'
run_pipeline(tag="webdev", limit=15)
```

Expected output:
```text
============================================================
[START] SOCIAL MEDIA ETL PIPELINE (Tag: 'python', Limit: 15)
============================================================
[EXTRACT] Calling Dev.to API (tag='python', per_page=15)...
[EXTRACT] Successfully retrieved 15 raw posts.
[TRANSFORM] Cleaning and transforming 15 raw posts...
[TRANSFORM] Successfully prepared DataFrame with shape: (15, 10) (rows, columns).
[LOAD] Loading 15 records into PostgreSQL table 'social_posts'...
Tables verified / created successfully.
[LOAD] Successfully upserted 15 posts into database!

============================================================
[SUCCESS] PIPELINE COMPLETED! 15 records processed.
============================================================
```

---

## DBeaver GUI Connection Guide

1. Launch **DBeaver**.
2. Click **New Database Connection** ➔ Select **PostgreSQL**.
3. Fill in the connection settings:
   * **Host**: `localhost`
   * **Port**: `5432`
   * **Database**: `social_data`
   * **Username**: `etl_user`
   * **Password**: `secretpassword`
4. Click **Test Connection ...** to confirm connectivity, then click **Finish**.
5. Navigate to: `social_data` ➔ `Schemas` ➔ `public` ➔ `Tables` ➔ `social_posts`.
6. Open the **Data** tab to visually inspect stored rows, relational columns, and expandable `JSONB` cells.

---

## Project File Inventory

```plaintext
khin-social-media-etl/
├── .venv/                  # Python 3.13 virtual environment with installed packages
├── extract/
│   └── client.py           # API ingestion engine with HTTP status validation and rate limiting
├── transform/
│   └── cleaner.py          # Pandas data cleaning, ISO 8601 UTC parsing, and JSONB packaging
├── load/
│   └── db.py               # SQLAlchemy 2.0 hybrid model, connection pooling, and upsert logic
├── index.html              # Interactive 1-page visualizer & analytics dashboard
├── serve_dashboard.py      # Local web server & PostgreSQL live API bridge
├── build_visualizer.py     # Generator script maintaining the embedded DB snapshot
├── data_sample.json        # Serialized JSON snapshot of PostgreSQL database records
├── .env                    # Local database credentials (ignored by git)
├── .env.example            # Template for environment variables
├── .gitignore              # Ignores .venv/, .env, __pycache__/, *.pyc, *.png
├── pipeline.py             # Main ETL orchestrator script (Extract -> Transform -> Load)
├── README.md               # System documentation and comprehensive architecture guide
└── requirements.txt        # Pinned Python package dependencies
```

---

## Resilience & Error Handling Strategy

1. **Network Interruptions & Rate Limits**:
   * Requests use an explicit 10-second timeout to prevent hanging connections.
   * Custom `User-Agent` headers inform the API gateway of client identity.
   * `response.raise_for_status()` cleanly catches non-200 HTTP responses.
2. **Volatile API Schemas**:
   * Missing or null fields (`description`, `user.name`, `title`) use `.get()` with safe fallback defaults (`"Unknown"`, `0`).
   * The complete unflattened JSON payload is stored in PostgreSQL `JSONB`, ensuring that no nested attributes are permanently lost if schemas change.
3. **Timestamp Inconsistencies**:
   * `parse_iso_datetime()` converts trailing `'Z'` into standard `'+00:00'` UTC offsets and safely returns `None` on unparseable strings without throwing runtime exceptions.
4. **Idempotency & Deduplication**:
   * PostgreSQL unique constraints on `post_id` combined with `ON CONFLICT (post_id) DO UPDATE` prevent duplicate records across multiple runs while updating latest engagement scores in-place.
5. **Database Connection Health**:
   * SQLAlchemy engine utilizes `pool_pre_ping=True` to test database connectivity before issuing transactions, automatically reconnecting dropped sockets.

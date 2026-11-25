# NEXORA — AI Daily Social Media Content & Auto-Publishing System
## Comprehensive Architecture & Implementation Report

---

### Executive Summary

The **AI Daily Social Media Content Generation & Facebook Auto-Publishing System** has been fully engineered and seamlessly integrated into the existing **NEXORA Real Estate CRM** platform as an independent module: **AI Marketing Studio** (`/marketing` / `/ai-marketing-studio`).

The system generates exactly **ONE marketing post and ONE high-aesthetic branded image per day** focused on **NEXORA Smart Replies**, 24/7 business automation, and multi-channel customer communications, utilizing cost-efficient external APIs with free-tier capabilities (Google Gemini API for text, Cloudflare Workers AI with FLUX.1 Schnell for images, and Meta Graph API for Facebook publishing), while maintaining 100% data integrity, strict role-based access control (RBAC), multi-tenancy, and zero regressions on existing CRM & Smart Replies functionality.

All **76 backend tests** passed, and the frontend TypeScript production build completed with **zero errors**.

---

### 1. Files Created and Modified

#### Backend Files Created
| File | Purpose |
|---|---|
| `backend/app/schemas/marketing.py` | Pydantic v2 schemas for marketing posts, settings, generation requests, Facebook validation, and KPI dashboard stats. |
| `backend/app/services/marketing/gemini_content_service.py` | Topic rotation engine, Egyptian Arabic copywriting, and image prompt generator using Google Gemini API (`gemini-1.5-flash`), with offline heuristic fallback. |
| `backend/app/services/marketing/image_providers.py` | Abstract provider interface (`ImageGenerationProvider`), Cloudflare Workers AI REST API integration (`FLUX.1 Schnell`), and procedural NEXORA brand image generator (`MockProceduralImageProvider`). |
| `backend/app/services/marketing/image_branding_service.py` | High-resolution image branding pipeline using Pillow, official NEXORA logo overlay, and programmatic Arabic typography rendering with `arabic_reshaper` and `python-bidi`. |
| `backend/app/services/marketing/facebook_publisher.py` | Direct Meta Graph API integration (v20.0) for connection testing, token validation, and multipart photo post publishing with caption. |
| `backend/app/services/marketing/marketing_service.py` | Central business orchestrator for daily generation, manual approval, duplicate prevention, image regeneration, and immediate Facebook publishing. |
| `backend/app/services/marketing/marketing_scheduler.py` | APScheduler background service operating strictly in `Africa/Cairo` timezone for automated daily generation (7:00 PM) and auto-publishing (8:00 PM). |
| `backend/app/api/v1/marketing.py` | REST API router providing endpoints for stats, posts, settings, manual generation, image regeneration, publishing, and audit logs. |
| `backend/app/assets/brand/nexora_logo.png` | Official high-resolution transparent PNG logo asset with Deep Navy, Neon Cyan, and Electric Blue/Purple gradient. |
| `backend/app/assets/brand/nexora_logo.svg` | Vector SVG version of the official NEXORA brand identity. |
| `backend/app/assets/fonts/` | Bundled Arabic bold fonts (`segoeuib.ttf`, `tahomabd.ttf`) for cross-platform Arabic rendering. |
| `backend/tests/test_marketing_system.py` | Automated test suite covering Gemini text generation, image branding, duplicate prevention, Facebook publisher, APIs, and RBAC authorization. |

#### Backend Files Modified
| File | Modifications |
|---|---|
| `backend/app/models/models.py` | Added enums (`MarketingGenerationStatus`, `MarketingPublishingStatus`, `MarketingLogStatus`) and database models (`MarketingPost`, `MarketingSetting`, `MarketingLog`). |
| `backend/app/core/config.py` | Added configuration settings for Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`), Cloudflare (`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_IMAGE_MODEL`), and Meta Graph API (`FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_ACCESS_TOKEN`, `FACEBOOK_API_VERSION`). |
| `backend/app/api/v1/__init__.py` | Registered `marketing_router` under `/api/v1/marketing`. |
| `backend/app/main.py` | Initialized and started `MarketingScheduler` on FastAPI startup event and stopped on shutdown. |
| `backend/requirements.txt` | Added `pillow`, `arabic-reshaper`, `python-bidi`, and `apscheduler`. |
| `.env.example` | Documented all required environment variables for Gemini, Cloudflare Workers AI, and Meta Graph API. |

#### Frontend Files Created & Modified
| File | Action | Description |
|---|---|---|
| `frontend/src/pages/MarketingStudioPage.tsx` | **Created** | Comprehensive **AI Marketing Studio** dashboard featuring KPI overview cards, posts management, Facebook feed simulation modal, caption editor, settings modal, and audit logs modal. |
| `frontend/src/types/index.ts` | **Modified** | Added TypeScript interfaces for `MarketingPost`, `MarketingSetting`, `MarketingLog`, `MarketingDashboardStats`, and `FacebookConnectionTestResponse`. |
| `frontend/src/components/layout/Sidebar.tsx` | **Modified** | Added **أستوديو التسويق الذكي / AI Marketing Studio** navigation item with `Megaphone` icon, restricted to `SUPER_ADMIN`, `COMPANY_ADMIN`, and `SALES_MANAGER`. |
| `frontend/src/App.tsx` | **Modified** | Added routes for `/marketing` and `/ai-marketing-studio` (redirecting to `/marketing`). |

---

### 2. Database Schema & Migrations

The database models were created in `backend/app/models/models.py` and auto-created in SQLite/PostgreSQL:

#### `marketing_posts` Table
- `id` (INTEGER, Primary Key)
- `company_id` (INTEGER, Foreign Key -> `companies.id` ON DELETE CASCADE, Index)
- `topic` (VARCHAR(255), Not Null)
- `headline` (VARCHAR(255), Not Null)
- `caption` (TEXT, Not Null)
- `image_prompt` (TEXT, Not Null)
- `image_path` (VARCHAR(500), Nullable) — Path to branded image in `/uploads/marketing/`
- `raw_image_path` (VARCHAR(500), Nullable) — Path to unbranded AI image
- `generation_provider` (VARCHAR(50), Default "gemini")
- `generation_model` (VARCHAR(100), Default "gemini-1.5-flash")
- `image_provider` (VARCHAR(50), Default "cloudflare")
- `image_model` (VARCHAR(100), Default "@cf/black-forest-labs/flux-1-schnell")
- `generation_status` (ENUM: `PENDING`, `GENERATING`, `COMPLETED`, `FAILED`)
- `publishing_status` (ENUM: `DRAFT`, `SCHEDULED`, `PUBLISHING`, `PUBLISHED`, `FAILED`)
- `facebook_post_id` (VARCHAR(100), Nullable)
- `facebook_permalink_url` (VARCHAR(500), Nullable)
- `scheduled_at` (DATETIME, Nullable)
- `published_at` (DATETIME, Nullable)
- `post_date` (VARCHAR(10), Not Null, Index) — `YYYY-MM-DD` for strict daily duplicate prevention
- `error_message` (TEXT, Nullable)
- `created_at`, `updated_at` (DATETIME)
- Index on `(company_id, post_date)`

#### `marketing_settings` Table
- `id` (INTEGER, Primary Key)
- `company_id` (INTEGER, Foreign Key -> `companies.id` ON DELETE CASCADE, Unique, Index)
- `auto_generation_enabled` (BOOLEAN, Default True)
- `auto_publishing_enabled` (BOOLEAN, Default False) — *Disabled by default until verified*
- `generation_time` (VARCHAR(10), Default "19:00")
- `publishing_time` (VARCHAR(10), Default "20:00")
- `timezone` (VARCHAR(50), Default "Africa/Cairo")
- `text_provider` (VARCHAR(50), Default "gemini")
- `text_model` (VARCHAR(100), Default "gemini-1.5-flash")
- `image_provider` (VARCHAR(50), Default "cloudflare")
- `image_model` (VARCHAR(100), Default "@cf/black-forest-labs/flux-1-schnell")
- `facebook_page_id` (VARCHAR(100), Nullable)
- `facebook_page_name` (VARCHAR(255), Nullable)
- `facebook_access_token` (TEXT, Nullable)
- `created_at`, `updated_at` (DATETIME)

#### `marketing_logs` Table
- `id` (INTEGER, Primary Key)
- `company_id` (INTEGER, Foreign Key -> `companies.id` ON DELETE CASCADE, Index)
- `post_id` (INTEGER, Foreign Key -> `marketing_posts.id` ON DELETE CASCADE, Nullable, Index)
- `action` (VARCHAR(100), Not Null)
- `status` (ENUM: `SUCCESS`, `ERROR`, `INFO`)
- `error_message` (TEXT, Nullable)
- `details` (JSON, Nullable)
- `created_at` (DATETIME)

---

### 3. NEXORA Image Branding Pipeline & Protection

```
Raw AI Image Generation (Cloudflare Workers AI / FLUX.1 Schnell)
                     │
                     ▼
Resize & Aspect Ratio Standardization (1080x1350, 4:5 Social Media Ratio)
                     │
                     ▼
Deep Navy (#050817) Ambient Gradient Overlays (Top & Bottom Vignettes)
                     │
                     ▼
Official NEXORA Logo Overlay (Preserving exact colors, transparency & aspect ratio)
                     │
                     ▼
Arabic Text Shaping & Bidi Algorithm (arabic_reshaper + bidi.algorithm)
                     │
                     ▼
Programmatic Arabic Headline inside Translucent Glassmorphic Card (Cyan Border)
                     │
                     ▼
Brand Slogan Badge: "ردود ذكية • مبيعات أسرع • على مدار الساعة"
                     │
                     ▼
Save to /uploads/marketing/nexora_marketing_{date}_{id}.png & Verify Validity
```

#### Logo Protection
- The image model is **strictly forbidden** from generating text or logos (enforced via negative prompting and prompt composition).
- The official NEXORA logo (`nexora_logo.png`) is loaded programmatically and placed cleanly at the top-center with exact pixel dimensions and alpha channel preservation.

#### Arabic Text Protection
- Image generation models frequently distort Arabic script.
- The headline and slogans are rendered programmatically using Pillow with `arabic_reshaper` and `python-bidi`, utilizing bundled bold typography (`segoeuib.ttf` / `tahomabd.ttf`), with proper RTL alignment, character shaping, and high-contrast glassmorphic backing.

---

### 4. Marketing Strategy & Tone of Voice

- **Core Focus:** NEXORA Smart Replies, AI WhatsApp automated replies, 24/7 business automation, eliminating slow response times, multi-channel conversations inbox.
- **Copywriting:** Professional, persuasive Egyptian Arabic marketing copy.
- **Tone:** Enterprise-grade, clean, respectful of client intelligence.
- **Rules Enforced:**
  - **No emojis** anywhere in the marketing post copy.
  - Clear, compelling Call to Action (CTA) inviting prospects to schedule a free demo.
  - Slogan placed consistently: `NEXORA — Smart Replies. Smarter Business.`
  - Dynamic topic rotation preventing repetition across recent posts.

---

### 5. Scheduling and Meta Graph API Publishing

1. **Scheduler (`MarketingScheduler`):**
   - Built on `APScheduler` in the `Africa/Cairo` timezone.
   - Runs a non-blocking check every 60 seconds.
   - At `generation_time` (e.g. 7:00 PM Cairo), if `auto_generation_enabled=True` and no post exists today, generates today's post.
   - At `publishing_time` (e.g. 8:00 PM Cairo), if `auto_publishing_enabled=True` and a post is in `SCHEDULED` status, publishes to Facebook.
   - Uses database guards to avoid duplicate executions.
2. **Meta Graph API (`FacebookPublisher`):**
   - Connects directly to `https://graph.facebook.com/v20.0/`.
   - `test_connection`: Verifies Page ID and Page Access Token validity, page name, and permissions (`pages_manage_posts`, `pages_read_engagement`).
   - `publish_photo_post`: Uploads the branded image as multipart form-data to `POST /{page_id}/photos` with the Arabic caption.
   - Saves `facebook_post_id` and `facebook_permalink_url`.
   - Automatic publishing is **disabled by default** until the administrator verifies the connection.

---

### 6. Environment Variables Required

Add these variables to `.env` or the production environment:

```env
# =====================================================================
# AI MARKETING STUDIO & SOCIAL MEDIA AUTO-PUBLISHING
# =====================================================================
# Google Gemini API for daily Arabic copywriting & visual prompts (Free tier supported)
# Get your free key at https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# Cloudflare Workers AI for FLUX.1 Schnell image generation (Free tier: 10,000 neurons/day)
# Get credentials at https://dash.cloudflare.com/
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id_here
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here
CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-1-schnell

# Meta Graph API for Facebook Page Auto-Publishing
# Get Page ID & Page Access Token from Meta Developer Portal (https://developers.facebook.com/)
FACEBOOK_PAGE_ID=your_facebook_page_id_here
FACEBOOK_PAGE_ACCESS_TOKEN=your_facebook_page_access_token_here
FACEBOOK_API_VERSION=v20.0
```

> [!NOTE]
> If any external API credentials are not yet configured, the system operates safely:
> - Content generation falls back to the built-in Egyptian Arabic copywriting engine.
> - Image generation falls back to the procedural NEXORA dark navy/cyan brand generator.
> - Facebook publishing remains in `DRAFT` status until credentials are provided and tested.

---

### 7. Automated Test Results

#### Backend Test Suite
```bash
$env:PYTHONPATH="."
.\backend\venv\Scripts\python.exe -m pytest backend/tests/
```
- **Results:** **76 passed**, 0 failed in 48.73s.
- Includes:
  - `test_gemini_content_service_rotation_and_copy`: PASSED
  - `test_image_provider_and_branding_pipeline`: PASSED
  - `test_marketing_service_daily_workflow_and_duplicate_prevention`: PASSED
  - `test_facebook_publisher_connection_test`: PASSED
  - `test_marketing_api_endpoints_and_rbac`: PASSED
  - All 71 prior CRM, voice, inventory, and RBAC tests: PASSED

#### Frontend Production Build
```bash
npm --prefix frontend run build
```
- **Results:** TypeScript compilation (`tsc`) passed with zero errors, Vite bundled all assets in 31.43s with exit code 0.

---

### 8. Remaining Setup Steps & Operational Instructions

1. **Meta Developer Setup (When ready to connect live Facebook Page):**
   - Create a Meta App at [developers.facebook.com](https://developers.facebook.com/).
   - Add the **Facebook Login for Business** and **Page API** products.
   - Grant `pages_show_list`, `pages_read_engagement`, and `pages_manage_posts` permissions.
   - Generate a Long-Lived Page Access Token for your NEXORA Facebook Page.
   - Enter the `Page ID` and `Page Access Token` into the **AI Marketing Studio Settings** modal and click **فحص الاتصال بـ Meta API**.
   - Once verified, toggle **النشر التلقائي على فيسبوك** to enabled.
2. **Google Gemini Free API Key:**
   - Generate a free API key at [aistudio.google.com](https://aistudio.google.com/) and place it in `.env` as `GEMINI_API_KEY`.
3. **Cloudflare Workers AI Credentials:**
   - In Cloudflare Dashboard, create an API token with `Workers AI: Read` permissions and copy your `Account ID` into `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`.


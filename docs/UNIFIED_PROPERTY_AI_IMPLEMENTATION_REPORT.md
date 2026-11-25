# NEXORA CRM — Unified Locations, Inventory & Conversational AI Integration
## Comprehensive Architecture & Implementation Report

---

### Executive Summary

The NEXORA CRM platform has been successfully upgraded with a single, unified property management workspace: **المناطق والمخزون العقاري** (`/properties-management`). This consolidates the previously separated Locations (`/locations`) and Inventory (`/inventory`) pages into an enterprise-grade hierarchy while preserving 100% of existing property and location data. Furthermore, the CRM Conversational AI Assistant has been integrated with live real estate inventory tools and multi-turn Egyptian Arabic context awareness.

All 71 automated backend tests are passing, and the frontend TypeScript production build completes with zero errors.

---

### 1. Changed and Removed Frontend Files

| File | Action | Description |
|---|---|---|
| `frontend/src/pages/PropertiesManagementPage.tsx` | **Created** | Consolidated unified workspace with dual tabs ("محفظة الوحدات والمخزون" & "الهيكل الجغرافي والمشروعات"), 3-tier hierarchical navigation pills (Governorates → Cities/Areas → Projects & Independent Units), full filtering toolbar, property cards, and 5 interactive modals. |
| `frontend/src/components/layout/Sidebar.tsx` | **Modified** | Replaced separate `/locations` and `/inventory` items with a single unified navigation entry: `المناطق والمخزون العقاري` pointing to `/properties-management` with `Building2` icon. |
| `frontend/src/App.tsx` | **Modified** | Added route for `/properties-management`. Replaced old routes with declarative `<Navigate to="/properties-management" replace />` redirects for both `/inventory` and `/locations`. Cleaned up unused imports. |
| `frontend/src/types/index.ts` | **Modified** | Added `'ARCHIVED'` to `PropertyStatus`. Extended `Property` with `project_id?: number | null`, `title?: string`, `is_archived?: boolean`, and `videos?: PropertyVideo[]`. Defined `PropertyVideo` interface and added `is_archived?: boolean` to `Project`. |
| `frontend/src/pages/InventoryPage.tsx` | **Removed** | Cleanly removed after migrating all inventory, unit management, and offer dispatch functionality to the unified page. |
| `frontend/src/pages/LocationsPage.tsx` | **Removed** | Cleanly removed after migrating all governorates, cities, districts, and project hierarchy management to the unified page. |

---

### 2. The New Unified Route and Redirects

#### New Unified Route
- **Path:** `/properties-management`
- **Component:** `PropertiesManagementPage`
- **Features:**
  - **Header & Stats:** Live unit counts (Available, Reserved, Sold, Total) and quick action buttons (`+ إضافة وحدة عقارية`, `+ إضافة مشروع`, `+ إضافة موقع / منطقة`).
  - **Dual Workspace Modes:**
    1. *محفظة الوحدات والمخزون (Units & Inventory):* Real-time grid of properties with primary image, status badges, specs, video indicators, and action triggers.
    2. *الهيكل الجغرافي والمشروعات (Geographic Hierarchy & Projects):* Governorate, City, District, and Project management with archiving controls.
  - **3-Tier Hierarchy Navigation:** Governorates → Areas/Cities → Projects & Independent Units.
  - **Media Management Modal:** Direct photo upload (with primary image designation) and video pipeline (local file uploads up to 50MB and streaming links from YouTube, Google Drive, or direct URLs).
  - **Full Soft-Delete/Archiving:** Instant toggle for properties and projects between active and archived states.

#### Redirect Mechanism
In `frontend/src/App.tsx`:
```tsx
<Route path="/properties-management" element={<PropertiesManagementPage />} />
{/* Backward-compatible redirects */}
<Route path="/inventory" element={<Navigate to="/properties-management" replace />} />
<Route path="/locations" element={<Navigate to="/properties-management" replace />} />
```
- Uses `replace={true}` so that old bookmarks or in-app links seamlessly transition without polluting browser navigation history or creating dead links.

---

### 3. Backend APIs and AI Tools Added or Reused

#### REST API Endpoints (`backend/app/api/v1/properties.py`)

1. **`GET /properties`**
   - Added query parameters: `governorate_id: Optional[int]`, `city_id: Optional[int]`, `district_id: Optional[int]`, and `include_archived: bool = False`.
   - Excludes archived units by default unless explicitly requested.
   - Serializes `title`, `is_archived`, `project_name` ("عقار مستقل" when independent), `videos`, and `images`.
2. **`POST /properties`**
   - Supports independent properties (`project_id = None` or omitted).
   - Validates duplicate unit numbers within the same project or district.
3. **`PUT /properties/{property_id}`**
   - Updates `title`, `project_id`, `is_archived`, specifications, and location relationships.
4. **`POST /properties/{property_id}/archive`**
   - Toggles property archive state between `ARCHIVED` and `AVAILABLE`.
5. **`POST /projects/{project_id}/archive`**
   - Toggles project archive state between active and archived.
6. **`POST /properties/{property_id}/videos/upload`**
   - Secure multipart video upload with magic-byte validation (MP4 `ftyp`, WebM `\x1a\x45\xdf\xa3`) and 50MB file size limit.
7. **`POST /properties/{property_id}/videos`**
   - Attaches streaming video links (YouTube, Google Drive, direct MP4 URLs).
8. **`GET /properties/{property_id}/videos`**
   - Lists all attached video assets for a property.
9. **`DELETE /properties/{property_id}/videos/{video_id}`**
   - Deletes video record and removes the local file from disk if uploaded.

#### AI Tools Suite (`backend/app/services/ai_tools/inventory_tools.py`)

| Tool Name | Parameters | Purpose |
|---|---|---|
| `search_available_properties` | `governorate`, `city`, `location`, `property_type`, `min_budget`, `max_budget`, `min_bedrooms`, `bathrooms`, `min_area`, `max_area`, `sort_by`, `status` | Direct database query engine executing strict multi-criteria filtering and sorting against live inventory. |
| `get_location_inventory` | `location`, `governorate`, `project_name` | Returns live aggregate statistics: total units, available, reserved, sold, and archived counts. |
| `get_property_details` | `property_id`, `unit_number` | Returns complete unit specifications, price/sqm, payment plans, photos, and video links. |
| `compare_properties` | `property_ids` | Generates a structured comparison matrix analyzing specs, pricing differences, price/sqm, and key value propositions. |
| `get_property_media` | `property_id` | Returns photo galleries and video tour links (differentiating uploaded files vs YouTube/Drive streams). |
| `get_property_recommendations` | `lead_id`, `budget`, `location` | Matches inventory against lead budget and recorded preferences. |
| `search_properties` | *(Alias)* | Backward-compatible alias routing to `search_available_properties`. |

---

### 4. Database Changes and Migrations

#### Pre-Migration Safety
- Created verified backups:
  - `crm_backup_pre_unification_20261110_194356.db`
  - `crm_backup_before_nullable_proj_20261110_201158.db`
- `PRAGMA integrity_check` verified: `ok`.

#### Schema Modifications
1. **`properties` Table:**
   - Modified `project_id INTEGER` to be `NULLABLE` with `ON DELETE SET NULL`. This allows independent properties belonging directly to a governorate, city, or district without requiring a project container.
   - Added `title VARCHAR(255)` for unit headlines (e.g. "شقة ممتازة في التجمع الخامس").
   - Added `is_archived BOOLEAN DEFAULT 0`.
2. **`projects` Table:**
   - Added `is_archived BOOLEAN DEFAULT 0`.
3. **`property_videos` Table (Created):**
   ```sql
   CREATE TABLE property_videos (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
       video_type VARCHAR(50) NOT NULL, -- 'UPLOAD', 'YOUTUBE', 'GOOGLE_DRIVE', 'DIRECT_URL'
       video_url VARCHAR(500) NOT NULL,
       title VARCHAR(255),
       is_primary BOOLEAN DEFAULT 0,
       created_at DATETIME
   );
   CREATE INDEX ix_property_videos_property_id ON property_videos(property_id);
   ```

---

### 5. Conversational Context Preservation across Multi-Turn Egyptian Arabic

The conversational operator (`CRMOperatorService` and `ConversationStateManager`) preserves context across successive turns without losing active criteria.

#### Context Life-Cycle
1. **Filter Extraction (`extract_property_query_filters`):**
   - Inspects Egyptian colloquial queries and extracts:
     - Locations: "التجمع", "زايد", "الشروق", "المعادي", "أكتوبر", etc.
     - Types: "شقة", "فيلا", "تاون هاوس", "بنتهاوس", "دوبلكس", "مكتب", "محل".
     - Budgets: "في حدود 5 مليون", "ميزانية 6 مليون", "أقل من 7 مليون".
     - Rooms: "3 غرف", "أوضتين", "4 نوم".
     - Sizing: "أكبر شوية", "أصغر شوية".
     - Sorting: "وريني الأرخص", "رتبهم بالسعر", "الأعلى سعراً".
2. **Multi-Turn Accumulation:**
   - Modifying a single attribute (e.g., Turn 1: *"عايز شقة في التجمع بـ 6 مليون"* followed by Turn 2: *"خليها 3 غرف"*) retains `location = "التجمع"` and `max_budget = 6000000`, while updating `bedrooms = 3`.
3. **Colloquial Reference Resolution:**
   - **Anaphora ("دي", "الوحدة دي"):** Resolves to the last viewed or single matching unit ID from `last_properties_shown`.
   - **Comparison ("قارن بينهم", "الفرق بين الاتنين"):** Extracts the top 2 IDs from `last_properties_shown` and invokes `compare_properties`.
   - **Media ("عندكم فيديو ليها؟"):** Resolves the target unit and invokes `get_property_media`.
   - **Inventory Tallies ("عندنا كام شقة في التجمع؟"):** Directs to `get_location_inventory` and returns live statistics.
4. **State Expiration Handling:**
   - Whenever an expired session is accessed, `ConversationStateManager` clears stale filters and immediately grants a fresh 30-minute TTL, avoiding deadlocks.

---

### 6. Live Inventory Accuracy Guarantees

- **No AI Hallucinations:** The LLM does not generate property specs, availability, or pricing out of thin air. All data is fetched directly from SQL tables via registered AI tools.
- **Strict Real-Time Status Filtering:** By default, queries apply `status == 'AVAILABLE'` and `is_archived == False`. If a unit is reserved or sold by another agent, it is instantly excluded from available inventory searches.
- **Relational Integrity:** Foreign keys enforce location consistency across governorates, cities, districts, and projects.

---

### 7. RBAC Boundaries (Internal CRM AI vs Public Website Chatbot)

| Dimension | Internal CRM AI Operator | Public Website Chatbot |
|---|---|---|
| **Authentication** | Authenticated session with JWT token. | Public / Anonymous visitor session. |
| **Tenant Isolation** | Scoped strictly to `current_user.company_id`. | Scoped to the public organization ID. |
| **Visible Inventory** | Available, Reserved, Sold, and Archived (if requested). | Strictly `AVAILABLE` and `is_archived = False`. |
| **Sensitive Data** | View internal notes, owner contact info, commission %, and assigned sales agent. | Sensitive fields stripped; only marketing specs, public pricing, and public media are exposed. |
| **Actions** | Create/edit leads, assign agents, create tasks/follow-ups, generate WhatsApp offers, archive records. | Lead capture inquiry only; cannot modify inventory or agent assignments. |

---

### 8. Verification and Test Results

#### 1. Automated Backend Test Suite
```bash
$env:PYTHONPATH="."
.\backend\venv\Scripts\python.exe -m pytest backend/tests/
```
- **Results:** **71 passed**, 0 failed (including `test_unified_properties_ai.py`).
- **Scenarios Verified:**
  - Independent properties creation without projects (`project_id = None`).
  - Unit and project soft-deletion / archiving toggles.
  - Video upload with magic byte verification and external video link attachments.
  - Location inventory aggregation counts.
  - Multi-turn 8-step Egyptian Arabic conversation sequence verifying filter accumulation, sorting, sizing adjustments, media retrieval, comparison, and inventory tallies.

#### 2. Frontend Production Build
```bash
npm --prefix frontend run build
```
- **Results:** TypeScript compilation passed with zero errors (`tsc -b`).
- Vite bundled all assets cleanly into `frontend/dist/`.

---

### 9. How to Test the Unified Page and Conversational AI

#### Testing the Unified Page
1. Start the backend: `uvicorn backend.app.main:app --reload`
2. Start the frontend: `npm --prefix frontend run dev`
3. Navigate to `http://localhost:5173/properties-management` (or access `/inventory` or `/locations` to verify automatic redirect).
4. **Test Geographic Hierarchy:** Click on Governorates, Cities, and Projects pills to filter down the inventory.
5. **Test Independent Property:** Click `+ إضافة وحدة عقارية`, select a City/District, leave "المشروع" empty, and submit.
6. **Test Media Management:** Click the photos/video icon on any card:
   - Upload an MP4 video or paste a YouTube / Google Drive URL.
   - Set primary photos and delete obsolete assets.
7. **Test Archiving:** Click the archive button on a property card; toggle "عرض المؤرشف" in the filter toolbar to verify soft-delete behavior.

#### Testing the Conversational AI
Open the AI Assistant drawer in the CRM and try this sequence in Egyptian Arabic:
1. *"عايز شقة في التجمع بميزانية 6 مليون"* → Verifies budget and location filtering.
2. *"خليها 3 غرف"* → Verifies multi-turn filter preservation (preserves New Cairo & 6M budget while adding 3 bedrooms).
3. *"وريني الأرخص"* → Verifies sorting by price ascending.
4. *"مفيش حاجة أكبر شوية؟"* → Verifies dynamic area/space adjustment.
5. *"عندكم فيديو ليها؟"* → Verifies unit media lookup for the selected property.
6. *"قارن بين الاتنين"* → Verifies side-by-side comparison matrix generation.
7. *"عندنا كام شقة في التجمع؟"* → Verifies real-time live inventory tally.


# UGA Course Scheduler

## Product Vision
AI-powered course planning tool for University of Georgia students. Helps students plan their degree path, choose courses, and understand what to expect before registration.

## Target Users
- UGA undergraduates planning their semester
- Students trying to understand degree requirements
- Students researching courses before registration

## Core Use Cases

### 1. Degree Planning
- Student selects major and goal (fast-track, specialist, well-rounded, flexible)
- System shows all required courses organized by category
- Student sees which courses are offered this semester with open seats

### 2. Course Research
- View course descriptions and prerequisites (from UGA Bulletin)
- See who's teaching each course this semester (instructors)
- Access past syllabi to understand workload, grading, textbooks

### 3. Smart Recommendations (Future)
- AI-powered course suggestions based on goals
- Prerequisite chain analysis
- Optimal course sequencing

---

## Data Inventory (Jan 2026)

| Source | Records | Status |
|--------|---------|--------|
| Courses (schedule PDF) | 6,908 | Complete |
| Sections | 20,143 | Complete |
| Bulletin Courses | 1,607 | Complete (descriptions, prereqs) |
| Programs | 44 | Complete (degree requirements) |
| Professors | 439 | Scraped (profiles, not RMP) |
| Syllabi metadata | 696 | Complete (after dedup) |
| Syllabi content | 443 | Complete (CS: 217, ENG: 225) |
| Documents (RAG) | 443 | Ready for embedding |

## Data Relationships
```
Program → Requirements → Courses
Course → Sections (with instructors, seats)
Course → BulletinCourse (description, prerequisites)
Course → Syllabi (content, instructor)
```

---

## AI Architecture

### Embedding Pipeline
```
Data → embedding_text property → OpenAI text-embedding-3-small → pgvector
```

### Search Flow
```
User Query → Embedding → pgvector cosine similarity → Top K results
```

### RAG (Retrieval Augmented Generation)
```
Query → Search courses + documents → Context → LLM → Response
```

### Current AI Status
- EmbeddingService: Using **Voyage AI** (voyage-3-lite, 512 dimensions)
- pgvector: Ready
- Embeddings generated:
  - Courses: **6,908** ✓
  - Bulletin courses: **1,607** ✓
  - Documents (syllabi): **443** ✓
- Semantic search: **Working** - query/document embedding types configured

### Data Ready for Embedding
1. **Courses** - `embedding_text` = code, title, department, description, prereqs
2. **BulletinCourses** - `embedding_text` = code, title, description, prereqs, outcomes
3. **Programs** - `embedding_text` = degree, name, department, overview, career

### Syllabi → RAG Pipeline (Added)
Methods added to `embedding_service.py`:
1. `import_syllabi_to_documents()` - Imports syllabi content to Document table
2. `embed_documents_batch()` - Generates embeddings for documents without them

Usage after scrape completes:
```python
from src.services.embedding_service import EmbeddingService
svc = EmbeddingService()
svc.import_syllabi_to_documents(embed=False)  # Add to RAG without embedding
svc.embed_documents_batch(source_type='syllabus')  # Add embeddings later
```

---

## Tech Stack
- **Backend**: FastAPI + PostgreSQL + pgvector
- **Frontend**: React + TypeScript + TailwindCSS + React Query
- **Auth**: Clerk
- **Scraping**: Playwright + BeautifulSoup + PyMuPDF
- **AI**: Voyage AI embeddings (voyage-3-lite, 512d)

---

## Key APIs

### Courses
- `GET /courses` - List with filters (subject, instructor, availability)
- `GET /courses/{code}` - Detail with bulletin data

### Programs
- `GET /programs` - List all degree programs
- `GET /programs/{id}` - Requirements
- `GET /programs/{id}/enriched` - Courses + instructors + syllabi

### Syllabi
- `GET /syllabi` - List with filters
- `GET /syllabi/course/{code}` - By course

### Search (not yet functional - needs embeddings)
- `POST /search/semantic` - Vector similarity search

---

## Terminology
- Use **"instructor"** not "professor" (matches course PDF)
- Syllabi are bound to instructors

---

## In Progress

### Syllabus Content Scraper (COMPLETE)
- CS: 217 syllabi with content
- ENG: 225 syllabi with content
- Total: 443 syllabi scraped and imported to Documents table

### Next Steps
1. Wire semantic search into API endpoints
2. Add elective discovery feature for students
3. Improve syllabus search (currently low similarity scores)
4. Consider embedding programs for degree-level search

---

## Files of Interest

### Backend
- `src/services/embedding_service.py` - AI/embedding logic
- `src/services/syllabus_scraper_playwright.py` - PDF scraper with content extraction
- `src/api/main.py` - All API endpoints
- `src/models/database.py` - SQLAlchemy models

### Frontend
- `frontend/src/pages/PlanPage.tsx` - Degree plan view
- `frontend/src/pages/CoursesPage.tsx` - Course catalog
- `frontend/src/components/Onboarding.tsx` - User flow

---

## CLI Commands

```bash
# Scrape syllabi with content (already done for CS/ENG)
python -m src.services.syllabus_scraper_playwright --content CS
python -m src.services.syllabus_scraper_playwright --content ENG

# Generate embeddings (requires OpenAI credits)
python -c "
from src.services.embedding_service import EmbeddingService
svc = EmbeddingService()
svc.embed_courses()  # 6,908 courses
svc.embed_documents_batch()  # 443 syllabi
"

# Run API
uvicorn src.api.main:app --reload

# Run frontend
cd frontend && npm run dev
```

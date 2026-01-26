"""
Embedding service for vector search and RAG.

Provides:
- Text embedding generation (Voyage AI or OpenAI)
- Semantic course search
- Document similarity search
- RAG context retrieval
"""
import logging
from typing import Optional
from datetime import datetime

import voyageai
from openai import OpenAI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.config import settings
from src.models.database import (
    Course, Document, BulletinCourse, Program,
    get_engine, get_session_factory, init_db
)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings and performing vector searches."""

    def __init__(
        self,
        session_factory=None,
    ):
        if session_factory is None:
            engine = get_engine()
            init_db(engine)
            session_factory = get_session_factory(engine)

        self.session_factory = session_factory
        self.provider = settings.embedding_provider

        # Initialize embedding client based on provider
        if self.provider == "voyage":
            if settings.voyage_api_key:
                self.voyage = voyageai.Client(api_key=settings.voyage_api_key)
                self.openai = None
                logger.info("Using Voyage AI for embeddings")
            else:
                self.voyage = None
                self.openai = None
                logger.warning("Voyage API key not set - embedding features disabled")
        else:
            # OpenAI fallback
            if settings.openai_api_key:
                self.openai = OpenAI(api_key=settings.openai_api_key)
                self.voyage = None
                logger.info("Using OpenAI for embeddings")
            else:
                self.openai = None
                self.voyage = None
                logger.warning("OpenAI API key not set - embedding features disabled")

    def _is_ready(self) -> bool:
        """Check if embedding client is initialized."""
        return self.voyage is not None or self.openai is not None

    def generate_embedding(self, text: str, input_type: str = "document") -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed
            input_type: "document" for indexing, "query" for searching (Voyage AI only)

        Returns:
            List of floats representing the embedding vector
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        # Truncate text if too long
        max_chars = 32000  # Voyage supports up to 32K tokens
        if len(text) > max_chars:
            text = text[:max_chars]

        if self.voyage:
            result = self.voyage.embed(
                texts=[text],
                model=settings.embedding_model,
                input_type=input_type,
            )
            return result.embeddings[0]
        else:
            response = self.openai.embeddings.create(
                model=settings.embedding_model,
                input=text,
            )
            return response.data[0].embedding

    def generate_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 128,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (Voyage supports 128)

        Returns:
            List of embedding vectors
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized")

        embeddings = []
        max_chars = 32000

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch = [t[:max_chars] for t in batch]

            if self.voyage:
                result = self.voyage.embed(
                    texts=batch,
                    model=settings.embedding_model,
                    input_type="document",
                )
                embeddings.extend(result.embeddings)
            else:
                response = self.openai.embeddings.create(
                    model=settings.embedding_model,
                    input=batch,
                )
                embeddings.extend([d.embedding for d in response.data])

        return embeddings

    def embed_courses(
        self,
        schedule_id: Optional[int] = None,
        force: bool = False,
    ) -> int:
        """
        Generate embeddings for all courses in a schedule.

        Args:
            schedule_id: Schedule to process (None = current)
            force: Re-embed even if already has embedding

        Returns:
            Number of courses embedded
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        with self.session_factory() as session:
            query = select(Course)

            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)

            if not force:
                query = query.where(Course.embedding.is_(None))

            courses = list(session.execute(query).scalars().all())

            if not courses:
                logger.info("No courses to embed")
                return 0

            logger.info(f"Embedding {len(courses)} courses...")

            # Generate texts for embedding
            texts = [c.embedding_text for c in courses]

            # Generate embeddings in batches
            embeddings = self.generate_embeddings_batch(texts)

            # Update courses with embeddings
            for course, embedding in zip(courses, embeddings):
                course.embedding = embedding

            session.commit()
            logger.info(f"Embedded {len(courses)} courses")

            return len(courses)

    def embed_bulletin_courses(self, force: bool = False) -> int:
        """
        Generate embeddings for bulletin courses (rich descriptions).

        Args:
            force: Re-embed even if already has embedding

        Returns:
            Number of courses embedded
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        with self.session_factory() as session:
            query = select(BulletinCourse)

            if not force:
                query = query.where(BulletinCourse.embedding.is_(None))

            courses = list(session.execute(query).scalars().all())

            if not courses:
                logger.info("No bulletin courses to embed")
                return 0

            logger.info(f"Embedding {len(courses)} bulletin courses...")

            texts = [c.embedding_text for c in courses]
            embeddings = self.generate_embeddings_batch(texts)

            for course, embedding in zip(courses, embeddings):
                course.embedding = embedding

            session.commit()
            logger.info(f"Embedded {len(courses)} bulletin courses")

            return len(courses)

    def embed_programs(self, force: bool = False) -> int:
        """
        Generate embeddings for programs (degrees, minors, certificates).

        Args:
            force: Re-embed even if already has embedding

        Returns:
            Number of programs embedded
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        with self.session_factory() as session:
            query = select(Program)

            if not force:
                query = query.where(Program.embedding.is_(None))

            programs = list(session.execute(query).scalars().all())

            if not programs:
                logger.info("No programs to embed")
                return 0

            logger.info(f"Embedding {len(programs)} programs...")

            texts = [p.embedding_text for p in programs]
            embeddings = self.generate_embeddings_batch(texts)

            for program, embedding in zip(programs, embeddings):
                program.embedding = embedding

            session.commit()
            logger.info(f"Embedded {len(programs)} programs")

            return len(programs)

    def search_bulletin_courses(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[tuple[BulletinCourse, float]]:
        """
        Search bulletin courses using semantic similarity.

        Args:
            query: Natural language search query
            limit: Maximum results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of (BulletinCourse, similarity_score) tuples
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        query_embedding = self.generate_embedding(query, input_type="query")

        with self.session_factory() as session:
            sql = text("""
                SELECT
                    bc.id,
                    1 - (bc.embedding <=> :query_embedding) as similarity
                FROM bulletin_courses bc
                WHERE bc.embedding IS NOT NULL
                AND 1 - (bc.embedding <=> :query_embedding) >= :threshold
                ORDER BY bc.embedding <=> :query_embedding
                LIMIT :limit
            """)

            result = session.execute(
                sql,
                {
                    "query_embedding": str(query_embedding),
                    "threshold": threshold,
                    "limit": limit,
                }
            )

            course_scores = [(row[0], row[1]) for row in result]

            if course_scores:
                course_ids = [cs[0] for cs in course_scores]
                scores_map = {cs[0]: cs[1] for cs in course_scores}

                courses = session.execute(
                    select(BulletinCourse).where(BulletinCourse.id.in_(course_ids))
                ).scalars().all()

                return sorted(
                    [(c, scores_map[c.id]) for c in courses],
                    key=lambda x: x[1],
                    reverse=True
                )

            return []

    def search_courses_semantic(
        self,
        query: str,
        schedule_id: Optional[int] = None,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[Course, float]]:
        """
        Search courses using semantic similarity.

        Args:
            query: Natural language search query
            schedule_id: Schedule to search (None = current)
            limit: Maximum results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of (Course, similarity_score) tuples
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        # Generate query embedding
        query_embedding = self.generate_embedding(query, input_type="query")

        with self.session_factory() as session:
            # Use pgvector cosine similarity search
            # 1 - cosine_distance = cosine_similarity
            sql = text("""
                SELECT
                    c.id,
                    1 - (c.embedding <=> :query_embedding) as similarity
                FROM courses c
                WHERE c.embedding IS NOT NULL
                AND (:schedule_id IS NULL OR c.schedule_id = :schedule_id)
                AND 1 - (c.embedding <=> :query_embedding) >= :threshold
                ORDER BY c.embedding <=> :query_embedding
                LIMIT :limit
            """)

            result = session.execute(
                sql,
                {
                    "query_embedding": str(query_embedding),
                    "schedule_id": schedule_id,
                    "threshold": threshold,
                    "limit": limit,
                }
            )

            course_scores = [(row[0], row[1]) for row in result]

            # Fetch full course objects with sections eagerly loaded
            if course_scores:
                from sqlalchemy.orm import joinedload
                course_ids = [cs[0] for cs in course_scores]
                scores_map = {cs[0]: cs[1] for cs in course_scores}

                courses = session.execute(
                    select(Course)
                    .options(joinedload(Course.sections))
                    .where(Course.id.in_(course_ids))
                ).unique().scalars().all()

                # Sort by score and return
                return sorted(
                    [(c, scores_map[c.id]) for c in courses],
                    key=lambda x: x[1],
                    reverse=True
                )

            return []

    def add_document(
        self,
        title: str,
        content: str,
        source_type: str,
        source_url: Optional[str] = None,
        source_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        embed: bool = True,
    ) -> Document:
        """
        Add a document to the RAG store.

        Args:
            title: Document title
            content: Document content
            source_type: Type of document (e.g., 'bulletin', 'syllabus')
            source_url: Original URL if applicable
            source_id: External ID for deduplication
            metadata: Additional metadata as dict
            embed: Generate embedding immediately

        Returns:
            Created Document object
        """
        import json

        with self.session_factory() as session:
            doc = Document(
                title=title,
                content=content,
                source_type=source_type,
                source_url=source_url,
                source_id=source_id,
                metadata_json=json.dumps(metadata) if metadata else None,
            )

            if embed and self.openai:
                embed_text = f"{title}\n\n{content}"
                doc.embedding = self.generate_embedding(embed_text)

            session.add(doc)
            session.commit()

            return doc

    def search_documents(
        self,
        query: str,
        source_type: Optional[str] = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[Document, float]]:
        """
        Search documents using semantic similarity.

        Args:
            query: Search query
            source_type: Filter by document type
            limit: Maximum results
            threshold: Minimum similarity

        Returns:
            List of (Document, similarity_score) tuples
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        query_embedding = self.generate_embedding(query, input_type="query")

        with self.session_factory() as session:
            sql = text("""
                SELECT
                    d.id,
                    1 - (d.embedding <=> :query_embedding) as similarity
                FROM documents d
                WHERE d.embedding IS NOT NULL
                AND (:source_type IS NULL OR d.source_type = :source_type)
                AND 1 - (d.embedding <=> :query_embedding) >= :threshold
                ORDER BY d.embedding <=> :query_embedding
                LIMIT :limit
            """)

            result = session.execute(
                sql,
                {
                    "query_embedding": str(query_embedding),
                    "source_type": source_type,
                    "threshold": threshold,
                    "limit": limit,
                }
            )

            doc_scores = [(row[0], row[1]) for row in result]

            if doc_scores:
                doc_ids = [ds[0] for ds in doc_scores]
                scores_map = {ds[0]: ds[1] for ds in doc_scores}

                docs = session.execute(
                    select(Document).where(Document.id.in_(doc_ids))
                ).scalars().all()

                return sorted(
                    [(d, scores_map[d.id]) for d in docs],
                    key=lambda x: x[1],
                    reverse=True
                )

            return []

    def get_rag_context(
        self,
        query: str,
        max_courses: int = 5,
        max_documents: int = 3,
        schedule_id: Optional[int] = None,
    ) -> dict:
        """
        Get context for RAG (Retrieval Augmented Generation).

        Retrieves relevant courses and documents for use as context
        in LLM prompts.

        Args:
            query: User's question/query
            max_courses: Maximum courses to include
            max_documents: Maximum documents to include
            schedule_id: Schedule to search

        Returns:
            Dict with 'courses' and 'documents' context
        """
        context = {
            "query": query,
            "courses": [],
            "documents": [],
        }

        if not self._is_ready():
            return context

        seen_codes = set()

        # Search current semester courses (with availability info)
        try:
            course_results = self.search_courses_semantic(
                query, schedule_id=schedule_id, limit=max_courses, threshold=0.5
            )
            for course, score in course_results:
                seen_codes.add(course.course_code)
                # Avoid lazy loading issues - use attributes that are loaded
                try:
                    sections_count = len(course.sections) if course.sections else 0
                except Exception:
                    sections_count = 0
                context["courses"].append({
                    "course_code": course.course_code,
                    "title": course.title,
                    "department": course.department,
                    "description": course.description,
                    "sections": sections_count,
                    "available_seats": getattr(course, 'available_seats', 0) or 0,
                    "similarity": round(score, 3),
                    "in_current_schedule": True,
                })
        except Exception as e:
            logger.error(f"Course search error: {e}")

        # Also search bulletin courses for comprehensive coverage
        try:
            bulletin_results = self.search_bulletin_courses(
                query, limit=max_courses, threshold=0.5
            )
            for course, score in bulletin_results:
                if course.course_code not in seen_codes:
                    seen_codes.add(course.course_code)
                    context["courses"].append({
                        "course_code": course.course_code,
                        "title": course.title,
                        "department": course.subject,  # BulletinCourse uses 'subject'
                        "description": course.description,
                        "prerequisites": course.prerequisites,
                        "sections": 0,
                        "available_seats": 0,
                        "similarity": round(score, 3),
                        "in_current_schedule": False,
                    })
        except Exception as e:
            logger.error(f"Bulletin course search error: {e}")

        # Sort all courses by similarity
        context["courses"] = sorted(
            context["courses"],
            key=lambda x: x["similarity"],
            reverse=True
        )[:max_courses]

        # Search documents
        try:
            doc_results = self.search_documents(query, limit=max_documents, threshold=0.5)
            for doc, score in doc_results:
                context["documents"].append({
                    "title": doc.title,
                    "content": doc.content[:1000],  # Truncate for context
                    "source_type": doc.source_type,
                    "similarity": round(score, 3),
                })
        except Exception as e:
            logger.error(f"Document search error: {e}")

        return context


    def import_syllabi_to_documents(
        self,
        embed: bool = True,
        limit: Optional[int] = None,
    ) -> int:
        """
        Import syllabi with content into the Document RAG store.

        Args:
            embed: Generate embeddings (requires OpenAI quota)
            limit: Max syllabi to import (None = all)

        Returns:
            Number of syllabi imported
        """
        import json
        from sqlalchemy import text

        with self.session_factory() as session:
            # Find syllabi with content not yet in documents
            sql = """
                SELECT s.id, s.course_code, s.semester, s.instructor_name,
                       s.department, s.content, s.file_name
                FROM syllabi s
                WHERE s.content IS NOT NULL
                AND s.content != ''
                AND NOT EXISTS (
                    SELECT 1 FROM documents d
                    WHERE d.source_type = 'syllabus'
                    AND d.source_id = CAST(s.id AS TEXT)
                )
            """
            if limit:
                sql += f" LIMIT {limit}"

            syllabi = session.execute(text(sql)).fetchall()

            if not syllabi:
                logger.info("No new syllabi to import")
                return 0

            logger.info(f"Importing {len(syllabi)} syllabi to documents...")
            imported = 0

            for s in syllabi:
                syl_id, course_code, semester, instructor, dept, content, filename = s

                # Create meaningful title
                title = f"Syllabus: {course_code}"
                if instructor:
                    title += f" - {instructor}"
                if semester:
                    title += f" ({semester})"

                metadata = {
                    "course_code": course_code,
                    "semester": semester,
                    "instructor": instructor,
                    "department": dept,
                    "file_name": filename,
                }

                doc = Document(
                    title=title,
                    content=content,
                    source_type="syllabus",
                    source_id=str(syl_id),
                    metadata_json=json.dumps(metadata),
                )

                # Generate embedding if requested and possible
                if embed and self.openai:
                    try:
                        embed_text = f"{title}\n\n{content[:30000]}"  # Limit content size
                        doc.embedding = self.generate_embedding(embed_text)
                    except Exception as e:
                        logger.warning(f"Failed to embed syllabus {syl_id}: {e}")
                        # Continue without embedding

                session.add(doc)
                imported += 1

                # Commit in batches to avoid memory issues
                if imported % 50 == 0:
                    session.commit()
                    logger.info(f"  Imported {imported}/{len(syllabi)}...")

            session.commit()
            logger.info(f"Imported {imported} syllabi to documents")
            return imported

    def embed_documents_batch(
        self,
        source_type: Optional[str] = None,
        batch_size: int = 10,
    ) -> int:
        """
        Generate embeddings for documents that don't have them.

        Args:
            source_type: Filter by document type (None = all)
            batch_size: Documents per API call

        Returns:
            Number of documents embedded
        """
        if not self._is_ready():
            raise RuntimeError("Embedding client not initialized - check API keys")

        with self.session_factory() as session:
            query = select(Document).where(Document.embedding.is_(None))
            if source_type:
                query = query.where(Document.source_type == source_type)

            docs = list(session.execute(query).scalars().all())

            if not docs:
                logger.info("No documents to embed")
                return 0

            logger.info(f"Embedding {len(docs)} documents...")
            embedded = 0

            for i in range(0, len(docs), batch_size):
                batch = docs[i:i + batch_size]
                texts = [f"{d.title}\n\n{d.content[:30000]}" for d in batch]

                try:
                    embeddings = self.generate_embeddings_batch(texts, batch_size=batch_size)
                    for doc, emb in zip(batch, embeddings):
                        doc.embedding = emb
                        embedded += 1
                    session.commit()
                    logger.info(f"  Embedded {embedded}/{len(docs)}...")
                except Exception as e:
                    logger.error(f"Batch embedding failed: {e}")
                    break

            logger.info(f"Embedded {embedded} documents")
            return embedded


def create_embedding_service() -> EmbeddingService:
    """Create an EmbeddingService instance."""
    return EmbeddingService()

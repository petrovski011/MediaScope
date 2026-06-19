from sqlalchemy import (
    Column, BigInteger, Integer, String, Boolean, Text,
    DateTime, ARRAY, CHAR, ForeignKey, JSON
)
from sqlalchemy.sql import func

from database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(BigInteger, primary_key=True)
    source_id = Column(String(20), ForeignKey("sources.source_id"), nullable=False)
    url = Column(Text, nullable=False)
    url_hash = Column(CHAR(64), nullable=False, unique=True)
    content_hash = Column(CHAR(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)

    title = Column(Text, nullable=False)
    subtitle = Column(Text)
    text_content = Column(Text)
    text_raw = Column(Text)
    word_count = Column(Integer)

    author = Column(String(500))
    published_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    category = Column(String(200))
    tags = Column(ARRAY(Text))
    image_url = Column(Text)
    image_caption = Column(Text)
    comment_count = Column(Integer)

    scraped_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    scraper_version = Column(String(20))

    has_paywall = Column(Boolean, nullable=False, default=False)
    is_live_blog = Column(Boolean, nullable=False, default=False)
    language = Column(CHAR(2), nullable=False, default="sr")
    script = Column(CHAR(4), nullable=False, default="Latn")

    schema_data = Column(JSON)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ArticleVersion(Base):
    __tablename__ = "article_versions"

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    subtitle = Column(Text)
    text_content = Column(Text)
    text_raw = Column(Text)
    content_hash = Column(CHAR(64), nullable=False)
    changed_fields = Column(ARRAY(Text))
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id = Column(BigInteger, primary_key=True)
    source_id = Column(String(20), ForeignKey("sources.source_id"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(20))
    articles_found = Column(Integer, default=0)
    articles_new = Column(Integer, default=0)
    articles_updated = Column(Integer, default=0)
    articles_skipped = Column(Integer, default=0)
    error_type = Column(String(50))
    error_message = Column(Text)
    consecutive_failures = Column(Integer, default=0)
    duration_ms = Column(Integer)


class PipelineBatch(Base):
    __tablename__ = "pipeline_batches"

    id = Column(BigInteger, primary_key=True)
    batch_id = Column(Text, nullable=False, unique=True)
    batch_type = Column(String(20), nullable=False, default="nightly")
    batch_date = Column(String(20))
    status = Column(String(20), nullable=False, default="submitted")
    article_count = Column(Integer, default=0)
    articles_saved = Column(Integer, default=0)
    articles_failed = Column(Integer, default=0)
    submitted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

from sqlalchemy import (
    Column, BigInteger, Integer, String, Boolean, Text,
    DateTime, Date, ARRAY, Float, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from database import Base

# pgvector je instaliran u Docker image-u; lokalno moze nedostajati.
# Fallback na UserDefinedType da modul ne pukne van kontejnera.
try:
    from pgvector.sqlalchemy import Vector as _Vector

    def _embedding_col(dim: int):
        return Column(_Vector(dim))
except ImportError:  # pragma: no cover
    from sqlalchemy.types import UserDefinedType

    class _Vector(UserDefinedType):  # type: ignore
        def __init__(self, dim):
            self.dim = dim

        def get_col_spec(self, **kw):
            return f"vector({self.dim})"

    def _embedding_col(dim: int):
        return Column(_Vector(dim))


class ArticleAnalysis(Base):
    __tablename__ = "article_analysis"

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False, unique=True)

    topics = Column(ARRAY(Text))
    primary_topic = Column(String(200))
    topic_confidence = Column(Float)

    political_score = Column(Float)
    value_score = Column(Float)
    sensationalism = Column(Float)

    sentiment = Column(String(20))
    sentiment_score = Column(Float)

    model_used = Column(String(50))
    model_version = Column(String(20))
    analysis_version = Column(String(20))
    analyzed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    tokens_used = Column(Integer)

    topic_explanation = Column(Text)
    political_explanation = Column(Text)
    value_explanation = Column(Text)

    calibration_applied = Column(Boolean, default=False)
    calibration_notes = Column(Text)

    # Meta-framing: populisticki 'narod vs elite' obrazac (Faza 10)
    populist_framing = Column(Boolean, default=False)
    populist_confidence = Column(Float)

    # Propaganda detekcija (Sprint 4)
    propaganda_techniques = Column(JSONB, nullable=True)
    propaganda_confidence = Column(Float, nullable=True)
    propaganda_targets = Column(JSONB, nullable=True)
    analysis_confidence = Column(Float, nullable=True)


class Entity(Base):
    __tablename__ = "entities"

    id = Column(BigInteger, primary_key=True)
    name = Column(String(500), nullable=False)
    name_variants = Column(ARRAY(Text))
    entity_type = Column(String(20), nullable=False)  # person, organization, location
    is_political_actor = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("name", "entity_type"),)


class ArticleEntity(Base):
    __tablename__ = "article_entities"

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    entity_id = Column(BigInteger, ForeignKey("entities.id"), nullable=False)
    mention_count = Column(Integer, nullable=False, default=1)
    is_quoted = Column(Boolean, default=False)
    is_subject = Column(Boolean, default=False)
    context_snippet = Column(Text)
    sentiment = Column(Float, nullable=True)  # sentiment pominjanja akteru (-1 neg, 0 neutral, +1 poz)

    __table_args__ = (UniqueConstraint("article_id", "entity_id"),)


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), nullable=False, unique=True)  # npr. PROTEST, KOSOVO
    label_sr = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FramingType(Base):
    __tablename__ = "framing_types"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"))  # NULL = globalni framing
    description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_validated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FramingTypeProposal(Base):
    """AI predlog novog framing tipa — staging dok ga istrazivac ne validira."""
    __tablename__ = "framing_type_proposals"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"))
    description = Column(Text)
    supporting_text = Column(Text)
    article_id = Column(BigInteger, ForeignKey("articles.id"))
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    occurrences = Column(Integer, default=1)
    article_ids = Column(postgresql.ARRAY(BigInteger), nullable=False, server_default="{}")
    embedding = _embedding_col(768)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NarrativeCluster(Base):
    """Semantički klaster narativnih predloga — grupiše slične AI predloge."""
    __tablename__ = "narrative_clusters"

    id = Column(BigInteger, primary_key=True)
    representative_name = Column(String(500), nullable=False)
    narrative_type = Column(String(50), nullable=False, default="thematic")
    centroid_embedding = _embedding_col(768)
    proposal_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    accepted_narrative_id = Column(Integer, ForeignKey("narratives.id"), nullable=True)
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now())


class ArticleFraming(Base):
    __tablename__ = "article_framings"

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    framing_type_id = Column(Integer, ForeignKey("framing_types.id"), nullable=False)
    confidence = Column(Float)
    supporting_text = Column(Text)

    __table_args__ = (UniqueConstraint("article_id", "framing_type_id"),)


class Narrative(Base):
    __tablename__ = "narratives"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    narrative_type = Column(String(20), nullable=False)  # systemic, thematic
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    is_validated = Column(Boolean, default=False)
    detected_at = Column(DateTime(timezone=True))
    validated_at = Column(DateTime(timezone=True))
    validated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NarrativeProposal(Base):
    """AI predlog novog narativa (per-article) — staging dok ga istrazivac ne validira."""
    __tablename__ = "narrative_proposals"

    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    narrative_type = Column(String(20), nullable=False, default="thematic")
    description = Column(Text)
    supporting_text = Column(Text)
    article_id = Column(BigInteger, ForeignKey("articles.id"))
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    occurrences = Column(Integer, default=1)
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    embedding = _embedding_col(768)
    cluster_id = Column(BigInteger, ForeignKey("narrative_clusters.id"), nullable=True)


class ArticleNarrative(Base):
    __tablename__ = "article_narratives"

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    narrative_id = Column(Integer, ForeignKey("narratives.id"), nullable=False)
    confidence = Column(Float)
    supporting_text = Column(Text)

    __table_args__ = (UniqueConstraint("article_id", "narrative_id"),)


class NarrativeDailyIntensity(Base):
    __tablename__ = "narrative_daily_intensity"

    id = Column(BigInteger, primary_key=True)
    narrative_id = Column(Integer, ForeignKey("narratives.id"), nullable=False)
    source_id = Column(String(20), ForeignKey("sources.source_id"))
    date = Column(Date, nullable=False)
    article_count = Column(Integer, nullable=False, default=0)
    avg_confidence = Column(Float)
    intensity_score = Column(Float)

    __table_args__ = (UniqueConstraint("narrative_id", "source_id", "date"),)


class CalibrationFeedback(Base):
    __tablename__ = "calibration_feedback"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    analysis_type = Column(String(50), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    comment = Column(Text)
    original_value = Column(Text)
    corrected_value = Column(Text)
    applied_to_pipeline = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CalibrationPrompt(Base):
    __tablename__ = "calibration_prompts"

    id = Column(Integer, primary_key=True)
    analysis_type = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False)
    prompt_text = Column(Text, nullable=False)
    feedback_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    activated_at = Column(DateTime(timezone=True))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("analysis_type", "version"),)


class ArticleEmbedding(Base):
    __tablename__ = "article_embeddings"

    id = Column(BigInteger, primary_key=True)
    article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False, unique=True)
    embedding = _embedding_col(768)  # lokalni e5-base (Faza 3)
    model_used = Column(String(100))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TopicProposal(Base):
    """AI predlozi novih tema (NOVA_TEMA: X iz pipeline-a). Istraživač validira."""
    __tablename__ = "topic_proposals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    proposed_key = Column(String(100), nullable=False)
    article_count = Column(Integer, nullable=False, default=1)
    first_seen = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(String(20), nullable=False, default="pending")
    accepted_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)

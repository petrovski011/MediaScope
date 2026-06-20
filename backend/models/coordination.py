from sqlalchemy import (
    Column, BigInteger, Integer, String, Boolean, Text,
    DateTime, ARRAY, Float, ForeignKey, JSON, CheckConstraint, Date
)
from sqlalchemy.sql import func

from database import Base


class CoordinationCopypaste(Base):
    __tablename__ = "coordination_copypaste"

    id = Column(BigInteger, primary_key=True)
    article_id_a = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    article_id_b = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    same_owner_group = Column(Boolean)
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (CheckConstraint("article_id_a < article_id_b"),)


class CoordinationFraming(Base):
    __tablename__ = "coordination_framing"

    id = Column(BigInteger, primary_key=True)
    framing_type_id = Column(Integer, ForeignKey("framing_types.id"), nullable=False)
    source_ids = Column(ARRAY(Text), nullable=False)
    date = Column(Date, nullable=False)
    hour_window = Column(Integer)
    article_count = Column(Integer, nullable=False)
    coordination_score = Column(Float, nullable=False)
    same_owner_group = Column(Boolean)
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CoordinationNarrative(Base):
    __tablename__ = "coordination_narrative"

    id = Column(BigInteger, primary_key=True)
    narrative_id = Column(Integer, ForeignKey("narratives.id"), nullable=False)
    source_ids = Column(ARRAY(Text), nullable=False)
    date = Column(Date, nullable=False)
    hour_window = Column(Integer)
    article_count = Column(Integer, nullable=False)
    coordination_score = Column(Float, nullable=False)
    same_owner_group = Column(Boolean)
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(BigInteger, primary_key=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    score = Column(Float)
    source_ids = Column(ARRAY(Text))
    related_ids = Column(JSON)
    date = Column(Date, nullable=False)
    is_read = Column(Boolean, default=False)
    read_by = Column(Integer, ForeignKey("users.id"))
    read_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(BigInteger, primary_key=True)
    anomaly_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    source_id = Column(String(20), ForeignKey("sources.source_id"))
    topic = Column(String(200))
    narrative_id = Column(Integer, ForeignKey("narratives.id"))
    date = Column(Date, nullable=False)
    baseline_value = Column(Float)
    detected_value = Column(Float)
    deviation_pct = Column(Float)
    baseline_type = Column(String(20))
    alert_id = Column(BigInteger, ForeignKey("alerts.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OriginTracking(Base):
    __tablename__ = "origin_tracking"

    id = Column(BigInteger, primary_key=True)
    topic = Column(String(200), nullable=False)
    first_article_id = Column(BigInteger, ForeignKey("articles.id"), nullable=False)
    first_source_id = Column(String(20), ForeignKey("sources.source_id"), nullable=False)
    first_published_at = Column(DateTime(timezone=True), nullable=False)
    has_exact_time = Column(Boolean, nullable=False, default=True)  # FALSE za RTS/Tanjug
    total_coverage = Column(Integer)
    spread_hours = Column(Float)
    narrative_id = Column(Integer, ForeignKey("narratives.id"))
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PeriodType(Base):
    """Istrazivac oznacava periode (izborni/krizni/miran) radi kontekstualizacije anomalija."""
    __tablename__ = "period_types"

    id = Column(Integer, primary_key=True)
    date_from = Column(String(10), nullable=False)
    date_to = Column(String(10), nullable=False)
    period_type = Column(String(20), nullable=False)  # electoral, crisis, calm
    note = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(BigInteger, primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    summary_text = Column(Text, nullable=False)
    top_topics = Column(ARRAY(Text))
    top_narratives = Column(ARRAY(Integer))
    alert_count = Column(Integer, default=0)
    article_count = Column(Integer, default=0)
    coordination_alerts = Column(Integer, default=0)
    anomaly_count = Column(Integer, default=0)
    model_used = Column(String(50))
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

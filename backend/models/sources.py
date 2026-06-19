from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    source_id = Column(String(20), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    owner = Column(String(200))
    owner_group = Column(String(100))
    media_type = Column(String(20))        # portal, tv_portal, agency, weekly
    scraper_method = Column(String(20))    # rss, html_listing, wp_api, stub
    is_active = Column(Boolean, nullable=False, default=True)
    has_timestamp_time = Column(Boolean, nullable=False, default=True)
    has_author = Column(Boolean, nullable=False, default=True)
    has_category = Column(Boolean, nullable=False, default=True)
    cloudflare = Column(Boolean, nullable=False, default=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

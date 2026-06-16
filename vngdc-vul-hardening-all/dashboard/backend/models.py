from sqlalchemy import Column, String, Integer, DateTime, Text, JSON
from datetime import datetime, timezone
import uuid
from database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class Server(Base):
    __tablename__ = "servers"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, default=22)
    username = Column(String, nullable=False)
    password = Column(String)
    ssh_key = Column(Text)
    os_type = Column(String, default="ubuntu")  # ubuntu | windows | junos
    created_at = Column(DateTime(timezone=True), default=_now)
    last_checked_at = Column(DateTime(timezone=True))
    last_status = Column(String)  # hardened | partial | none


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=_uuid)
    server_id = Column(String, nullable=False, index=True)
    checked_at = Column(DateTime(timezone=True), default=_now)
    status = Column(String)  # hardened | partial | none | error
    sections = Column(JSON)
    raw_output = Column(Text)
    error = Column(Text)
    duration_seconds = Column(Integer)
    analysis = Column(Text)  # AI-generated analysis from agent


class CheckTask(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=_uuid)
    server_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending | running | completed | failed
    created_at = Column(DateTime(timezone=True), default=_now)
    completed_at = Column(DateTime(timezone=True))
    report_id = Column(String)
    error = Column(Text)


class VulnerabilityScan(Base):
    __tablename__ = "vulnerability_scans"

    id = Column(String, primary_key=True, default=_uuid)
    scanned_at = Column(DateTime(timezone=True), default=_now, index=True)
    status = Column(String, default="pending")  # completed | failed | not_configured
    source = Column(String)
    agent_filter = Column(String)
    total = Column(Integer, default=0)
    fetched = Column(Integer, default=0)
    critical = Column(Integer, default=0)
    high = Column(Integer, default=0)
    medium = Column(Integer, default=0)
    low = Column(Integer, default=0)
    summary = Column(JSON)
    items = Column(JSON)
    analysis = Column(Text)
    error = Column(Text)
    duration_seconds = Column(Integer)


class VulnerabilityEnrichment(Base):
    __tablename__ = "vulnerability_enrichments"

    cve = Column(String, primary_key=True)
    fetched_at = Column(DateTime(timezone=True), default=_now, index=True)
    data = Column(JSON)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class AgentChatMessage(Base):
    __tablename__ = "agent_chat_messages"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)

"""
数据库模型定义

使用SQLAlchemy ORM定义4个核心模型：
1. Teacher - 老师信息
2. Evaluation - 评价信息
3. EvaluationSource - 评价来源
4. MatchHistory - 匹配历史
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    DECIMAL,
    JSON,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Teacher(Base):
    """老师信息表"""

    __tablename__ = "teachers"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 基础信息（复用现有Excel字段）
    school = Column(String(200), nullable=True, comment="学校名称")
    college = Column(String(200), nullable=True, comment="学院名称")
    name = Column(String(100), nullable=False, comment="姓名")
    title = Column(String(100), nullable=True, comment="职称")
    email = Column(String(200), unique=True, nullable=True, comment="邮箱（唯一键）")
    research = Column(Text, nullable=True, comment="研究方向")
    tag = Column(JSON, nullable=True, comment="研究领域标签（JSON数组，4-5个）")
    introduction = Column(Text, nullable=True, comment="导师介绍原文")
    mark = Column(Text, nullable=True, comment="备注")

    # 时间戳
    created_at = Column(
        DateTime, default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    # 关系：一个老师有多条评价
    evaluations = relationship(
        "Evaluation", back_populates="teacher", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_teacher_email", "email"),
        Index("idx_teacher_name", "name"),
        Index("idx_teacher_school_name", "school", "name"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "school": self.school,
            "college": self.college,
            "name": self.name,
            "title": self.title,
            "email": self.email,
            "research": self.research,
            "tag": self.tag,
            "introduction": self.introduction,
            "mark": self.mark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Teacher(id={self.id}, name='{self.name}', school='{self.school}', email='{self.email}')>"


class EvaluationSource(Base):
    """评价来源表"""

    __tablename__ = "evaluation_sources"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 来源信息
    source_name = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="来源名称（如：小木虫、小红书）",
    )
    source_url = Column(String(500), nullable=True, comment="来源网站URL")
    crawler_config = Column(JSON, nullable=True, comment="爬虫配置（JSON格式）")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    # 时间戳
    created_at = Column(
        DateTime, default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    # 关系：一个来源有多条评价
    evaluations = relationship(
        "Evaluation", back_populates="source", cascade="all, delete-orphan"
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "crawler_config": self.crawler_config,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<EvaluationSource(id={self.id}, name='{self.source_name}', active={self.is_active})>"


class Evaluation(Base):
    """评价信息表"""

    __tablename__ = "evaluations"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 原始信息（从爬虫获取）
    raw_teacher_name = Column(String(100), nullable=False, comment="原始老师姓名")
    raw_school_name = Column(String(200), nullable=True, comment="原始学校名称")
    raw_metadata = Column(JSON, nullable=True, comment="原始元数据（JSON格式）")

    # 评价内容
    content = Column(Text, nullable=True, comment="评价内容")
    rating = Column(DECIMAL(3, 2), nullable=True, comment="总体评分（0-5）")

    # 评价维度细分
    rating_academic = Column(
        DECIMAL(3, 2), nullable=True, comment="学术水平评分（0-5）"
    )
    rating_guidance = Column(
        DECIMAL(3, 2), nullable=True, comment="指导质量评分（0-5）"
    )
    rating_personality = Column(
        DECIMAL(3, 2), nullable=True, comment="人品态度评分（0-5）"
    )

    # 评价时间和热度
    published_at = Column(DateTime, nullable=True, comment="发布时间")
    likes_count = Column(Integer, default=0, nullable=False, comment="点赞数")
    comments_count = Column(Integer, default=0, nullable=False, comment="评论数")

    # 来源信息
    source_url = Column(String(1000), nullable=True, comment="来源URL")
    source_id = Column(
        Integer,
        ForeignKey("evaluation_sources.id"),
        nullable=True,
        comment="评价来源ID",
    )

    # 匹配状态
    match_status = Column(
        String(20),
        default="pending",
        nullable=False,
        comment="匹配状态：pending（待匹配）、matched（已匹配）、rejected（已拒绝）、needs_review（需人工审核）",
    )
    confidence_score = Column(DECIMAL(3, 2), nullable=True, comment="匹配置信度（0-1）")
    match_reason = Column(Text, nullable=True, comment="匹配/拒绝原因")

    # 关联老师
    teacher_id = Column(
        Integer, ForeignKey("teachers.id"), nullable=True, comment="关联的老师ID"
    )

    # 时间戳
    created_at = Column(
        DateTime, default=func.now(), nullable=False, comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )

    # 关系
    teacher = relationship("Teacher", back_populates="evaluations")
    source = relationship("EvaluationSource", back_populates="evaluations")
    match_histories = relationship(
        "MatchHistory", back_populates="evaluation", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_evaluation_match_status", "match_status"),
        Index("idx_evaluation_teacher_id", "teacher_id"),
        Index("idx_evaluation_source_id", "source_id"),
        Index("idx_evaluation_published_at", "published_at"),
        Index("idx_evaluation_likes_count", "likes_count"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "raw_teacher_name": self.raw_teacher_name,
            "raw_school_name": self.raw_school_name,
            "raw_metadata": self.raw_metadata,
            "content": self.content,
            "rating": float(self.rating) if self.rating else None,
            "rating_academic": float(self.rating_academic)
            if self.rating_academic
            else None,
            "rating_guidance": float(self.rating_guidance)
            if self.rating_guidance
            else None,
            "rating_personality": float(self.rating_personality)
            if self.rating_personality
            else None,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "likes_count": self.likes_count,
            "comments_count": self.comments_count,
            "source_url": self.source_url,
            "source_id": self.source_id,
            "match_status": self.match_status,
            "confidence_score": float(self.confidence_score)
            if self.confidence_score
            else None,
            "match_reason": self.match_reason,
            "teacher_id": self.teacher_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Evaluation(id={self.id}, teacher='{self.raw_teacher_name}', status='{self.match_status}')>"


class MatchHistory(Base):
    """匹配历史表"""

    __tablename__ = "match_history"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联评价
    evaluation_id = Column(
        Integer, ForeignKey("evaluations.id"), nullable=False, comment="评价ID"
    )

    # 匹配信息
    matched_teacher_id = Column(Integer, nullable=True, comment="匹配的老师ID")
    confidence_score = Column(DECIMAL(3, 2), nullable=False, comment="置信度（0-1）")
    match_decision = Column(
        String(20),
        nullable=False,
        comment="匹配决策：accept（接受）、reject（拒绝）、review（需审核）",
    )
    reasoning = Column(Text, nullable=True, comment="决策理由")

    # Agent工具调用记录
    tool_calls = Column(JSON, nullable=True, comment="Agent工具调用记录（JSON格式）")

    # 时间戳
    created_at = Column(
        DateTime, default=func.now(), nullable=False, comment="创建时间"
    )

    # 关系
    evaluation = relationship("Evaluation", back_populates="match_histories")

    # 索引
    __table_args__ = (
        Index("idx_match_history_evaluation_id", "evaluation_id"),
        Index("idx_match_history_decision", "match_decision"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "evaluation_id": self.evaluation_id,
            "matched_teacher_id": self.matched_teacher_id,
            "confidence_score": float(self.confidence_score)
            if self.confidence_score
            else None,
            "match_decision": self.match_decision,
            "reasoning": self.reasoning,
            "tool_calls": self.tool_calls,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<MatchHistory(id={self.id}, eval_id={self.evaluation_id}, decision='{self.match_decision}')>"

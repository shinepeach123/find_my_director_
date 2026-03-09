"""
存储抽象层

提供统一的存储接口，支持多种后端（PostgreSQL、SQLite、Excel）
通过工厂函数get_storage_backend()切换存储方式
"""

import os
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, and_, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from models import Base, Teacher, Evaluation, EvaluationSource, MatchHistory


class StorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    def add_teacher(self, teacher_info: Dict[str, Any]) -> Optional[int]:
        """添加老师信息，返回老师ID"""
        pass

    @abstractmethod
    def teacher_exists(self, email: str) -> bool:
        """检查邮箱是否已存在"""
        pass

    @abstractmethod
    def search_teachers(
        self,
        name: Optional[str] = None,
        school: Optional[str] = None,
        college: Optional[str] = None,
        email: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索老师（模糊匹配），用于Agent工具"""
        pass

    @abstractmethod
    def get_teacher_by_id(self, teacher_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取老师详细信息"""
        pass

    @abstractmethod
    def get_teacher_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取老师信息"""
        pass

    @abstractmethod
    def add_evaluation(self, evaluation_info: Dict[str, Any]) -> Optional[int]:
        """添加评价信息，返回评价ID"""
        pass

    @abstractmethod
    def get_pending_evaluations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待匹配的评价"""
        pass

    @abstractmethod
    def update_evaluation_match(
        self,
        evaluation_id: int,
        teacher_id: Optional[int],
        confidence: float,
        reason: str,
        match_status: str,
    ) -> bool:
        """更新评价的匹配状态"""
        pass

    @abstractmethod
    def add_match_history(self, history_info: Dict[str, Any]) -> Optional[int]:
        """添加匹配历史记录"""
        pass

    @abstractmethod
    def add_evaluation_source(self, source_info: Dict[str, Any]) -> Optional[int]:
        """添加评价来源"""
        pass

    @abstractmethod
    def get_all_teachers(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有老师信息（用于数据迁移）"""
        pass

    @abstractmethod
    def find_evaluation(
        self,
        raw_teacher_name: str,
        raw_school_name: str,
        source_id: Optional[int],
    ) -> Optional[int]:
        """查找已存在的评价记录，返回评价ID，不存在则返回None"""
        pass

    @abstractmethod
    def update_evaluation_content(
        self,
        evaluation_id: int,
        content: str,
    ) -> bool:
        """重置评价内容并将匹配状态恢复为 pending"""
        pass


class SQLAlchemyBackend(StorageBackend):
    """
    基于 SQLAlchemy 的存储后端基类

    包含 PostgreSQL 和 SQLite 共享的所有数据库操作方法。
    子类负责在 __init__ 中初始化 self.engine 和 self.SessionLocal。
    """

    def __init__(self):
        # 子类必须在 __init__ 中赋值，这里仅声明用于类型提示
        self.engine: Any = None
        self.SessionLocal: Any = None

    def _get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    def add_teacher(self, teacher_info: Dict[str, Any]) -> Optional[int]:
        """添加老师信息"""
        session = self._get_session()
        try:
            # 检查邮箱是否已存在
            email = teacher_info.get("email")
            if email and self.teacher_exists(email):
                print(f"⚠️  老师邮箱已存在，跳过: {email}")
                return None

            teacher = Teacher(
                school=teacher_info.get("school"),
                college=teacher_info.get("college"),
                name=teacher_info.get("name"),
                title=teacher_info.get("title"),
                email=email,
                research=teacher_info.get("research"),
                tag=teacher_info.get("tag"),
                introduction=teacher_info.get("introduction"),
                mark=teacher_info.get("mark"),
            )
            session.add(teacher)
            session.commit()
            teacher_id = teacher.id
            print(f"✅ 添加老师成功: {teacher.name} (ID={teacher_id})")
            return teacher_id
        except Exception as e:
            session.rollback()
            print(f"❌ 添加老师失败: {e}")
            return None
        finally:
            session.close()

    def teacher_exists(self, email: str) -> bool:
        """检查邮箱是否已存在"""
        if not email:
            return False
        session = self._get_session()
        try:
            exists = (
                session.query(Teacher).filter(Teacher.email == email).first()
                is not None
            )
            return exists
        finally:
            session.close()

    def search_teachers(
        self,
        name: Optional[str] = None,
        school: Optional[str] = None,
        college: Optional[str] = None,
        email: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索老师（模糊匹配）"""
        session = self._get_session()
        try:
            query = session.query(Teacher)

            # 构建查询条件
            conditions = []
            if name:
                conditions.append(Teacher.name.contains(name))
            if school:
                conditions.append(Teacher.school.contains(school))
            if college:
                conditions.append(Teacher.college.contains(college))
            if email:
                conditions.append(Teacher.email.contains(email))

            if conditions:
                query = query.filter(and_(*conditions))

            teachers = query.limit(limit).all()
            return [teacher.to_dict() for teacher in teachers]
        finally:
            session.close()

    def get_teacher_by_id(self, teacher_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取老师详细信息"""
        session = self._get_session()
        try:
            teacher = session.query(Teacher).filter(Teacher.id == teacher_id).first()
            return teacher.to_dict() if teacher else None
        finally:
            session.close()

    def get_teacher_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取老师信息"""
        session = self._get_session()
        try:
            teacher = session.query(Teacher).filter(Teacher.email == email).first()
            return teacher.to_dict() if teacher else None
        finally:
            session.close()

    def add_evaluation(self, evaluation_info: Dict[str, Any]) -> Optional[int]:
        """添加评价信息"""
        session = self._get_session()
        try:
            # 处理published_at字段
            published_at = evaluation_info.get("published_at")
            if published_at and isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None

            evaluation = Evaluation(
                raw_teacher_name=evaluation_info.get("raw_teacher_name"),
                raw_school_name=evaluation_info.get("raw_school_name"),
                raw_metadata=evaluation_info.get("raw_metadata"),
                content=evaluation_info.get("content"),
                rating=evaluation_info.get("rating"),
                rating_academic=evaluation_info.get("rating_academic"),
                rating_guidance=evaluation_info.get("rating_guidance"),
                rating_personality=evaluation_info.get("rating_personality"),
                published_at=published_at,
                likes_count=evaluation_info.get("likes_count", 0),
                comments_count=evaluation_info.get("comments_count", 0),
                source_url=evaluation_info.get("source_url"),
                source_id=evaluation_info.get("source_id"),
                match_status=evaluation_info.get("match_status", "pending"),
                teacher_id=evaluation_info.get("teacher_id"),
            )
            session.add(evaluation)
            session.commit()
            evaluation_id = evaluation.id
            print(
                f"✅ 添加评价成功: {evaluation.raw_teacher_name} (ID={evaluation_id})"
            )
            return evaluation_id
        except Exception as e:
            session.rollback()
            print(f"❌ 添加评价失败: {e}")
            return None
        finally:
            session.close()

    def get_pending_evaluations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待匹配的评价"""
        session = self._get_session()
        try:
            evaluations = (
                session.query(Evaluation)
                .filter(Evaluation.match_status == "pending")
                .limit(limit)
                .all()
            )
            return [eval.to_dict() for eval in evaluations]
        finally:
            session.close()

    def update_evaluation_match(
        self,
        evaluation_id: int,
        teacher_id: Optional[int],
        confidence: float,
        reason: str,
        match_status: str,
    ) -> bool:
        """更新评价的匹配状态"""
        session = self._get_session()
        try:
            evaluation = (
                session.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
            )
            if not evaluation:
                print(f"❌ 评价ID={evaluation_id}不存在")
                return False

            evaluation.teacher_id = teacher_id
            evaluation.confidence_score = confidence
            evaluation.match_reason = reason
            evaluation.match_status = match_status
            session.commit()
            print(f"✅ 更新评价匹配状态: ID={evaluation_id}, status={match_status}")
            return True
        except Exception as e:
            session.rollback()
            print(f"❌ 更新评价匹配状态失败: {e}")
            return False
        finally:
            session.close()

    def add_match_history(self, history_info: Dict[str, Any]) -> Optional[int]:
        """添加匹配历史记录"""
        session = self._get_session()
        try:
            history = MatchHistory(
                evaluation_id=history_info.get("evaluation_id"),
                matched_teacher_id=history_info.get("matched_teacher_id"),
                confidence_score=history_info.get("confidence_score"),
                match_decision=history_info.get("match_decision"),
                reasoning=history_info.get("reasoning"),
                tool_calls=history_info.get("tool_calls"),
            )
            session.add(history)
            session.commit()
            return history.id
        except Exception as e:
            session.rollback()
            print(f"❌ 添加匹配历史失败: {e}")
            return None
        finally:
            session.close()

    def add_evaluation_source(self, source_info: Dict[str, Any]) -> Optional[int]:
        """添加评价来源"""
        session = self._get_session()
        try:
            # 检查来源是否已存在
            existing = (
                session.query(EvaluationSource)
                .filter(EvaluationSource.source_name == source_info.get("source_name"))
                .first()
            )
            if existing:
                print(f"⚠️  评价来源已存在: {source_info.get('source_name')}")
                return existing.id

            source = EvaluationSource(
                source_name=source_info.get("source_name"),
                source_url=source_info.get("source_url"),
                crawler_config=source_info.get("crawler_config"),
                is_active=source_info.get("is_active", True),
            )
            session.add(source)
            session.commit()
            print(f"✅ 添加评价来源成功: {source.source_name} (ID={source.id})")
            return source.id
        except Exception as e:
            session.rollback()
            print(f"❌ 添加评价来源失败: {e}")
            return None
        finally:
            session.close()

    def get_all_teachers(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有老师信息（用于数据迁移）"""
        session = self._get_session()
        try:
            query = session.query(Teacher)
            if limit:
                query = query.limit(limit)
            teachers = query.all()
            return [teacher.to_dict() for teacher in teachers]
        finally:
            session.close()

    def find_evaluation(
        self,
        raw_teacher_name: str,
        raw_school_name: str,
        source_id: Optional[int],
    ) -> Optional[int]:
        """查找已存在的评价记录，返回评价ID，不存在则返回None"""
        session = self._get_session()
        try:
            existing = (
                session.query(Evaluation)
                .filter_by(
                    raw_teacher_name=raw_teacher_name,
                    raw_school_name=raw_school_name,
                    source_id=source_id,
                )
                .first()
            )
            return existing.id if existing else None
        finally:
            session.close()

    def update_evaluation_content(
        self,
        evaluation_id: int,
        content: str,
    ) -> bool:
        """重置评价内容并将匹配状态恢复为 pending"""
        session = self._get_session()
        try:
            evaluation = session.get(Evaluation, evaluation_id)
            if not evaluation:
                print(f"❌ 评价ID={evaluation_id}不存在")
                return False
            evaluation.content = content
            evaluation.match_status = "pending"
            evaluation.confidence_score = None
            evaluation.teacher_id = None
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"❌ 更新评价内容失败: {e}")
            return False
        finally:
            session.close()


class PostgreSQLBackend(SQLAlchemyBackend):
    """PostgreSQL存储后端"""

    def __init__(self, database_url: Optional[str] = None):
        """
        初始化PostgreSQL连接

        Args:
            database_url: 数据库连接URL，如：postgresql://user:pass@localhost:5432/dbname
                         如果不提供，会从环境变量DATABASE_URL读取
        """
        if database_url is None:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                raise ValueError(
                    "请提供数据库连接URL或设置环境变量DATABASE_URL\n"
                    "示例: DATABASE_URL=postgresql://faculty_user:faculty_pass@localhost:5432/faculty_db"
                )

        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # 自动检测断开的连接
            echo=False,
        )

        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        print(
            f"✅ PostgreSQL连接成功: {database_url.split('@')[1] if '@' in database_url else database_url}"
        )


class SQLiteBackend(SQLAlchemyBackend):
    """SQLite存储后端（本地测试/开发）"""

    def __init__(self, database_path: Optional[str] = None):
        """
        初始化SQLite连接

        Args:
            database_path: SQLite数据库文件路径
                         - 可以是相对路径（相对于项目根目录）
                         - 可以是绝对路径
                         - 可以是 ":memory:" 表示内存数据库
                         - 如果不提供，会从环境变量SQLITE_DB_PATH读取，默认为 'faculty.db'
        """
        # 1. 确定数据库路径
        if database_path is None:
            database_path = os.getenv("SQLITE_DB_PATH", "faculty.db")

        # 2. 处理相对路径（转为绝对路径）
        if database_path != ":memory:" and not os.path.isabs(database_path):
            project_root = os.path.dirname(os.path.abspath(__file__))
            database_path = os.path.join(project_root, database_path)

        # 3. 构建 SQLAlchemy URL
        database_url = f"sqlite:///{database_path}"

        # 4. 创建引擎（SQLite 特有配置）
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=1,  # SQLite 适合小连接池
            max_overflow=3,
            pool_pre_ping=True,
            pool_recycle=3600,  # 每小时回收连接
            echo=False,
            connect_args={
                "check_same_thread": False,  # 允许多线程访问
                "timeout": 20,  # 锁超时时间（秒）
            },
        )

        # 5. 配置 PRAGMA（性能优化）
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")  # WAL 模式（提升并发性能）
            cursor.execute("PRAGMA synchronous=NORMAL")  # 同步模式（平衡性能和安全性）
            cursor.execute("PRAGMA cache_size=-10000")  # 10MB 缓存
            cursor.execute("PRAGMA foreign_keys=ON")  # 启用外键约束
            cursor.close()

        # 6. 创建所有表
        Base.metadata.create_all(self.engine)

        # 7. 创建Session工厂
        self.SessionLocal = sessionmaker(bind=self.engine)

        if database_path == ":memory:":
            print(f"✅ SQLite连接成功: 内存数据库")
        else:
            print(f"✅ SQLite连接成功: {database_path}")


class ExcelBackend(StorageBackend):
    """Excel存储后端（向后兼容）"""

    def __init__(self, excel_path: str, csv_path: Optional[str] = None):
        """
        初始化Excel存储

        Args:
            excel_path: Excel文件路径
            csv_path: CSV文件路径（可选）
        """
        self.excel_path = excel_path
        self.csv_path = csv_path
        self.lock = threading.Lock()

        # 确保文件存在
        if not os.path.exists(excel_path):
            df = pd.DataFrame(
                columns=[
                    "school",
                    "college",
                    "name",
                    "title",
                    "email",
                    "research",
                    "tag",
                    "introduction",
                    "mark",
                ]
            )
            df.to_excel(excel_path, index=False)
            print(f"✅ 创建Excel文件: {excel_path}")

        if csv_path and not os.path.exists(csv_path):
            df = pd.DataFrame(
                columns=[
                    "school",
                    "college",
                    "name",
                    "title",
                    "email",
                    "research",
                    "tag",
                    "introduction",
                    "mark",
                ]
            )
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"✅ 创建CSV文件: {csv_path}")

    def add_teacher(self, teacher_info: Dict[str, Any]) -> Optional[int]:
        """添加老师信息"""
        with self.lock:
            try:
                # 读取Excel
                df = pd.read_excel(self.excel_path)

                # 检查邮箱是否已存在
                email = teacher_info.get("email")
                if email and self.teacher_exists(email):
                    print(f"⚠️  老师邮箱已存在，跳过: {email}")
                    return None

                # 添加新行
                new_row = {
                    "school": teacher_info.get("school"),
                    "college": teacher_info.get("college"),
                    "name": teacher_info.get("name"),
                    "title": teacher_info.get("title"),
                    "email": email,
                    "research": teacher_info.get("research"),
                    "tag": teacher_info.get("tag"),
                    "introduction": teacher_info.get("introduction"),
                    "mark": teacher_info.get("mark"),
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                # 写入文件
                df.to_excel(self.excel_path, index=False)
                if self.csv_path:
                    df.to_csv(self.csv_path, index=False, encoding="utf-8-sig")

                print(f"✅ 添加老师成功: {teacher_info.get('name')}")
                return len(df) - 1  # 返回行索引作为ID
            except Exception as e:
                print(f"❌ 添加老师失败: {e}")
                return None

    def teacher_exists(self, email: str) -> bool:
        """检查邮箱是否已存在"""
        if not email:
            return False
        try:
            df = pd.read_excel(self.excel_path)
            return email in df["email"].values
        except Exception:
            return False

    def search_teachers(
        self,
        name: Optional[str] = None,
        school: Optional[str] = None,
        college: Optional[str] = None,
        email: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索老师（模糊匹配）"""
        try:
            df = pd.read_excel(self.excel_path)

            # 构建查询条件
            mask = pd.Series([True] * len(df))
            if name:
                mask &= df["name"].str.contains(name, na=False)
            if school:
                mask &= df["school"].str.contains(school, na=False)
            if college:
                mask &= df["college"].str.contains(college, na=False)
            if email:
                mask &= df["email"].str.contains(email, na=False)

            results = df[mask].head(limit)
            return results.to_dict("records")
        except Exception as e:
            print(f"❌ 搜索老师失败: {e}")
            return []

    def get_teacher_by_id(self, teacher_id: int) -> Optional[Dict[str, Any]]:
        """根据ID（行索引）获取老师详细信息"""
        try:
            df = pd.read_excel(self.excel_path)
            if teacher_id < len(df):
                return df.iloc[teacher_id].to_dict()
            return None
        except Exception as e:
            print(f"❌ 获取老师信息失败: {e}")
            return None

    def get_teacher_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取老师信息"""
        try:
            df = pd.read_excel(self.excel_path)
            result = df[df["email"] == email]
            if not result.empty:
                return result.iloc[0].to_dict()
            return None
        except Exception as e:
            print(f"❌ 获取老师信息失败: {e}")
            return None

    def add_evaluation(self, evaluation_info: Dict[str, Any]) -> Optional[int]:
        """Excel后端不支持评价功能"""
        print("⚠️  Excel后端不支持评价功能，请使用PostgreSQL后端")
        return None

    def get_pending_evaluations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Excel后端不支持评价功能"""
        print("⚠️  Excel后端不支持评价功能，请使用PostgreSQL后端")
        return []

    def update_evaluation_match(
        self,
        evaluation_id: int,
        teacher_id: Optional[int],
        confidence: float,
        reason: str,
        match_status: str,
    ) -> bool:
        """Excel后端不支持评价功能"""
        print("⚠️  Excel后端不支持评价功能，请使用PostgreSQL后端")
        return False

    def add_match_history(self, history_info: Dict[str, Any]) -> Optional[int]:
        """Excel后端不支持匹配历史功能"""
        print("⚠️  Excel后端不支持匹配历史功能，请使用PostgreSQL后端")
        return None

    def add_evaluation_source(self, source_info: Dict[str, Any]) -> Optional[int]:
        """Excel后端不支持评价来源功能"""
        print("⚠️  Excel后端不支持评价来源功能，请使用PostgreSQL后端")
        return None

    def get_all_teachers(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取所有老师信息（用于数据迁移）"""
        try:
            df = pd.read_excel(self.excel_path)
            if limit:
                df = df.head(limit)
            return df.to_dict("records")
        except Exception as e:
            print(f"❌ 获取老师列表失败: {e}")
            return []

    def find_evaluation(
        self,
        raw_teacher_name: str,
        raw_school_name: str,
        source_id: Optional[int],
    ) -> Optional[int]:
        """Excel后端不支持评价查找功能"""
        print("⚠️  Excel后端不支持评价查找功能，请使用PostgreSQL或SQLite后端")
        return None

    def update_evaluation_content(
        self,
        evaluation_id: int,
        content: str,
    ) -> bool:
        """Excel后端不支持评价更新功能"""
        print("⚠️  Excel后端不支持评价更新功能，请使用PostgreSQL或SQLite后端")
        return False


def get_storage_backend(backend_type: Optional[str] = None, **kwargs) -> StorageBackend:
    """
    工厂函数：根据类型创建存储后端

    Args:
        backend_type: 后端类型
            - "postgresql": PostgreSQL（生产环境）
            - "sqlite": SQLite（本地测试/开发）
            - "excel": Excel（简单使用场景）
            - None: 自动检测（从环境变量）
        **kwargs: 后端特定的参数
            - PostgreSQL: database_url
            - SQLite: database_path
            - Excel: excel_path, csv_path

    环境变量：
        DB_TYPE: 数据库类型（sqlite/postgresql/excel）
        DATABASE_URL: 数据库连接字符串（可推断类型）
        SQLITE_DB_PATH: SQLite 数据库文件路径

    Returns:
        StorageBackend实例
    """
    # 1. 自动检测后端类型（如果未指定）
    if backend_type is None:
        database_url = os.getenv("DATABASE_URL", "")
        if database_url.startswith("postgresql://"):
            backend_type = "postgresql"
        elif database_url.startswith("sqlite://"):
            backend_type = "sqlite"
        else:
            backend_type = os.getenv("DB_TYPE", "excel")  # 默认 Excel（向后兼容）

    backend_type = backend_type.lower()

    # 2. 根据类型创建后端
    if backend_type == "postgresql":
        database_url = kwargs.get("database_url") or os.getenv("DATABASE_URL")
        return PostgreSQLBackend(database_url=database_url)

    elif backend_type == "sqlite":
        database_path = kwargs.get("database_path") or os.getenv("SQLITE_DB_PATH")
        return SQLiteBackend(database_path=database_path)

    elif backend_type == "excel":
        excel_path = kwargs.get("excel_path", "supervisors.xlsx")
        csv_path = kwargs.get("csv_path", "supervisors.csv")
        return ExcelBackend(excel_path=excel_path, csv_path=csv_path)

    else:
        raise ValueError(
            f"不支持的后端类型: {backend_type}\n"
            f"支持的类型: postgresql, sqlite, excel\n"
            f"请设置环境变量 DB_TYPE 或传入 backend_type 参数"
        )


# 示例用法
if __name__ == "__main__":
    # 测试 SQLite 后端（内存模式，无需外部依赖）
    print("=== 测试SQLite后端 ===")
    storage = get_storage_backend("sqlite", database_path=":memory:")

    teacher_id = storage.add_teacher(
        {
            "school": "测试大学",
            "college": "计算机学院",
            "name": "张三",
            "title": "教授",
            "email": "zhangsan@test.edu.cn",
            "research": "AI、机器学习",
            "tag": ["人工智能", "机器学习", "深度学习"],
            "introduction": "测试导师介绍",
            "mark": "测试数据",
        }
    )

    if teacher_id:
        results = storage.search_teachers(name="张三")
        print(f"\n搜索结果: {results}")

        teacher = storage.get_teacher_by_id(teacher_id)
        print(f"\n老师详情: {teacher}")

        exists = storage.teacher_exists("zhangsan@test.edu.cn")
        print(f"\n邮箱存在: {exists}")

    print("\n=== 测试PostgreSQL后端（需要配置DATABASE_URL）===")
    try:
        storage_pg = get_storage_backend("postgresql")
        print("PostgreSQL 连接成功")
    except Exception as e:
        print(f"PostgreSQL 测试跳过: {e}")

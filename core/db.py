"""数据库引擎、模型基类和会话管理。"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """所有 ORM 模型都继承这个声明式基类。"""


def load_all_models() -> None:
    """导入所有模型模块，确保 SQLAlchemy 能收集完整 metadata。"""
    import api.document.model  # noqa: F401
    import api.chunk.model  # noqa: F401
    import api.files.model  # noqa: F401
    import api.knowledge.model  # noqa: F401
    import api.rag.model  # noqa: F401
    import api.user.model  # noqa: F401


def _build_engine():
    """根据配置构建数据库引擎。"""
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        echo=settings.database_echo,
        future=True,
        connect_args=connect_args,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """通过 FastAPI 依赖注入提供请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """按当前模型定义创建全部数据表。"""
    load_all_models()
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """按当前模型定义删除全部数据表，便于本地学习时重置环境。"""
    load_all_models()
    Base.metadata.drop_all(bind=engine)


def test_database_connection() -> bool:
    """执行最小 SQL 验证数据库连接是否可用。"""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
    import api.audit.model  # noqa: F401

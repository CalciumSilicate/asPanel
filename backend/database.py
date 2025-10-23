# database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.core.constants import SQLALCHEMY_DATABASE_URL, DATABASE_CONNECT_ARGS
from contextlib import contextmanager
from sqlalchemy import text

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=DATABASE_CONNECT_ARGS
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_user_columns():
    """
    轻量级 SQLite 迁移：在 users 表不存在以下列时，执行 ALTER TABLE 添加：
    - email TEXT
    - qq TEXT
    - bound_player_id INTEGER
    说明：SQLite 对外键约束的 ALTER 限制较多，此处仅添加列，不强制 FK 约束。
    """
    try:
        with engine.connect() as conn:
            cols = set()
            for r in conn.exec_driver_sql("PRAGMA table_info('users')").fetchall():
                # r: cid, name, type, notnull, dflt_value, pk
                cols.add(str(r[1]))
            to_add: list[tuple[str, str]] = []
            if 'email' not in cols:
                to_add.append(("email", "TEXT"))
            if 'qq' not in cols:
                to_add.append(("qq", "TEXT"))
            if 'bound_player_id' not in cols:
                to_add.append(("bound_player_id", "INTEGER"))
            for name, typ in to_add:
                conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {name} {typ}")
    except Exception:
        # 不阻断启动；记录到日志由上层捕获（main.py 中已做全局异常保护）
        pass

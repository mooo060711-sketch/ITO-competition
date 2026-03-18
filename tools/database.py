from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ==========================================
# 1. 配置数据库的“家庭住址” (URL)
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./courseware_agent.db" 

# ==========================================
# 2. 启动“核心引擎” (Engine)
# ==========================================
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} 
)

# ==========================================
# 3. 创建“会话制造工厂” (SessionLocal)
# ==========================================
# 🌟 核心修改：增加 expire_on_commit=False
# 防止 commit 后对象失效导致的二阶段提交或连接中断报错
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine, 
    expire_on_commit=False
)

# ==========================================
# 4. 快捷获取连接的生成器
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

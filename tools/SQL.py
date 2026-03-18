from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()

class SessionHistory(Base):
    """
    会话历史表：记录人机对话交互上下文。
    """
    __tablename__ = 'session_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), index=True) # 关联的会话ID
    role = Column(String(20))                   # 角色：'user' 或 'assistant'
    content = Column(Text)                      # 具体的聊天内容
    timestamp = Column(DateTime, default=datetime.utcnow) # 记录发生时间

class SessionContext(Base):
    """
    会话上下文表：存储当前教学任务的所有【实时/最新】资产路径。
    """
    __tablename__ = 'session_context'
    
    session_id = Column(String(50), primary_key=True, default=lambda: f"sess_{uuid.uuid4().hex}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 教学要素 (Agent 1 提取结果)
    extracted_slots = Column(JSON, nullable=True, default={})
    
    # --- 🌟 当前活跃资产 (供一键导出和前端实时展示) ---
    baidu_outline_str = Column(Text, nullable=True) # 当前大纲文本
    total_pages = Column(Integer, default=0)       # 幻灯片页数统计
    lesson_plan_str = Column(Text, nullable=True)   # 当前教案文本
    lesson_plan_path = Column(Text, nullable=True)  # 当前教案 Word 物理路径
    
    # 🌟 新增：当前活跃的 PPT 文件物理路径
    # 将其从版本快照提升至此，使导出逻辑无需查询版本表即可直接打包
    ppt_path = Column(Text, nullable=True) 
    
    # 游戏资产 (Module 5)：存储 1-7 种游戏的路径列表对象
    game_path = Column(JSON, nullable=True, default=[]) 
    
    # 标记：是否延迟图片安放追问
    is_image_placement_deferred = Column(Boolean, default=False)
    
    # 关系映射
    images = relationship("TempImage", back_populates="session", cascade="all, delete-orphan")
    versions = relationship("CoursewareVersion", back_populates="session", cascade="all, delete-orphan")

class CoursewareVersion(Base):
    """
    时光机版本库：记录【核心资产】在某一时刻的完整快照。
    用于版本回滚、对比及历史记录查看。
    """
    __tablename__ = 'courseware_version'
    
    version_id = Column(String(50), primary_key=True, default=lambda: f"ver_{uuid.uuid4().hex[:8]}")
    session_id = Column(String(50), ForeignKey('session_context.session_id'))
    version_note = Column(String(255)) # 版本说明
    
    # --- 核心资产快照（用于还原还原） ---
    outline_snapshot = Column(Text)           # 大纲内容快照
    plan_snapshot = Column(Text, nullable=True) # 教案文本快照
    lesson_plan_path_snapshot = Column(Text, nullable=True) # 教案物理路径快照
    ppt_path = Column(Text, nullable=True)    # PPT 物理路径快照
    
    # 🌟 游戏资产快照 (支持回滚到特定游戏版本)
    game_path_snapshot = Column(JSON, nullable=True, default=[]) 
    
    # 图片布局快照 (记录当时图片的排版位置 JSON)
    image_layout_snapshot = Column(JSON, nullable=True)     
    
    created_at = Column(DateTime, default=datetime.utcnow)
    session = relationship("SessionContext", back_populates="versions")

class TempImage(Base):
    """
    图片库：关联到当前会话的图片素材及其排版坐标。
    """
    __tablename__ = 'temp_image'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), ForeignKey('session_context.session_id'))
    image_id = Column(String(50), index=True)      # 业务唯一标识
    url = Column(Text)                             # 图片预览 URL
    image_prompt = Column(Text)                    # 生成提示词
    
    # 🌟 核心新增：添加 target 字段，默认值为 1（1代表激活，0代表失效/废弃）
    target = Column(Integer, default=1) 
    
    target_page = Column(Integer, nullable=True)     # 目标幻灯片页码
    position_code = Column(String(20), nullable=True) # 排版占位符编码
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("SessionContext", back_populates="images")

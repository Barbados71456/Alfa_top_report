from sqlalchemy import Column, Integer, String, Float, Date, Boolean
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    email = Column(String, nullable=True)
    role = Column(String, default="user")  # admin или user
    is_active = Column(Boolean, default=True)
    created_at = Column(Date, server_default='now()')

class FinanceData(Base):
    __tablename__ = "finance_data"
    
    id = Column(Integer, primary_key=True, index=True)
    распределение = Column(String)  # "до распределения" или "распределение"
    статья = Column(String)
    сумма = Column(Float)
    период = Column(Date)
    признак = Column(String)
    категория = Column(String)
    проект = Column(String)
    контрагент = Column(String)
    тип_кошелька = Column(String)
    кошелек = Column(String)
    комментарии = Column(String)
    поток = Column(String)
    pl = Column(String)  # P&L
    ue = Column(String)  # UE
    статьяуровень0 = Column(String)
    статьяуровень1 = Column(String)
    статьяуровень2 = Column(String)
    статьяуровень3 = Column(String)
    статьяуровень4 = Column(String)
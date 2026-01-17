from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username}>'


class FinancialData(db.Model):
    __tablename__ = 'FinancialData'
    
    id = db.Column(db.Integer, primary_key=True)
    Распределение = db.Column(db.String(100))
    Статья = db.Column(db.String(255))
    Сумма = db.Column(db.Float)
    Период = db.Column(db.Date)
    Признак = db.Column(db.String(100))
    Категория = db.Column(db.String(100))
    Проект = db.Column(db.String(255))
    Контрагент = db.Column(db.String(255))
    Тип_Кошелька = db.Column('Тип Кошелька', db.String(100))
    Кошелек = db.Column(db.String(100))
    Комментарии = db.Column(db.Text)
    Поток = db.Column(db.String(100))
    P_L = db.Column('P&L', db.String(100))
    UE = db.Column(db.String(100))
    СтатьяУровень0 = db.Column(db.String(255))
    СтатьяУровень1 = db.Column(db.String(255))
    СтатьяУровень2 = db.Column(db.String(255))
    СтатьяУровень3 = db.Column(db.String(255))
    СтатьяУровень4 = db.Column(db.String(255))
    
    def __repr__(self):
        return f'<FinancialData {self.Проект}: {self.Сумма}>'
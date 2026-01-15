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
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def __repr__(self):
        return f'<User {self.username}>'


class FinancialData(db.Model):
    __tablename__ = 'financial_data'
    
    id = db.Column(db.Integer, primary_key=True)
    Период = db.Column(db.Date, nullable=False)
    Проект = db.Column(db.String(255))
    СтатьяУровень1 = db.Column(db.String(255))
    СтатьяУровень2 = db.Column(db.String(255))
    СтатьяУровень4 = db.Column(db.String(255))
    Сумма = db.Column(db.Float, nullable=False)
    Распределение = db.Column(db.String(50))
    Комментарии = db.Column(db.Text)
    Создано = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<FinancialData {self.Проект}: {self.Сумма}>'


class ProjectMetrics(db.Model):
    __tablename__ = 'project_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    project = db.Column(db.String(255), nullable=False)
    group = db.Column(db.String(50))
    income = db.Column(db.Float, default=0.0)
    expense = db.Column(db.Float, default=0.0)
    net = db.Column(db.Float, default=0.0)
    margin = db.Column(db.Float, default=0.0)
    roi = db.Column(db.Float, default=0.0)
    employees = db.Column(db.Integer, default=0)
    fot_total = db.Column(db.Float, default=0.0)
    period = db.Column(db.Date, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProjectMetrics {self.project}: {self.net}>'
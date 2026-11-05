import os
from datetime import datetime
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# переменные из env
load_dotenv()

# приложение фласк
app = Flask(__name__)

# значения из переменного окружения
db_user = os.getenv('DB_USER', 'CHandZH')
db_password = os.getenv('DB_PASSWORD', 'cat123')
db_host = os.getenv('DB_HOST', 'localhost')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'CHandZH_db')

# строка подключения
app.config['SQLALCHEMY_DATABASE_URI'] = (f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# модель Visit
class Visit(db.Model):
    __tablename__ = 'visits'  # имя таблицы в БД
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))

# создание таблицы
with app.app_context():
    db.create_all()

# GET /hello 
@app.route('/hello', methods=['GET'])
def hello():
    current_time = datetime.now()
    client_ip = request.remote_addr
    new_visit = Visit(timestamp=current_time, ip_address=client_ip)
    db.session.add(new_visit)
    db.session.commit()
    
    return "Hello", 200

# запуск приложения
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
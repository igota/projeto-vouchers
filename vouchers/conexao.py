# conexao.py
import os
import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv

load_dotenv()

# Configuração do pool
pool = PooledDB(
    creator=pymysql,
    host=os.environ['DB_HOST'],
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD'],
    database=os.environ['DB_NAME'],
    autocommit=True,
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor,
# Configurações otimizadas:
    maxconnections=20,      # Máximo de conexões
    mincached=3,           # Mínimo em cache
    maxcached=7,           # Máximo em cache  
    maxusage=100,          # Reutiliza conexões
    blocking=True,         # Espera se pool cheio
    ping=1,                # Verifica conexão ao reutilizar
)

def get_db_connection():
    return pool.connection()
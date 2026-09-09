import os

# 0.0.0.0 porque dentro do container só a rede interna do Docker alcança essa
# porta (o Nginx é quem publica 80/443 pro host). Rodando fora de Docker,
# apontar GUNICORN_BIND=127.0.0.1:8000 para não expor a porta na rede.
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", 3))
worker_class = "sync"
timeout = 60
accesslog = "-"
errorlog = "-"

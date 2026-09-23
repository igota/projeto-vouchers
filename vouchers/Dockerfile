FROM python:3.11-slim

# python:3.11-slim não vem com tzdata — sem isso TZ fica ignorado e o
# container roda em UTC, deixando timestamps (ultimo_acesso, data_impressao
# etc.) 3h adiantados em relação ao horário de Fortaleza/CE.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=America/Fortaleza

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]

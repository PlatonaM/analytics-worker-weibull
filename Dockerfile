FROM  platonam/data-science-base:latest

RUN apt-get update && apt-get install -y git

RUN mkdir /db && mkdir /data_cache

WORKDIR /usr/src/app

COPY . .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

EXPOSE 80

CMD ["gunicorn", "-b", "0.0.0.0:80", "--workers", "1", "--threads", "4", "--worker-class", "gthread", "--log-level", "warning", "--timeout", "250", "app:app"]

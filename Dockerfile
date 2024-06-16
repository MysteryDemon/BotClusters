FROM python:3.11-slim-buster

WORKDIR /app
RUN apt-get update && apt-get upgrade -y && apt-get install git jq -y

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

RUN bash run.sh
CMD flask run -h 0.0.0.0 -p 10000 & python3 ping_server.py & python3 worker.py

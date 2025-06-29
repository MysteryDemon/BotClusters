FROM mysterydemon/botclusters:master

WORKDIR /app
COPY install.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install.sh
RUN /usr/local/bin/install.sh

RUN uv venv --system-site-packages
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD ["python3", "cluster.py"]

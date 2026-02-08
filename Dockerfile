FROM mysterydemon/botclusters:av1an

WORKDIR /app
COPY install.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install.sh
RUN /usr/local/bin/install.sh

COPY requirements.txt ./
RUN echo "supervisor" >> requirements.tx
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD ["python3", "cluster.py"]

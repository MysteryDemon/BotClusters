FROM python:3.10-slim-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends  
RUN apt-get install -y gcc python3-dev mediainfo libsm6 libxext6 libfontconfig1 libxrender1 libgl1-mesa-glx g++ make wget pv jq git supervisor && rm -rf /var/lib/apt/lists/*
   
ENV SUPERVISORD_CONF_DIR=/etc/supervisor/conf.d
ENV SUPERVISORD_LOG_DIR=/var/log/supervisor

RUN mkdir -p ${SUPERVISORD_CONF_DIR} \
    ${SUPERVISORD_LOG_DIR} \
    /app
    
WORKDIR /app

COPY install.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install.sh

COPY requirements.txt ./
RUN echo "supervisor" >> requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /bin/ffmpeg
COPY --from=mwader/static-ffmpeg:7.1 /ffprobe /bin/ffprobe
COPY . .

EXPOSE 5000
CMD ["python3", "cluster.py"]

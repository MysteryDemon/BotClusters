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

RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/64/) && \
    wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux${arch}-gpl-7.1.tar.xz && tar -xvf *xz && cp *7.1/bin/* /usr/bin && rm -rf *xz && rm -rf *7.1
    
COPY requirements.txt ./
RUN echo "supervisor" >> requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD ["python3", "cluster.py"]

FROM fedora:42

RUN dnf -y update && \
    dnf -y install \
    g++ make wget pv git bash xz \
    python3.10 python3.10-devel \
    mediainfo psmisc procps-ng supervisor && \
    dnf clean all

RUN python3.10 -m ensurepip --upgrade && \
    python3.10 -m pip install --upgrade pip setuptools

RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.10 1

RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/64/) && \
    wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux${arch}-gpl-7.1.tar.xz && \
    tar -xvf *xz && cp *7.1/bin/* /usr/bin && rm -rf *xz && rm -rf *7.1

COPY install.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install.sh

COPY requirements.txt ./
RUN echo "supervisor" >> requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . ./

EXPOSE 5000
CMD ["python3", "cluster.py"]

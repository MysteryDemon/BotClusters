FROM fedora:42

RUN dnf -qq -y update && \
    dnf -qq -y install g++ make wget pv git bash xz python3.12 python3.12-pip mediainfo psmisc procps-ng supervisor && \
    if [[ $(arch) == 'aarch64' ]]; then dnf -qq -y install gcc python3.12-devel; fi && \
    dnf clean all
RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/64/) && \
    wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux${arch}-gpl-7.1.tar.xz && tar -xvf *xz && cp *7.1/bin/* /usr/bin && rm -rf *xz && rm -rf *7.1
    
COPY install.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install.sh

COPY requirements.txt ./
RUN echo "supervisor" >> requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN if [[ $(arch) == 'aarch64' ]]; then   dnf -qq -y history undo last; fi && dnf clean all
COPY . .

EXPOSE 5000
CMD ["python3", "cluster.py"]

FROM fedora:42

# Update system and install necessary packages
RUN dnf -y update && \
    dnf -y install \
    g++ make wget pv git bash xz \
    python3.12 python3.12-pip python3.12-devel \
    mediainfo psmisc procps-ng supervisor && \
    dnf clean all

# Set Python 3.12 as the default
RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.12 1

# Upgrade pip and setuptools
RUN python3 -m pip install --upgrade pip setuptools

# Download and install FFmpeg
RUN arch=$(arch | sed s/aarch64/arm64/ | sed s/x86_64/64/) && \
    wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-linux${arch}-gpl-7.1.tar.xz && \
    tar -xvf *xz && cp *7.1/bin/* /usr/bin && rm -rf *xz && rm -rf *7.1

# Copy and set up the install script
COPY install.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/install.sh

# Install Python dependencies
COPY requirements.txt ./
RUN echo "supervisor" >> requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the application port
EXPOSE 5000

# Set the default command
CMD ["python3", "cluster.py"]

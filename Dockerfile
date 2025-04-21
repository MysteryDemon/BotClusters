FROM fedora:42

ENV PYTHON_VERSION=3.9

RUN dnf -y update && \
    dnf -y install \
    g++ make wget pv git bash xz \
    python${PYTHON_VERSION} python${PYTHON_VERSION}-devel \
    mediainfo psmisc procps-ng supervisor && \
    dnf clean all

RUN python${PYTHON_VERSION} -m ensurepip --upgrade && \
    python${PYTHON_VERSION} -m pip install --upgrade pip setuptools && \
    alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1 && \
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip${PYTHON_VERSION} 1

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
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
RUN if [[ $(arch) == 'aarch64' ]]; then   dnf -qq -y history undo last; fi && dnf clean all
CMD ["python3", "cluster.py"]

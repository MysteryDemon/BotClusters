#!/bin/bash
set -e
usage() {
    echo "Usage: $0 [--apt-packages \"pkg1 pkg2...\"] [--pip-packages \"pkg1 pkg2...\"]"
    exit 1
}

APT_PACKAGES="ngnix"
PIP_PACKAGES="pytest gunicorn gallery-dl"

while [[ $# -gt 0 ]]; do
    case $1 in
        --apt-packages)
            APT_PACKAGES="$2"
            shift 2
            ;;
        --pip-packages)
            PIP_PACKAGES="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

if [ ! -z "$APT_PACKAGES" ]; then
    echo "Installing apt packages: $APT_PACKAGES"
    apt-get update
    echo "$APT_PACKAGES" | xargs apt-get install -y
fi

if [ ! -z "$PIP_PACKAGES" ]; then
    echo "Installing pip packages: $PIP_PACKAGES"
    which pip >/dev/null || apt-get install -y python3-pip
    echo "$PIP_PACKAGES" | xargs pip install
fi

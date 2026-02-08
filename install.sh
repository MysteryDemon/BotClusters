#!/bin/bash
set -e

usage() {
    echo "Usage: $0 [--dnf-packages \"pkg1 pkg2...\"] [--pip-packages \"pkg1 pkg2...\"]"
    exit 1
}

DNF_PACKAGES="nano"
PIP_PACKAGES="croniter python-dateutil apscheduler"

echo "[INFO] Starting install.sh script"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dnf-packages)
            DNF_PACKAGES="$2"
            echo "[INFO] Overriding DNF packages to install: $DNF_PACKAGES"
            shift 2
            ;;
        --pip-packages)
            PIP_PACKAGES="$2"
            echo "[INFO] Overriding PIP packages to install: $PIP_PACKAGES"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

if [ ! -z "$DNF_PACKAGES" ]; then
    echo "[INFO] Updating DNF repositories"
    dnf -y update || echo "[WARN] dnf update failed, continuing..."
    echo "[INFO] Installing DNF packages: $DNF_PACKAGES"
    echo "$DNF_PACKAGES" | xargs dnf install -y || echo "[WARN] dnf install failed, continuing..."
    echo "[INFO] DNF packages installed (with possible warnings)"
fi

if [ ! -z "$PIP_PACKAGES" ]; then
    echo "[INFO] Checking for pip3"
    if ! command -v pip3 &> /dev/null; then
        echo "[INFO] pip3 not found, installing python3-pip"
        dnf install -y python3-pip
    fi
    echo "[INFO] Installing pip packages: $PIP_PACKAGES"
    echo "$PIP_PACKAGES" | xargs pip3 install
    echo "[INFO] PIP packages installed successfully"
fi

echo "[INFO] install.sh script completed"

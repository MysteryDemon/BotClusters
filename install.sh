#!/bin/bash
set -e

usage() {
    echo "Usage: $0 [--dnf-packages \"pkg1 pkg2...\"] [--pip-packages \"pkg1 pkg2...\"]"
    exit 1
}

DNF_PACKAGES="nginx"
PIP_PACKAGES="pytest gunicorn gallery-dl"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dnf-packages)
            DNF_PACKAGES="$2"
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

if [ ! -z "$DNF_PACKAGES" ]; then
    echo "Installing dnf packages: $DNF_PACKAGES"
    dnf -y update
    echo "$DNF_PACKAGES" | xargs dnf install -y
fi

if [ ! -z "$PIP_PACKAGES" ]; then
    echo "Installing pip packages: $PIP_PACKAGES"
    if ! command -v pip >/dev/null 2>&1; then
        echo "pip not found, installing python3-pip..."
        dnf install -y python3-pip
    fi
    echo "$PIP_PACKAGES" | xargs pip install
fi

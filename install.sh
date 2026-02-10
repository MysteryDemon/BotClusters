#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: $0 [--pacman-packages \"pkg1 pkg2...\"] [--pip-packages \"pkg1 pkg2...\"] [--venv-path /path/to/venv] [--system-pip]"
  exit 1
}

PACMAN_PACKAGES="nano"
PIP_PACKAGES="croniter python-dateutil apscheduler"

# By default on Arch, install pip packages into a venv to avoid "externally-managed-environment" issues
VENV_PATH="/opt/app/.venv"
USE_SYSTEM_PIP=0

echo "[INFO] Starting install.sh (Arch Linux)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pacman-packages)
      PACMAN_PACKAGES="$2"
      echo "[INFO] Overriding pacman packages to install: $PACMAN_PACKAGES"
      shift 2
      ;;
    --pip-packages)
      PIP_PACKAGES="$2"
      echo "[INFO] Overriding pip packages to install: $PIP_PACKAGES"
      shift 2
      ;;
    --venv-path)
      VENV_PATH="$2"
      echo "[INFO] Using venv path: $VENV_PATH"
      shift 2
      ;;
    --system-pip)
      USE_SYSTEM_PIP=1
      echo "[WARN] Using system pip (may be blocked by Arch's externally-managed Python policy)"
      shift 1
      ;;
    -h|--help)
      usage
      ;;
    *)
      usage
      ;;
  esac
done

# Ensure we're on Arch-like system with pacman
if ! command -v pacman &>/dev/null; then
  echo "[ERROR] pacman not found. This script is for Arch Linux (or Arch-based distros)."
  exit 1
fi

# Install pacman packages
if [[ -n "${PACMAN_PACKAGES// }" ]]; then
  echo "[INFO] Updating pacman repositories"
  pacman -Syu --noconfirm

  echo "[INFO] Installing pacman packages: $PACMAN_PACKAGES"
  # shellcheck disable=SC2086
  pacman -S --noconfirm --needed $PACMAN_PACKAGES
  echo "[INFO] pacman packages installed successfully"
fi

# Install pip packages
if [[ -n "${PIP_PACKAGES// }" ]]; then
  echo "[INFO] Checking for python/pip tooling"

  if [[ "$USE_SYSTEM_PIP" -eq 1 ]]; then
    # System pip path (may require --break-system-packages depending on your Arch setup)
    pacman -S --noconfirm --needed python python-pip

    echo "[INFO] Installing pip packages globally: $PIP_PACKAGES"
    # Try normal first; if blocked, retry with --break-system-packages
    if ! echo "$PIP_PACKAGES" | xargs -r pip install; then
      echo "[WARN] Global pip install blocked; retrying with --break-system-packages"
      echo "$PIP_PACKAGES" | xargs -r pip install --break-system-packages
    fi
  else
    # Recommended: venv
    pacman -S --noconfirm --needed python python-pip

    echo "[INFO] Creating/using venv at: $VENV_PATH"
    mkdir -p "$(dirname "$VENV_PATH")"
    python -m venv "$VENV_PATH"

    echo "[INFO] Upgrading pip in venv"
    "$VENV_PATH/bin/pip" install --upgrade pip

    echo "[INFO] Installing pip packages into venv: $PIP_PACKAGES"
    echo "$PIP_PACKAGES" | xargs -r "$VENV_PATH/bin/pip" install

    echo "[INFO] PIP packages installed successfully (venv)"
    echo "[INFO] To use them: source \"$VENV_PATH/bin/activate\""
  fi
fi

echo "[INFO] install.sh script completed"

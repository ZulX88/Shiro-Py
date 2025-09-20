#!/usr/bin/env bash
set -e

echo "[INFO] Deteksi OS..."

if [ -f /etc/debian_version ]; then
    echo "[INFO] Detected Debian/Ubuntu"
    sudo apt update -y
    sudo apt upgrade -y
    sudo apt install libmagic1 python3 python3-pip git ffmpeg -y

elif [ -f /etc/arch-release ]; then
    echo "[INFO] Detected Arch Linux"
    sudo pacman -Syu --noconfirm
    sudo pacman -S --noconfirm file python python-pip git ffmpeg

elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "[INFO] Detected macOS"
    if ! command -v brew &> /dev/null; then
        echo "[INFO] Homebrew tidak ditemukan. Menginstal..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew update
    brew install libmagic python git ffmpeg

else
    echo "[ERROR] OS tidak dikenali. Install manual dependencies:"
    echo "libmagic, python3, pip, git, ffmpeg"
    exit 1
fi
echo "[INFO] Cloning repo..."
git clone "https://github.com/ZulX88/Shiro-Py"
cd Shiro-Py
echo "[INFO] Install Python dependencies..."
pip install --break-system-packages -r requirements.txt || pip install -r requirements.txt

echo "[INFO] Done!"

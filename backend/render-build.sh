#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing system dependencies..."
# Update apt and install Tesseract OCR (Phase 2 Requirement)
apt-get update && apt-get install -y tesseract-ocr

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

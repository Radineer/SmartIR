#!/bin/bash

# SadTalker Setup Script
# This script clones SadTalker repository and downloads required models

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SADTALKER_DIR="$PROJECT_ROOT/sadtalker"

echo "========================================"
echo "SadTalker Setup Script"
echo "========================================"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed"
    exit 1
fi

# Clone SadTalker repository
if [ ! -d "$SADTALKER_DIR" ]; then
    echo "Cloning SadTalker repository..."
    git clone https://github.com/OpenTalker/SadTalker.git "$SADTALKER_DIR"
    echo "SadTalker cloned successfully!"
else
    echo "SadTalker directory already exists at $SADTALKER_DIR"
    echo "Updating repository..."
    cd "$SADTALKER_DIR" && git pull
fi

# Create checkpoints directory
CHECKPOINTS_DIR="$SADTALKER_DIR/checkpoints"
GFPGAN_DIR="$SADTALKER_DIR/gfpgan/weights"
mkdir -p "$CHECKPOINTS_DIR"
mkdir -p "$GFPGAN_DIR"

# Create outputs directory
OUTPUTS_DIR="$PROJECT_ROOT/outputs/sadtalker"
mkdir -p "$OUTPUTS_DIR"

# Create uploads directory
UPLOADS_DIR="$PROJECT_ROOT/uploads/sadtalker"
mkdir -p "$UPLOADS_DIR"

echo ""
echo "========================================"
echo "Downloading Model Checkpoints..."
echo "========================================"
echo ""

# Function to download file if not exists
download_if_not_exists() {
    local url="$1"
    local filepath="$2"
    local filename=$(basename "$filepath")

    if [ ! -f "$filepath" ]; then
        echo "Downloading $filename..."
        curl -L -o "$filepath" "$url"
        echo "Downloaded: $filename"
    else
        echo "Already exists: $filename"
    fi
}

# SadTalker models
echo "Downloading SadTalker models..."
download_if_not_exists \
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00109-model.pth.tar" \
    "$CHECKPOINTS_DIR/mapping_00109-model.pth.tar"

download_if_not_exists \
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00229-model.pth.tar" \
    "$CHECKPOINTS_DIR/mapping_00229-model.pth.tar"

download_if_not_exists \
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors" \
    "$CHECKPOINTS_DIR/SadTalker_V0.0.2_256.safetensors"

download_if_not_exists \
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors" \
    "$CHECKPOINTS_DIR/SadTalker_V0.0.2_512.safetensors"

# GFPGAN models for face enhancement
echo ""
echo "Downloading GFPGAN models for face enhancement..."
download_if_not_exists \
    "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth" \
    "$GFPGAN_DIR/GFPGANv1.4.pth"

download_if_not_exists \
    "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth" \
    "$GFPGAN_DIR/detection_Resnet50_Final.pth"

download_if_not_exists \
    "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth" \
    "$GFPGAN_DIR/parsing_parsenet.pth"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "SadTalker has been installed at: $SADTALKER_DIR"
echo "Model checkpoints are at: $CHECKPOINTS_DIR"
echo "Output directory: $OUTPUTS_DIR"
echo ""
echo "To use SadTalker via API:"
echo "  POST /api/sadtalker/generate"
echo "  - Upload image and audio files"
echo "  - Returns job_id for status tracking"
echo ""
echo "API Documentation: http://localhost:8000/docs#/sadtalker"
echo ""

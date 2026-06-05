#!/usr/bin/env python3
"""
Generate lip-sync video using SadTalker or alternative methods.

This script generates talking head videos from a static image and audio file.
It supports multiple backends:
1. SadTalker (requires GPU) - Best quality for realistic faces
2. Wav2Lip (requires GPU) - Good for lip-sync only
3. First Order Motion Model (requires GPU) - Good for anime

Usage:
    python scripts/generate_lipsync_video.py --image path/to/image.png --audio path/to/audio.wav --output path/to/output.mp4

Requirements:
    - CUDA-capable GPU (for SadTalker/Wav2Lip)
    - Python 3.8+
    - Required packages: torch, torchaudio, opencv-python, ffmpeg-python
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def check_gpu_available():
    """Check if CUDA GPU is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


async def generate_with_sadtalker(image_path: str, audio_path: str, output_path: str) -> bool:
    """Generate lip-sync video using SadTalker."""
    try:
        from app.services.sadtalker import sadtalker_service

        print("Checking if SadTalker models are installed...")
        if not sadtalker_service.check_models_installed():
            print("SadTalker models not found. Downloading...")
            job = sadtalker_service.create_job()
            await sadtalker_service.download_models(job.job_id)
            print("Models downloaded successfully.")

        print("Generating lip-sync video with SadTalker...")
        job = sadtalker_service.create_job()
        result = await sadtalker_service.generate_video(
            job_id=job.job_id,
            image_path=image_path,
            audio_path=audio_path,
            pose_style=0,
            expression_scale=1.0,
            enhancer="gfpgan",
            still_mode=False,
            preprocess="crop",
            size=512,
        )

        if result:
            # Move to output path
            import shutil
            shutil.move(result, output_path)
            print(f"Video generated successfully: {output_path}")
            return True
        else:
            print("SadTalker video generation failed.")
            return False

    except Exception as e:
        print(f"SadTalker error: {e}")
        return False


async def generate_with_ffmpeg_sprites(image_path: str, audio_path: str, output_path: str) -> bool:
    """
    Generate a simple animated video using FFmpeg and sprite-based animation.
    This is a fallback method that doesn't require GPU.
    """
    import subprocess
    import json

    try:
        # Get audio duration
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', audio_path],
            capture_output=True,
            text=True
        )
        audio_info = json.loads(result.stdout)
        duration = float(audio_info['format']['duration'])

        print(f"Audio duration: {duration:.2f}s")

        # Create video with simple zoom/pan effect on the image
        # This creates a Ken Burns-like effect
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', image_path,
            '-i', audio_path,
            '-filter_complex',
            f"""[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,
                pad=1920:1080:(ow-iw)/2:(oh-ih)/2,
                zoompan=z='min(zoom+0.0005,1.2)':d={int(duration*30)}:s=1920x1080:fps=30[v]""",
            '-map', '[v]',
            '-map', '1:a',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            output_path
        ]

        print("Generating video with FFmpeg...")
        subprocess.run(cmd, check=True)
        print(f"Video generated: {output_path}")
        return True

    except Exception as e:
        print(f"FFmpeg error: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Generate lip-sync video from image and audio")
    parser.add_argument("--image", required=True, help="Path to source image (PNG/JPG)")
    parser.add_argument("--audio", required=True, help="Path to audio file (WAV/MP3)")
    parser.add_argument("--output", required=True, help="Path for output video (MP4)")
    parser.add_argument("--method", choices=["auto", "sadtalker", "ffmpeg"], default="auto",
                        help="Generation method (default: auto)")
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.image):
        print(f"Error: Image not found: {args.image}")
        sys.exit(1)
    if not os.path.exists(args.audio):
        print(f"Error: Audio not found: {args.audio}")
        sys.exit(1)

    # Create output directory if needed
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    method = args.method

    if method == "auto":
        # Check GPU availability
        gpu_available = await check_gpu_available()
        if gpu_available:
            print("GPU detected, using SadTalker...")
            method = "sadtalker"
        else:
            print("No GPU detected, using FFmpeg fallback...")
            method = "ffmpeg"

    success = False
    if method == "sadtalker":
        success = await generate_with_sadtalker(args.image, args.audio, args.output)
        if not success:
            print("Falling back to FFmpeg method...")
            success = await generate_with_ffmpeg_sprites(args.image, args.audio, args.output)
    else:
        success = await generate_with_ffmpeg_sprites(args.image, args.audio, args.output)

    if success:
        print("\n✅ Video generation complete!")
        print(f"Output: {args.output}")
    else:
        print("\n❌ Video generation failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

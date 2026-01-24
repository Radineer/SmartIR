"""
SadTalker Service - Lip Sync Video Generation
Generates talking head videos from a static image and audio file
"""

import os
import sys
import subprocess
import tempfile
import shutil
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SadTalkerStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING_MODELS = "downloading_models"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SadTalkerJob:
    job_id: str
    status: SadTalkerStatus
    progress: int = 0
    output_path: Optional[str] = None
    error: Optional[str] = None


class SadTalkerService:
    """Service for generating lip-sync videos using SadTalker"""

    SADTALKER_DIR = Path(__file__).parent.parent.parent / "sadtalker"
    CHECKPOINTS_DIR = SADTALKER_DIR / "checkpoints"
    GFPGAN_DIR = SADTALKER_DIR / "gfpgan" / "weights"
    OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs" / "sadtalker"

    # Model URLs
    MODEL_URLS = {
        "sadtalker": {
            "mapping_00109-model.pth.tar": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00109-model.pth.tar",
            "mapping_00229-model.pth.tar": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00229-model.pth.tar",
            "SadTalker_V0.0.2_256.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors",
            "SadTalker_V0.0.2_512.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors",
        },
        "gfpgan": {
            "GFPGANv1.4.pth": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
            "detection_Resnet50_Final.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth",
            "parsing_parsenet.pth": "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth",
        }
    }

    def __init__(self):
        self._jobs: Dict[str, SadTalkerJob] = {}
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure output and checkpoint directories exist"""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        self.GFPGAN_DIR.mkdir(parents=True, exist_ok=True)

    def check_models_installed(self) -> bool:
        """Check if required models are downloaded"""
        required_files = [
            self.CHECKPOINTS_DIR / "SadTalker_V0.0.2_256.safetensors",
            self.CHECKPOINTS_DIR / "mapping_00109-model.pth.tar",
        ]
        return all(f.exists() for f in required_files)

    async def download_models(self, job_id: str) -> bool:
        """Download required model checkpoints"""
        try:
            self._update_job(job_id, status=SadTalkerStatus.DOWNLOADING_MODELS, progress=0)

            total_files = len(self.MODEL_URLS["sadtalker"]) + len(self.MODEL_URLS["gfpgan"])
            downloaded = 0

            # Download SadTalker models
            for filename, url in self.MODEL_URLS["sadtalker"].items():
                filepath = self.CHECKPOINTS_DIR / filename
                if not filepath.exists():
                    logger.info(f"Downloading {filename}...")
                    await self._download_file(url, filepath)
                downloaded += 1
                self._update_job(job_id, progress=int(downloaded / total_files * 100))

            # Download GFPGAN models
            for filename, url in self.MODEL_URLS["gfpgan"].items():
                filepath = self.GFPGAN_DIR / filename
                if not filepath.exists():
                    logger.info(f"Downloading {filename}...")
                    await self._download_file(url, filepath)
                downloaded += 1
                self._update_job(job_id, progress=int(downloaded / total_files * 100))

            return True
        except Exception as e:
            logger.error(f"Failed to download models: {e}")
            self._update_job(job_id, status=SadTalkerStatus.FAILED, error=str(e))
            return False

    async def _download_file(self, url: str, filepath: Path):
        """Download a file from URL"""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                with open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

    def create_job(self) -> SadTalkerJob:
        """Create a new job"""
        job_id = str(uuid.uuid4())
        job = SadTalkerJob(
            job_id=job_id,
            status=SadTalkerStatus.PENDING,
            progress=0
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[SadTalkerJob]:
        """Get job by ID"""
        return self._jobs.get(job_id)

    def _update_job(self, job_id: str, **kwargs):
        """Update job properties"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(job, key, value)

    async def generate_video(
        self,
        job_id: str,
        image_path: str,
        audio_path: str,
        pose_style: int = 0,
        batch_size: int = 2,
        expression_scale: float = 1.0,
        enhancer: Optional[str] = "gfpgan",
        still_mode: bool = False,
        preprocess: str = "crop",
        size: int = 256,
    ) -> Optional[str]:
        """
        Generate a lip-sync video from image and audio

        Args:
            job_id: Job identifier
            image_path: Path to source image
            audio_path: Path to audio file
            pose_style: Pose style (0-45)
            batch_size: Batch size for processing
            expression_scale: Expression intensity scale
            enhancer: Face enhancer ('gfpgan' or None)
            still_mode: If True, only animate the face (no head movement)
            preprocess: Preprocessing mode ('crop', 'resize', 'full')
            size: Output resolution (256 or 512)

        Returns:
            Path to generated video or None on failure
        """
        try:
            self._update_job(job_id, status=SadTalkerStatus.PROCESSING, progress=10)

            # Validate inputs
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image not found: {image_path}")
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio not found: {audio_path}")

            # Check if models are installed
            if not self.check_models_installed():
                await self.download_models(job_id)

            self._update_job(job_id, progress=20)

            # Prepare output path
            output_filename = f"{job_id}.mp4"
            output_path = self.OUTPUT_DIR / output_filename

            # Run SadTalker inference
            result = await self._run_sadtalker(
                image_path=image_path,
                audio_path=audio_path,
                output_path=str(output_path),
                pose_style=pose_style,
                batch_size=batch_size,
                expression_scale=expression_scale,
                enhancer=enhancer,
                still_mode=still_mode,
                preprocess=preprocess,
                size=size,
                job_id=job_id
            )

            if result and output_path.exists():
                self._update_job(
                    job_id,
                    status=SadTalkerStatus.COMPLETED,
                    progress=100,
                    output_path=str(output_path)
                )
                return str(output_path)
            else:
                raise Exception("Video generation failed")

        except Exception as e:
            logger.error(f"Video generation failed: {e}")
            self._update_job(job_id, status=SadTalkerStatus.FAILED, error=str(e))
            return None

    async def _run_sadtalker(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        pose_style: int,
        batch_size: int,
        expression_scale: float,
        enhancer: Optional[str],
        still_mode: bool,
        preprocess: str,
        size: int,
        job_id: str
    ) -> bool:
        """Run SadTalker inference using the installed package"""
        try:
            # Import SadTalker modules
            from src.facerender.animate import AnimateFromCoeff
            from src.generate_batch import get_data
            from src.generate_facerender_batch import get_facerender_data
            from src.test_audio2coeff import Audio2Coeff
            from src.utils.init_path import init_path
            from src.utils.preprocess import CropAndExtract

            self._update_job(job_id, progress=30)

            # Initialize paths
            sadtalker_paths = init_path(
                str(self.CHECKPOINTS_DIR),
                os.path.join(str(self.SADTALKER_DIR), "src", "config"),
                size,
                False,  # old_version
                preprocess
            )

            self._update_job(job_id, progress=40)

            # Initialize models
            preprocess_model = CropAndExtract(sadtalker_paths)
            audio_to_coeff = Audio2Coeff(sadtalker_paths)
            animate_from_coeff = AnimateFromCoeff(sadtalker_paths)

            self._update_job(job_id, progress=50)

            # Create temp directory for intermediate files
            with tempfile.TemporaryDirectory() as tmpdir:
                # Preprocess - extract face
                first_frame_dir = os.path.join(tmpdir, "first_frame")
                os.makedirs(first_frame_dir, exist_ok=True)

                first_coeff_path, crop_pic_path, crop_info = preprocess_model.generate(
                    image_path, first_frame_dir, preprocess, source_image_flag=True
                )

                if first_coeff_path is None:
                    raise Exception("Failed to detect face in image")

                self._update_job(job_id, progress=60)

                # Audio to coefficients
                batch = get_data(
                    first_coeff_path, audio_path, batch_size,
                    expression_scale, still_mode, preprocess
                )
                coeff_path = audio_to_coeff.generate(batch, tmpdir, pose_style)

                self._update_job(job_id, progress=75)

                # Generate video
                data = get_facerender_data(
                    coeff_path, crop_pic_path, first_coeff_path,
                    audio_path, batch_size,
                    expression_scale, still_mode, preprocess
                )

                result = animate_from_coeff.generate(
                    data, tmpdir,
                    enhancer=enhancer,
                    full_img_path=image_path if preprocess == 'full' else None,
                    fps=25
                )

                self._update_job(job_id, progress=90)

                # Copy result to output path
                if result and os.path.exists(result):
                    shutil.copy2(result, output_path)
                    return True

            return False

        except ImportError as e:
            logger.warning(f"SadTalker modules not available, using subprocess: {e}")
            return await self._run_sadtalker_subprocess(
                image_path, audio_path, output_path,
                pose_style, batch_size, expression_scale,
                enhancer, still_mode, preprocess, size, job_id
            )
        except Exception as e:
            logger.error(f"SadTalker inference failed: {e}")
            raise

    async def _run_sadtalker_subprocess(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        pose_style: int,
        batch_size: int,
        expression_scale: float,
        enhancer: Optional[str],
        still_mode: bool,
        preprocess: str,
        size: int,
        job_id: str
    ) -> bool:
        """Run SadTalker as subprocess (fallback method)"""
        import asyncio

        inference_script = self.SADTALKER_DIR / "inference.py"

        if not inference_script.exists():
            raise FileNotFoundError(
                f"SadTalker not found at {self.SADTALKER_DIR}. "
                "Please run the setup script first."
            )

        cmd = [
            sys.executable,
            str(inference_script),
            "--driven_audio", audio_path,
            "--source_image", image_path,
            "--result_dir", str(self.OUTPUT_DIR),
            "--pose_style", str(pose_style),
            "--batch_size", str(batch_size),
            "--expression_scale", str(expression_scale),
            "--preprocess", preprocess,
            "--size", str(size),
        ]

        if enhancer:
            cmd.extend(["--enhancer", enhancer])
        if still_mode:
            cmd.append("--still")

        self._update_job(job_id, progress=30)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.SADTALKER_DIR)
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"SadTalker subprocess failed: {error_msg}")
            raise Exception(f"SadTalker failed: {error_msg}")

        # Find and move the output file
        output_files = list(self.OUTPUT_DIR.glob("*.mp4"))
        if output_files:
            latest = max(output_files, key=os.path.getctime)
            if str(latest) != output_path:
                shutil.move(str(latest), output_path)
            return True

        return False

    def cleanup_job(self, job_id: str):
        """Clean up job resources"""
        job = self._jobs.get(job_id)
        if job and job.output_path and os.path.exists(job.output_path):
            os.remove(job.output_path)
        if job_id in self._jobs:
            del self._jobs[job_id]


# Global service instance
sadtalker_service = SadTalkerService()

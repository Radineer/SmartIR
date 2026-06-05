"""
SadTalker API - Lip Sync Video Generation Endpoints
"""

import os
import shutil
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.sadtalker import sadtalker_service, SadTalkerStatus

router = APIRouter(prefix="/api/sadtalker", tags=["sadtalker"])

# Upload directory for temporary files
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "sadtalker"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class GenerateRequest(BaseModel):
    """Request model for video generation with file paths"""
    image_path: str = Field(..., description="Path to source image")
    audio_path: str = Field(..., description="Path to audio file")
    pose_style: int = Field(0, ge=0, le=45, description="Pose style (0-45)")
    batch_size: int = Field(2, ge=1, le=8, description="Batch size")
    expression_scale: float = Field(1.0, ge=0.0, le=3.0, description="Expression intensity")
    enhancer: Optional[str] = Field("gfpgan", description="Face enhancer (gfpgan or null)")
    still_mode: bool = Field(False, description="Still mode - only animate face")
    preprocess: str = Field("crop", description="Preprocessing mode (crop, resize, full)")
    size: int = Field(256, description="Output size (256 or 512)")


class JobResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    status: str
    progress: int
    output_path: Optional[str] = None
    error: Optional[str] = None


class StatusResponse(BaseModel):
    """Response model for SadTalker status"""
    models_installed: bool
    sadtalker_dir: str
    checkpoints_dir: str
    output_dir: str


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Check SadTalker installation status"""
    return StatusResponse(
        models_installed=sadtalker_service.check_models_installed(),
        sadtalker_dir=str(sadtalker_service.SADTALKER_DIR),
        checkpoints_dir=str(sadtalker_service.CHECKPOINTS_DIR),
        output_dir=str(sadtalker_service.OUTPUT_DIR)
    )


@router.post("/download-models", response_model=JobResponse)
async def download_models(background_tasks: BackgroundTasks):
    """Download required model checkpoints"""
    job = sadtalker_service.create_job()

    async def download_task():
        await sadtalker_service.download_models(job.job_id)

    background_tasks.add_task(download_task)

    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress
    )


@router.post("/generate", response_model=JobResponse)
async def generate_video(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="Source face image"),
    audio: UploadFile = File(..., description="Audio file (wav/mp3)"),
    pose_style: int = Form(0, ge=0, le=45),
    batch_size: int = Form(2, ge=1, le=8),
    expression_scale: float = Form(1.0, ge=0.0, le=3.0),
    enhancer: Optional[str] = Form("gfpgan"),
    still_mode: bool = Form(False),
    preprocess: str = Form("crop"),
    size: int = Form(256),
):
    """
    Generate lip-sync video from uploaded image and audio

    - **image**: Source face image (PNG, JPG)
    - **audio**: Audio file (WAV, MP3)
    - **pose_style**: Pose variation style (0-45)
    - **batch_size**: Processing batch size
    - **expression_scale**: Expression intensity multiplier
    - **enhancer**: Face enhancement (gfpgan or null)
    - **still_mode**: Only animate face, no head movement
    - **preprocess**: crop, resize, or full
    - **size**: Output resolution (256 or 512)
    """
    # Create job
    job = sadtalker_service.create_job()
    job_dir = UPLOAD_DIR / job.job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save uploaded files
        image_path = job_dir / f"image{Path(image.filename).suffix}"
        audio_path = job_dir / f"audio{Path(audio.filename).suffix}"

        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

        # Start background generation
        async def generate_task():
            try:
                await sadtalker_service.generate_video(
                    job_id=job.job_id,
                    image_path=str(image_path),
                    audio_path=str(audio_path),
                    pose_style=pose_style,
                    batch_size=batch_size,
                    expression_scale=expression_scale,
                    enhancer=enhancer if enhancer != "null" else None,
                    still_mode=still_mode,
                    preprocess=preprocess,
                    size=size,
                )
            finally:
                # Cleanup uploaded files
                if job_dir.exists():
                    shutil.rmtree(job_dir)

        background_tasks.add_task(generate_task)

        return JobResponse(
            job_id=job.job_id,
            status=job.status.value,
            progress=job.progress
        )

    except Exception as e:
        # Cleanup on error
        if job_dir.exists():
            shutil.rmtree(job_dir)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-from-path", response_model=JobResponse)
async def generate_video_from_path(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Generate lip-sync video from file paths (for server-side files)

    Useful for integrating with existing audio/image generation pipelines
    """
    # Validate paths
    if not os.path.exists(request.image_path):
        raise HTTPException(status_code=404, detail=f"Image not found: {request.image_path}")
    if not os.path.exists(request.audio_path):
        raise HTTPException(status_code=404, detail=f"Audio not found: {request.audio_path}")

    # Create job
    job = sadtalker_service.create_job()

    async def generate_task():
        await sadtalker_service.generate_video(
            job_id=job.job_id,
            image_path=request.image_path,
            audio_path=request.audio_path,
            pose_style=request.pose_style,
            batch_size=request.batch_size,
            expression_scale=request.expression_scale,
            enhancer=request.enhancer if request.enhancer != "null" else None,
            still_mode=request.still_mode,
            preprocess=request.preprocess,
            size=request.size,
        )

    background_tasks.add_task(generate_task)

    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress
    )


@router.get("/job/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Get job status and progress"""
    job = sadtalker_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        output_path=job.output_path,
        error=job.error
    )


@router.get("/download/{job_id}")
async def download_video(job_id: str):
    """Download generated video"""
    job = sadtalker_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != SadTalkerStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job.status.value}"
        )

    if not job.output_path or not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        job.output_path,
        media_type="video/mp4",
        filename=f"sadtalker_{job_id}.mp4"
    )


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete job and cleanup resources"""
    job = sadtalker_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sadtalker_service.cleanup_job(job_id)
    return {"message": "Job deleted successfully"}

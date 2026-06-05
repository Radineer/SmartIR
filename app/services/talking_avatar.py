"""
Talking Avatar Service - D-ID / HeyGen / Hedra Integration
Generates lip-synced talking avatar videos from static images and audio/text.
"""

import os
import asyncio
import aiohttp
import base64
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AvatarProvider(str, Enum):
    DID = "d-id"
    HEYGEN = "heygen"
    HEDRA = "hedra"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TalkingAvatarJob:
    job_id: str
    provider: AvatarProvider
    status: JobStatus
    progress: int = 0
    video_url: Optional[str] = None
    local_path: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# D-ID
# ---------------------------------------------------------------------------

class DIDService:
    """D-ID API integration for talking avatar generation.

    Docs: https://docs.d-id.com/
    Authentication: Basic auth with the API key.
    Flow: POST /talks -> poll GET /talks/{id} -> get result_url.
    """

    BASE_URL = "https://api.d-id.com"

    def __init__(self):
        self.api_key = os.getenv("DID_API_KEY")
        self.enabled = self.api_key is not None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }

    # -- unified interface ---------------------------------------------------

    async def create_video(
        self,
        text: str,
        avatar_url: str,
        voice_id: Optional[str] = None,
    ) -> str:
        """Create a talking-head video and return the job id.

        Args:
            text: Script text to speak.
            avatar_url: Public URL of the source portrait image.
            voice_id: Optional voice identifier (e.g. "en-US-JennyNeural").
                      Defaults to D-ID's default voice when *None*.

        Returns:
            The talk id used to poll for results.

        Raises:
            RuntimeError: When the API key is missing or the request fails.
        """
        if not self.enabled:
            raise RuntimeError("D-ID API key not configured (set DID_API_KEY)")

        script: Dict[str, Any] = {
            "type": "text",
            "input": text,
        }
        if voice_id:
            script["provider"] = {"type": "microsoft", "voice_id": voice_id}

        payload: Dict[str, Any] = {
            "source_url": avatar_url,
            "script": script,
            "config": {
                "stitch": True,
                "result_format": "mp4",
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/talks",
                headers=self._get_headers(),
                json=payload,
            ) as resp:
                body = await resp.json()
                if resp.status == 201:
                    job_id = body.get("id")
                    logger.info("D-ID talk created: %s", job_id)
                    return job_id
                error_msg = body.get("description") or body.get("message") or str(body)
                logger.error("D-ID create_video failed (%s): %s", resp.status, error_msg)
                raise RuntimeError(f"D-ID create_video failed: {error_msg}")

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """Poll the status of a talk generation job.

        Returns:
            {"status": JobStatus, "video_url": str | None, "error": str | None}
        """
        if not self.enabled:
            return {"status": JobStatus.FAILED, "video_url": None, "error": "API key not configured"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/talks/{job_id}",
                headers=self._get_headers(),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("D-ID get_status failed (%s): %s", resp.status, error_text)
                    return {"status": JobStatus.FAILED, "video_url": None, "error": error_text}

                data = await resp.json()

        # D-ID statuses: created, started, done, error, rejected
        raw = data.get("status", "")
        if raw == "done":
            return {
                "status": JobStatus.COMPLETED,
                "video_url": data.get("result_url"),
                "error": None,
            }
        elif raw in ("error", "rejected"):
            return {
                "status": JobStatus.FAILED,
                "video_url": None,
                "error": data.get("error", {}).get("description", raw),
            }
        else:
            return {
                "status": JobStatus.PROCESSING,
                "video_url": None,
                "error": None,
            }

    # -- legacy helpers (kept for backward compat) ---------------------------

    async def create_talk(
        self,
        image_url: str,
        audio_url: str,
        driver_url: str = "bank://lively",
    ) -> Optional[str]:
        """Create a talk from a pre-existing audio URL (legacy interface)."""
        if not self.enabled:
            logger.error("D-ID API key not configured")
            return None

        payload = {
            "source_url": image_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url,
            },
            "driver_url": driver_url,
            "config": {
                "stitch": True,
                "result_format": "mp4",
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/talks",
                headers=self._get_headers(),
                json=payload,
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    return data.get("id")
                error = await resp.text()
                logger.error("D-ID create_talk failed: %s", error)
                return None

    async def get_talk_status(self, talk_id: str) -> Dict[str, Any]:
        """Get raw status dict (legacy interface)."""
        if not self.enabled:
            return {"status": "error", "error": "API key not configured"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/talks/{talk_id}",
                headers=self._get_headers(),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"status": "error", "error": await resp.text()}

    async def wait_for_completion(
        self,
        talk_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> Optional[str]:
        """Block until the talk finishes and return the video URL (legacy)."""
        elapsed = 0
        while elapsed < timeout:
            status = await self.get_talk_status(talk_id)
            if status.get("status") == "done":
                return status.get("result_url")
            elif status.get("status") in ("error", "rejected"):
                logger.error("D-ID talk failed: %s", status.get("error"))
                return None
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        logger.error("D-ID talk timed out after %ss", timeout)
        return None


# ---------------------------------------------------------------------------
# HeyGen
# ---------------------------------------------------------------------------

class HeyGenService:
    """HeyGen API integration for talking avatar generation.

    Docs: https://docs.heygen.com/
    Authentication: X-Api-Key header.
    Flow: POST /v2/video/generate -> poll GET /v1/video_status.get -> get video_url.
    """

    BASE_URL = "https://api.heygen.com"

    def __init__(self):
        self.api_key = os.getenv("HEYGEN_API_KEY")
        self.enabled = self.api_key is not None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    # -- unified interface ---------------------------------------------------

    async def create_video(
        self,
        text: str,
        avatar_url: str,
        voice_id: Optional[str] = None,
    ) -> str:
        """Create a talking avatar video.

        Args:
            text: Script text to speak.
            avatar_url: Public URL of the talking photo image.
            voice_id: Optional HeyGen voice id (e.g. "en-US-MonicaNeural").
                      When *None* the default HeyGen voice is used.

        Returns:
            The video_id for polling.

        Raises:
            RuntimeError: On missing key or request failure.
        """
        if not self.enabled:
            raise RuntimeError("HeyGen API key not configured (set HEYGEN_API_KEY)")

        voice_cfg: Dict[str, Any] = {"type": "text", "input_text": text}
        if voice_id:
            voice_cfg["voice_id"] = voice_id

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "talking_photo",
                        "talking_photo_url": avatar_url,
                    },
                    "voice": voice_cfg,
                }
            ],
            "dimension": {"width": 1080, "height": 1920},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/v2/video/generate",
                headers=self._get_headers(),
                json=payload,
            ) as resp:
                body = await resp.json()
                if resp.status == 200:
                    video_id = body.get("data", {}).get("video_id")
                    if video_id:
                        logger.info("HeyGen video created: %s", video_id)
                        return video_id
                error_msg = body.get("message") or body.get("error") or str(body)
                logger.error("HeyGen create_video failed (%s): %s", resp.status, error_msg)
                raise RuntimeError(f"HeyGen create_video failed: {error_msg}")

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """Poll the status of a video generation job.

        Returns:
            {"status": JobStatus, "video_url": str | None, "error": str | None}
        """
        if not self.enabled:
            return {"status": JobStatus.FAILED, "video_url": None, "error": "API key not configured"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/v1/video_status.get",
                headers=self._get_headers(),
                params={"video_id": job_id},
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("HeyGen get_status failed (%s): %s", resp.status, error_text)
                    return {"status": JobStatus.FAILED, "video_url": None, "error": error_text}

                body = await resp.json()

        data = body.get("data", {})
        raw = data.get("status", "")

        if raw == "completed":
            return {
                "status": JobStatus.COMPLETED,
                "video_url": data.get("video_url"),
                "error": None,
            }
        elif raw == "failed":
            return {
                "status": JobStatus.FAILED,
                "video_url": None,
                "error": data.get("error", raw),
            }
        elif raw == "pending":
            return {
                "status": JobStatus.PENDING,
                "video_url": None,
                "error": None,
            }
        else:  # processing / other
            return {
                "status": JobStatus.PROCESSING,
                "video_url": None,
                "error": None,
            }


# ---------------------------------------------------------------------------
# Hedra
# ---------------------------------------------------------------------------

class HedraService:
    """Hedra API integration for talking avatar generation.

    Docs: https://docs.hedra.com/
    Authentication: Bearer token via X-API-Key header.
    Flow: POST /v1/characters -> poll GET /v1/characters/{id} -> get video_url.
    """

    BASE_URL = "https://mercury.dev.dream-ai.com/api"

    def __init__(self):
        self.api_key = os.getenv("HEDRA_API_KEY")
        self.enabled = self.api_key is not None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_video(
        self,
        text: str,
        avatar_url: str,
        voice_id: Optional[str] = None,
    ) -> str:
        """Create a character video generation job.

        Args:
            text: Script text to speak.
            avatar_url: Public URL of the character image.
            voice_id: Optional voice identifier. Defaults to Hedra's default.

        Returns:
            The job/project id for polling.

        Raises:
            RuntimeError: On missing key or request failure.
        """
        if not self.enabled:
            raise RuntimeError("Hedra API key not configured (set HEDRA_API_KEY)")

        payload: Dict[str, Any] = {
            "text": text,
            "voice_id": voice_id or "default",
            "character_image_url": avatar_url,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}/v1/characters",
                headers=self._get_headers(),
                json=payload,
            ) as resp:
                body = await resp.json()
                if resp.status in (200, 201):
                    job_id = body.get("jobId") or body.get("id")
                    if job_id:
                        logger.info("Hedra generation created: %s", job_id)
                        return job_id
                error_msg = body.get("message") or body.get("error") or str(body)
                logger.error("Hedra create_video failed (%s): %s", resp.status, error_msg)
                raise RuntimeError(f"Hedra create_video failed: {error_msg}")

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """Poll the status of a character generation job.

        Returns:
            {"status": JobStatus, "video_url": str | None, "error": str | None}
        """
        if not self.enabled:
            return {"status": JobStatus.FAILED, "video_url": None, "error": "API key not configured"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/v1/characters/{job_id}",
                headers=self._get_headers(),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("Hedra get_status failed (%s): %s", resp.status, error_text)
                    return {"status": JobStatus.FAILED, "video_url": None, "error": error_text}

                body = await resp.json()

        raw = body.get("status", "")

        if raw in ("completed", "done"):
            return {
                "status": JobStatus.COMPLETED,
                "video_url": body.get("videoUrl") or body.get("video_url"),
                "error": None,
            }
        elif raw in ("failed", "error"):
            return {
                "status": JobStatus.FAILED,
                "video_url": None,
                "error": body.get("errorMessage") or body.get("error") or raw,
            }
        elif raw in ("pending", "queued"):
            return {
                "status": JobStatus.PENDING,
                "video_url": None,
                "error": None,
            }
        else:  # processing / rendering / etc.
            return {
                "status": JobStatus.PROCESSING,
                "video_url": None,
                "error": None,
            }


# ---------------------------------------------------------------------------
# Unified Router / Factory
# ---------------------------------------------------------------------------

class TalkingAvatarService:
    """
    Unified service for generating talking avatar videos.
    Supports multiple providers: D-ID, HeyGen, Hedra.

    Usage::

        svc = TalkingAvatarService()
        job_id = await svc.generate("d-id", "Hello world", "https://example.com/face.png")
        result = await svc.get_status("d-id", job_id)
        # result == {"status": JobStatus.COMPLETED, "video_url": "https://..."}
    """

    OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs" / "avatars"

    def __init__(self):
        self.did = DIDService()
        self.heygen = HeyGenService()
        self.hedra = HedraService()
        self._providers: Dict[AvatarProvider, Any] = {
            AvatarProvider.DID: self.did,
            AvatarProvider.HEYGEN: self.heygen,
            AvatarProvider.HEDRA: self.hedra,
        }
        self._jobs: Dict[str, TalkingAvatarJob] = {}
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -- provider resolution -------------------------------------------------

    def _resolve_provider(self, provider: str | AvatarProvider) -> Any:
        """Return the provider service instance or raise."""
        if isinstance(provider, str):
            provider = AvatarProvider(provider)
        svc = self._providers.get(provider)
        if svc is None:
            raise ValueError(f"Unknown provider: {provider}")
        if not svc.enabled:
            raise RuntimeError(f"Provider {provider.value} is not configured (API key missing)")
        return svc, provider

    # -- public API ----------------------------------------------------------

    def get_available_providers(self) -> list[AvatarProvider]:
        """Return providers whose API keys are set in the environment."""
        return [p for p, svc in self._providers.items() if svc.enabled]

    async def generate(
        self,
        provider: str | AvatarProvider,
        text: str,
        avatar_image_url: str,
        voice_id: Optional[str] = None,
    ) -> str:
        """Create a talking avatar video with the specified provider.

        Args:
            provider: One of "d-id", "heygen", "hedra" (or the enum).
            text: The script / text to speak.
            avatar_image_url: Public URL to the source portrait image.
            voice_id: Optional provider-specific voice identifier.

        Returns:
            A job id that can be polled with :meth:`get_status`.

        Raises:
            ValueError: Unknown provider.
            RuntimeError: Provider not configured or API error.
        """
        svc, prov_enum = self._resolve_provider(provider)
        job_id = await svc.create_video(text, avatar_image_url, voice_id)

        # Track internally
        self._jobs[job_id] = TalkingAvatarJob(
            job_id=job_id,
            provider=prov_enum,
            status=JobStatus.PENDING,
        )
        logger.info("Job %s created via %s", job_id, prov_enum.value)
        return job_id

    async def get_status(
        self,
        provider: str | AvatarProvider,
        job_id: str,
    ) -> Dict[str, Any]:
        """Check the current status of a generation job.

        Args:
            provider: The provider that owns this job.
            job_id: The id returned by :meth:`generate`.

        Returns:
            {"status": JobStatus, "video_url": str | None, "error": str | None}
        """
        svc, prov_enum = self._resolve_provider(provider)
        result = await svc.get_status(job_id)

        # Keep internal cache in sync
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.status = result["status"]
            job.video_url = result.get("video_url")
            job.error = result.get("error")

        return result

    async def wait_for_completion(
        self,
        provider: str | AvatarProvider,
        job_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> Optional[str]:
        """Block until the job completes and return the video URL.

        Args:
            provider: The provider that owns this job.
            job_id: The id returned by :meth:`generate`.
            timeout: Max wait in seconds.
            poll_interval: Seconds between polls.

        Returns:
            The video URL on success, *None* on failure or timeout.
        """
        elapsed = 0
        while elapsed < timeout:
            result = await self.get_status(provider, job_id)
            status = result["status"]

            if status == JobStatus.COMPLETED:
                video_url = result.get("video_url")
                logger.info("Job %s completed: %s", job_id, video_url)
                return video_url
            elif status == JobStatus.FAILED:
                logger.error("Job %s failed: %s", job_id, result.get("error"))
                return None

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        logger.error("Job %s timed out after %ss", job_id, timeout)
        return None

    # -- legacy interface (kept for backward compat) -------------------------

    async def generate_video(
        self,
        image_path: str,
        audio_path: str,
        provider: AvatarProvider = AvatarProvider.DID,
        image_url: Optional[str] = None,
        audio_url: Optional[str] = None,
    ) -> Optional[str]:
        """Legacy method: generate video from pre-uploaded audio URL.

        Prefer :meth:`generate` + :meth:`wait_for_completion` for new code.
        """
        if not image_url or not audio_url:
            logger.warning(
                "For D-ID/HeyGen, files must be accessible via public URLs. "
                "Please provide image_url and audio_url parameters."
            )
            return None

        if provider == AvatarProvider.DID:
            if not self.did.enabled:
                logger.error("D-ID not configured. Set DID_API_KEY env var.")
                return None
            talk_id = await self.did.create_talk(image_url, audio_url)
            if not talk_id:
                return None
            video_url = await self.did.wait_for_completion(talk_id)
            if video_url:
                output_path = self.OUTPUT_DIR / f"did_{talk_id}.mp4"
                await self._download_video(video_url, output_path)
                return str(output_path)

        elif provider == AvatarProvider.HEYGEN:
            if not self.heygen.enabled:
                logger.error("HeyGen not configured. Set HEYGEN_API_KEY env var.")
                return None
            video_id = await self.heygen.create_video(
                text="",  # audio_url 使用時はテキスト不要
                avatar_url=image_url,
                voice_id=audio_url,  # legacy: audio URL をvoice_idに渡す
            )
            if not video_id:
                return None
            for _ in range(60):
                result = await self.heygen.get_status(video_id)
                if result["status"] == JobStatus.COMPLETED:
                    video_url = result.get("video_url")
                    if video_url:
                        output_path = self.OUTPUT_DIR / f"heygen_{video_id}.mp4"
                        await self._download_video(video_url, output_path)
                        return str(output_path)
                elif result["status"] == JobStatus.FAILED:
                    logger.error("HeyGen video failed: %s", result.get("error"))
                    return None
                await asyncio.sleep(5)

        return None

    async def _download_video(self, url: str, output_path: Path):
        """Download video from URL to local file."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    logger.info("Downloaded video to %s", output_path)
                else:
                    logger.error("Failed to download video (%s): %s", response.status, url)


# Global service instance
talking_avatar_service = TalkingAvatarService()


# CLI usage example
if __name__ == "__main__":
    print("Talking Avatar Service")
    print("=" * 50)
    print("\nAvailable providers:")

    service = TalkingAvatarService()
    providers = service.get_available_providers()

    if not providers:
        print("  No providers configured!")
        print("\nTo enable providers, set environment variables:")
        print("  - DID_API_KEY:    Get from https://www.d-id.com/")
        print("  - HEYGEN_API_KEY: Get from https://www.heygen.com/")
        print("  - HEDRA_API_KEY:  Get from https://www.hedra.com/")
    else:
        for p in providers:
            print(f"  - {p.value}")

    print("\nUsage (new API):")
    print("  from app.services.talking_avatar import talking_avatar_service as svc")
    print('  job_id = await svc.generate("d-id", "Hello!", "https://.../face.png")')
    print('  result = await svc.get_status("d-id", job_id)')
    print('  # or block: url = await svc.wait_for_completion("d-id", job_id)')

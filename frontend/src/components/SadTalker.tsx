"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  SadTalkerJob,
  SadTalkerGenerateParams,
  SadTalkerStatusResponse,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SadTalkerProps {
  audioUrl?: string;
  onVideoGenerated?: (videoUrl: string) => void;
}

export default function SadTalker({
  audioUrl,
  onVideoGenerated,
}: SadTalkerProps) {
  const [status, setStatus] = useState<SadTalkerStatusResponse | null>(null);
  const [job, setJob] = useState<SadTalkerJob | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [params, setParams] = useState<SadTalkerGenerateParams>({
    pose_style: 0,
    expression_scale: 1.0,
    enhancer: "gfpgan",
    still_mode: false,
    preprocess: "crop",
    size: 256,
  });

  const imageInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Check SadTalker status on mount
  useEffect(() => {
    checkStatus();
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/sadtalker/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error("Failed to check SadTalker status:", err);
    }
  };

  const downloadModels = async () => {
    try {
      setError(null);
      const res = await fetch(`${API_BASE}/api/sadtalker/download-models`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setJob(data);
        startPolling(data.job_id);
      }
    } catch (err) {
      setError("Failed to start model download");
    }
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => setImagePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleAudioSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAudioFile(file);
    }
  };

  const startPolling = useCallback((jobId: string) => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
    }

    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/sadtalker/job/${jobId}`);
        if (res.ok) {
          const data: SadTalkerJob = await res.json();
          setJob(data);

          if (data.status === "completed") {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setIsGenerating(false);
            const url = `${API_BASE}/api/sadtalker/download/${jobId}`;
            setVideoUrl(url);
            onVideoGenerated?.(url);
            checkStatus();
          } else if (data.status === "failed") {
            clearInterval(pollingRef.current!);
            pollingRef.current = null;
            setIsGenerating(false);
            setError(data.error || "Generation failed");
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000);
  }, [onVideoGenerated]);

  const generateVideo = async () => {
    if (!imageFile) {
      setError("Please select an image");
      return;
    }

    if (!audioFile && !audioUrl) {
      setError("Please select an audio file or provide an audio URL");
      return;
    }

    setIsGenerating(true);
    setError(null);
    setVideoUrl(null);

    try {
      const formData = new FormData();
      formData.append("image", imageFile);

      if (audioFile) {
        formData.append("audio", audioFile);
      } else if (audioUrl) {
        // Fetch audio from URL and add to form data
        const audioRes = await fetch(audioUrl);
        const audioBlob = await audioRes.blob();
        formData.append("audio", audioBlob, "audio.wav");
      }

      formData.append("pose_style", String(params.pose_style || 0));
      formData.append("expression_scale", String(params.expression_scale || 1.0));
      formData.append("enhancer", params.enhancer || "gfpgan");
      formData.append("still_mode", String(params.still_mode || false));
      formData.append("preprocess", params.preprocess || "crop");
      formData.append("size", String(params.size || 256));

      const res = await fetch(`${API_BASE}/api/sadtalker/generate`, {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data: SadTalkerJob = await res.json();
        setJob(data);
        startPolling(data.job_id);
      } else {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Generation failed");
      }
    } catch (err) {
      setIsGenerating(false);
      setError(err instanceof Error ? err.message : "Generation failed");
    }
  };

  return (
    <div className="bg-gray-900 rounded-xl p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white">
          SadTalker - Lip Sync Video
        </h2>
        {status && (
          <span
            className={`px-3 py-1 rounded-full text-sm ${
              status.models_installed
                ? "bg-green-500/20 text-green-400"
                : "bg-yellow-500/20 text-yellow-400"
            }`}
          >
            {status.models_installed ? "Ready" : "Models Required"}
          </span>
        )}
      </div>

      {!status?.models_installed && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <p className="text-yellow-400 mb-3">
            SadTalker models need to be downloaded first.
          </p>
          <button
            onClick={downloadModels}
            disabled={isGenerating}
            className="px-4 py-2 bg-yellow-500 text-black rounded-lg hover:bg-yellow-400 transition disabled:opacity-50"
          >
            Download Models
          </button>
        </div>
      )}

      {/* Image Upload */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-300">
          Source Image (Face)
        </label>
        <div className="flex items-center gap-4">
          <input
            ref={imageInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            className="hidden"
          />
          <button
            onClick={() => imageInputRef.current?.click()}
            className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition"
          >
            Select Image
          </button>
          {imageFile && (
            <span className="text-gray-400 text-sm">{imageFile.name}</span>
          )}
        </div>
        {imagePreview && (
          <div className="mt-2">
            <img
              src={imagePreview}
              alt="Preview"
              className="w-32 h-32 object-cover rounded-lg"
            />
          </div>
        )}
      </div>

      {/* Audio Upload */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-300">
          Audio File
        </label>
        <div className="flex items-center gap-4">
          <input
            ref={audioInputRef}
            type="file"
            accept="audio/*"
            onChange={handleAudioSelect}
            className="hidden"
          />
          <button
            onClick={() => audioInputRef.current?.click()}
            className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition"
          >
            Select Audio
          </button>
          {audioFile && (
            <span className="text-gray-400 text-sm">{audioFile.name}</span>
          )}
          {audioUrl && !audioFile && (
            <span className="text-green-400 text-sm">Using generated audio</span>
          )}
        </div>
      </div>

      {/* Parameters */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Pose Style (0-45)
          </label>
          <input
            type="number"
            min={0}
            max={45}
            value={params.pose_style}
            onChange={(e) =>
              setParams({ ...params, pose_style: parseInt(e.target.value) })
            }
            className="w-full px-3 py-2 bg-gray-800 text-white rounded-lg border border-gray-700"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Expression Scale
          </label>
          <input
            type="number"
            min={0}
            max={3}
            step={0.1}
            value={params.expression_scale}
            onChange={(e) =>
              setParams({
                ...params,
                expression_scale: parseFloat(e.target.value),
              })
            }
            className="w-full px-3 py-2 bg-gray-800 text-white rounded-lg border border-gray-700"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Resolution
          </label>
          <select
            value={params.size}
            onChange={(e) =>
              setParams({ ...params, size: parseInt(e.target.value) as 256 | 512 })
            }
            className="w-full px-3 py-2 bg-gray-800 text-white rounded-lg border border-gray-700"
          >
            <option value={256}>256px</option>
            <option value={512}>512px (Higher Quality)</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Preprocess
          </label>
          <select
            value={params.preprocess}
            onChange={(e) =>
              setParams({
                ...params,
                preprocess: e.target.value as "crop" | "resize" | "full",
              })
            }
            className="w-full px-3 py-2 bg-gray-800 text-white rounded-lg border border-gray-700"
          >
            <option value="crop">Crop</option>
            <option value="resize">Resize</option>
            <option value="full">Full</option>
          </select>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-gray-300">
          <input
            type="checkbox"
            checked={params.still_mode}
            onChange={(e) =>
              setParams({ ...params, still_mode: e.target.checked })
            }
            className="rounded"
          />
          Still Mode (Face only)
        </label>
        <label className="flex items-center gap-2 text-gray-300">
          <input
            type="checkbox"
            checked={params.enhancer === "gfpgan"}
            onChange={(e) =>
              setParams({ ...params, enhancer: e.target.checked ? "gfpgan" : null })
            }
            className="rounded"
          />
          Face Enhancement (GFPGAN)
        </label>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Progress */}
      {job && isGenerating && (
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-400">
            <span>
              {job.status === "downloading_models"
                ? "Downloading models..."
                : "Generating video..."}
            </span>
            <span>{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-purple-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Generate Button */}
      <button
        onClick={generateVideo}
        disabled={isGenerating || !imageFile || (!audioFile && !audioUrl)}
        className="w-full py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-bold rounded-lg hover:from-purple-600 hover:to-pink-600 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isGenerating ? "Generating..." : "Generate Lip Sync Video"}
      </button>

      {/* Video Preview */}
      {videoUrl && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-white">Generated Video</h3>
          <video
            src={videoUrl}
            controls
            className="w-full rounded-lg"
            autoPlay
          />
          <a
            href={videoUrl}
            download
            className="inline-block px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition"
          >
            Download Video
          </a>
        </div>
      )}
    </div>
  );
}

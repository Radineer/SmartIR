"use client";

import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Environment } from "@react-three/drei";
import { useVRM } from "@/hooks/useVRM";
import { VRMAvatar } from "./VRMAvatar";

interface VRMViewerProps {
  modelUrl: string;
  viseme?: { a: number; i: number; u: number; e: number; o: number };
  expression?: string;
  className?: string;
}

function VRMModel({ modelUrl, viseme, expression }: Omit<VRMViewerProps, "className">) {
  const { vrm, loading, error } = useVRM(modelUrl);

  if (loading) return null;
  if (error) return null;
  if (!vrm) return null;

  return <VRMAvatar vrm={vrm} viseme={viseme} expression={expression} />;
}

export function VRMViewer({ modelUrl, viseme, expression, className }: VRMViewerProps) {
  return (
    <div className={className}>
      <Canvas
        camera={{ position: [0, 1.5, 2], fov: 30 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[1, 2, 1]} intensity={1} />
        <Suspense fallback={null}>
          <VRMModel modelUrl={modelUrl} viseme={viseme} expression={expression} />
        </Suspense>
        <OrbitControls target={[0, 1, 0]} />
        <Environment preset="studio" />
      </Canvas>
    </div>
  );
}

"use client";

import { useRef, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import { VRM } from "@pixiv/three-vrm";
import * as THREE from "three";

interface VRMAvatarProps {
  vrm: VRM;
  viseme?: { a: number; i: number; u: number; e: number; o: number };
  expression?: string;
}

export function VRMAvatar({ vrm, viseme, expression }: VRMAvatarProps) {
  const groupRef = useRef<THREE.Group>(null);

  // 表情制御
  useEffect(() => {
    if (!vrm.expressionManager || !expression) return;
    // リセット
    vrm.expressionManager.setValue("happy", 0);
    vrm.expressionManager.setValue("sad", 0);
    vrm.expressionManager.setValue("angry", 0);
    // 設定
    vrm.expressionManager.setValue(expression, 1);
  }, [vrm, expression]);

  // リップシンク
  useFrame(() => {
    if (!vrm.expressionManager || !viseme) return;
    vrm.expressionManager.setValue("aa", viseme.a);
    vrm.expressionManager.setValue("ih", viseme.i);
    vrm.expressionManager.setValue("ou", viseme.u);
    vrm.expressionManager.setValue("ee", viseme.e);
    vrm.expressionManager.setValue("oh", viseme.o);
    vrm.update(0.016);
  });

  return (
    <group ref={groupRef}>
      <primitive object={vrm.scene} />
    </group>
  );
}

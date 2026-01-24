"use client";

import { useState, useEffect } from "react";
import { VRM, VRMLoaderPlugin } from "@pixiv/three-vrm";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export function useVRM(url: string) {
  const [vrm, setVrm] = useState<VRM | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      url,
      (gltf) => {
        const vrm = gltf.userData.vrm as VRM;
        vrm.scene.rotation.y = Math.PI;
        setVrm(vrm);
        setLoading(false);
      },
      undefined,
      (err) => {
        setError(err as Error);
        setLoading(false);
      }
    );
  }, [url]);

  return { vrm, loading, error };
}

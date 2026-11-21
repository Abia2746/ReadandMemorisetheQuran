"use client";
import { useEffect } from "react";
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    void navigator.serviceWorker.register("/sw.js").catch(() => {
      // Degraded offline capability must never block the core reader.
    });
  }, []);
  return null;
}

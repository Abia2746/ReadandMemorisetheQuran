import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Al-Mu'allim — Qur'an Learning",
    short_name: "Al-Mu'allim",
    description: "Qur'an reading, memorisation, Arabic learning and revision.",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#1A120D",
    theme_color: "#1A120D",
    lang: "en",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
  };
}

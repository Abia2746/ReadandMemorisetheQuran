import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ServiceWorkerRegistration } from "@/components/shell/ServiceWorkerRegistration";
export const metadata: Metadata = {
  title: "Al-Mu'allim · Your Qur'an companion",
  description: "Read, listen, memorise, understand and revise Qur'an at your own pace.",
  applicationName: "Al-Mu'allim",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Al-Mu'allim" },
  formatDetection: { telephone: false },
};
export const viewport: Viewport = {
  width: "device-width", initialScale: 1, themeColor: "#1A120D",
  viewportFit: "cover",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning>
    <body>
      <ServiceWorkerRegistration />
      {children}
      <footer className="am-global-footer">
        <strong>Al-Mu&apos;allim</strong> · Qur&apos;an study at your own pace
        <div className="mt-1">QuranLife word timings (CC BY 4.0) · EveryAyah recitations · AI practice is not certified Tajweed assessment.</div>
      </footer>
    </body>
  </html>;
}

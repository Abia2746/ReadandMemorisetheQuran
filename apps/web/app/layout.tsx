import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Amiri, Amiri_Quran, DM_Sans, Playfair_Display } from "next/font/google";
const fontQuran=Amiri_Quran({subsets:["arabic"],weight:"400",display:"swap",variable:"--loaded-amiri-quran"});
const fontAmiri=Amiri({subsets:["arabic"],weight:["400","700"],display:"swap",variable:"--loaded-amiri"});
const fontSans=DM_Sans({subsets:["latin"],display:"swap",variable:"--loaded-dm-sans"});
const fontEditorial=Playfair_Display({subsets:["latin"],display:"swap",variable:"--loaded-playfair"});
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
    <body className={[fontQuran.variable,fontAmiri.variable,fontSans.variable,fontEditorial.variable].join(" ")}>
      <ServiceWorkerRegistration />
      {children}
      <footer className="am-global-footer">
        <strong>Al-Mu&apos;allim</strong> · Qur&apos;an study at your own pace
        <div className="mt-1">QuranLife word timings (CC BY 4.0) · EveryAyah recitations · AI practice is not certified Tajweed assessment.</div>
      </footer>
    </body>
  </html>;
}

import type { CapacitorConfig } from "@capacitor/cli";
const config: CapacitorConfig = {
  appId: "org.almuallim.study",
  appName: "Al-Mu'allim",
  webDir: "out",
  server: { androidScheme: "https" },
  ios: { contentInset: "automatic" },
};
export default config;

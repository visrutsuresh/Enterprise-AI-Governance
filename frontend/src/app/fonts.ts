import localFont from "next/font/local";

export const gsans = localFont({
  src: [
    { path: "./fonts/GeneralSans-Regular.woff2", weight: "400" },
    { path: "./fonts/GeneralSans-Medium.woff2", weight: "500" },
    { path: "./fonts/GeneralSans-Semibold.woff2", weight: "600" },
  ],
  variable: "--font-gsans",
});

export const cabinet = localFont({
  src: [
    { path: "./fonts/CabinetGrotesk-Bold.woff2", weight: "700" },
    { path: "./fonts/CabinetGrotesk-Extrabold.woff2", weight: "800" },
  ],
  variable: "--font-cabinet",
});

export const array = localFont({
  src: [
    { path: "./fonts/Array-Regular.woff2", weight: "400" },
    { path: "./fonts/Array-Semibold.woff2", weight: "600" },
  ],
  variable: "--font-array",
});

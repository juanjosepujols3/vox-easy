import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dictado - Speech to Text",
  description: "Transcribe tu voz a texto de manera rápida y precisa",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" data-theme="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}

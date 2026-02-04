import "../globals.css";

export default function RecordingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" data-theme="dark" style={{ background: "transparent" }}>
      <body style={{ background: "transparent", margin: 0, padding: 0 }}>
        {children}
      </body>
    </html>
  );
}

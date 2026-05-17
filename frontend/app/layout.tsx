import "./globals.css";

export const metadata = {
  title: "Tax-Copilot",
  description: "세무사를 위한 AI 영수증 검토 워크플로우",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

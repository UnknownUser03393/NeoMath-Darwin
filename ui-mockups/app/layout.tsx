import type { Metadata } from "next";
import { headers } from "next/headers";
/* App chrome first; KaTeX CSS last so radicals/operators keep their fonts. */
import "./globals.css";
import "katex/dist/katex.min.css";

export async function generateMetadata(): Promise<Metadata> {
  const headerStore = await headers();
  const host = headerStore.get("host") ?? "localhost:3000";
  const protocol =
    headerStore.get("x-forwarded-proto") ?? (host.includes("localhost") ? "http" : "https");
  const imageUrl = `${protocol}://${host}/og.png`;
  const title = "NeoMath · 可执行数学 Notebook";
  const description = "逐步运行方程变形，检查解集、等价性与反例。";

  return {
    title,
    description,
    icons: {
      icon: "/favicon.svg",
      shortcut: "/favicon.svg",
    },
    openGraph: {
      title,
      description,
      type: "website",
      images: [{ url: imageUrl, width: 1200, height: 630, alt: "NeoMath Notebook 执行流" }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [imageUrl],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

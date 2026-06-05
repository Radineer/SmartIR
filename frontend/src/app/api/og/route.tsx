import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title") || "AI-IR Insight";
  const subtitle = searchParams.get("subtitle") || "AIによるIR資料分析";
  const ticker = searchParams.get("ticker");

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#1e40af",
          backgroundImage: "linear-gradient(135deg, #1e40af 0%, #3b82f6 100%)",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "white",
            borderRadius: 20,
            padding: 60,
            margin: 40,
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
          }}
        >
          {ticker && (
            <div
              style={{
                fontSize: 32,
                fontWeight: 500,
                color: "#6b7280",
                marginBottom: 10,
              }}
            >
              {ticker}
            </div>
          )}
          <div
            style={{
              fontSize: 60,
              fontWeight: 800,
              color: "#111827",
              textAlign: "center",
              maxWidth: 900,
              lineHeight: 1.2,
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontSize: 28,
              color: "#6b7280",
              marginTop: 20,
              textAlign: "center",
            }}
          >
            {subtitle}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              marginTop: 40,
              gap: 10,
            }}
          >
            <div
              style={{
                fontSize: 24,
                fontWeight: 700,
                color: "#2563eb",
              }}
            >
              AI-IR Insight
            </div>
            <div
              style={{
                fontSize: 20,
                color: "#9ca3af",
              }}
            >
              - AIによるIR資料分析プラットフォーム
            </div>
          </div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
    }
  );
}

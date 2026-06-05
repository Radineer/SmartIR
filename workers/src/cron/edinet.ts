import { getSupabase, type Env } from "../lib/supabase";

const EDINET_API = "https://api.edinet-fsa.go.jp/api/v2/documents.json";

interface EDINETDoc {
  company_code: string;
  title: string;
  source_url: string;
  publish_date: string;
  doc_type: string;
}

async function fetchEDINETFeed(): Promise<EDINETDoc[]> {
  // Fetch today's EDINET submissions
  const today = new Date().toISOString().slice(0, 10);
  const url = `${EDINET_API}?date=${today}&type=2`;

  const res = await fetch(url, {
    headers: { "User-Agent": "SmartIR/1.0" },
  });

  if (!res.ok) {
    console.error(`EDINET fetch failed: ${res.status}`);
    return [];
  }

  const json = (await res.json()) as {
    results?: Array<{
      secCode?: string;
      filerName?: string;
      docDescription?: string;
      docID?: string;
      submitDateTime?: string;
      docTypeCode?: string;
    }>;
  };

  const items: EDINETDoc[] = [];

  for (const doc of json.results || []) {
    if (!doc.secCode) continue;

    // Map EDINET doc type codes to our types
    let docType = "other";
    if (["120", "130"].includes(doc.docTypeCode || "")) {
      docType = "securities_report"; // 有価証券報告書
    } else if (["140", "150"].includes(doc.docTypeCode || "")) {
      docType = "quarterly_report"; // 四半期報告書
    }

    items.push({
      company_code: doc.secCode.slice(0, -1), // Remove check digit
      title: doc.docDescription || doc.filerName || "",
      source_url: `https://disclosure.edinet-fsa.go.jp/api/v2/documents/${doc.docID}?type=1`,
      publish_date: today,
      doc_type: docType,
    });
  }

  return items;
}

export async function handleEDINETCron(env: Env): Promise<void> {
  console.log("Running EDINET cron job");
  const supabase = getSupabase(env);

  const items = await fetchEDINETFeed();
  console.log(`Fetched ${items.length} items from EDINET`);

  let savedCount = 0;
  for (const item of items) {
    const { data: company } = await supabase
      .from("companies")
      .select("id")
      .eq("ticker_code", item.company_code)
      .single();

    if (!company) continue;

    const { data: existing } = await supabase
      .from("documents")
      .select("id")
      .eq("source_url", item.source_url)
      .single();

    if (existing) continue;

    const { error } = await supabase.from("documents").insert({
      company_id: company.id,
      title: item.title,
      doc_type: item.doc_type,
      publish_date: item.publish_date,
      source_url: item.source_url,
    });

    if (!error) savedCount++;
  }

  console.log(`EDINET cron completed. Saved ${savedCount} new documents`);
}

import { getSupabase, type Env } from "../lib/supabase";

const TDNET_API = "https://www.release.tdnet.info/inbs/I_list_001_00.html";

interface TDNetItem {
  company_code: string;
  title: string;
  source_url: string;
  publish_date: string;
  doc_type: string;
}

async function fetchTDNetFeed(): Promise<TDNetItem[]> {
  // TDnet RSS/HTML scraping - lightweight fetch only
  // Parse the TDnet disclosure list page
  const res = await fetch(TDNET_API, {
    headers: { "User-Agent": "SmartIR/1.0" },
  });

  if (!res.ok) {
    console.error(`TDnet fetch failed: ${res.status}`);
    return [];
  }

  const html = await res.text();
  const items: TDNetItem[] = [];

  // Parse disclosure items from HTML
  // TDnet format: each row has company code, title, PDF link, date
  const rows = html.match(/<tr[^>]*class="[^"]*even-color[^"]*"[^>]*>[\s\S]*?<\/tr>/gi) || [];

  for (const row of rows) {
    const codeMatch = row.match(/(\d{4,5})/);
    const linkMatch = row.match(/href="([^"]*\.pdf)"/i);
    const titleMatch = row.match(/<td[^>]*>([^<]+)<\/td>/g);

    if (codeMatch && linkMatch && titleMatch) {
      const title = titleMatch[1]?.replace(/<[^>]*>/g, "").trim() || "";
      items.push({
        company_code: codeMatch[1],
        title,
        source_url: linkMatch[1].startsWith("http")
          ? linkMatch[1]
          : `https://www.release.tdnet.info/inbs/${linkMatch[1]}`,
        publish_date: new Date().toISOString().slice(0, 10),
        doc_type: title.includes("決算") ? "earnings" : "other",
      });
    }
  }

  return items;
}

export async function handleTDNetCron(env: Env): Promise<void> {
  console.log("Running TDnet cron job");
  const supabase = getSupabase(env);

  const items = await fetchTDNetFeed();
  console.log(`Fetched ${items.length} items from TDnet`);

  let savedCount = 0;
  for (const item of items) {
    // Look up company
    const { data: company } = await supabase
      .from("companies")
      .select("id")
      .eq("ticker_code", item.company_code)
      .single();

    if (!company) continue;

    // Dedup check
    const { data: existing } = await supabase
      .from("documents")
      .select("id")
      .eq("source_url", item.source_url)
      .single();

    if (existing) continue;

    // Insert
    const { error } = await supabase.from("documents").insert({
      company_id: company.id,
      title: item.title,
      doc_type: item.doc_type,
      publish_date: item.publish_date,
      source_url: item.source_url,
    });

    if (!error) savedCount++;
  }

  console.log(`TDnet cron completed. Saved ${savedCount} new documents`);
}

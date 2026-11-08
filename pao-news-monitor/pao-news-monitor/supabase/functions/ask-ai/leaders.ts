// Leadership questions ("who is their president?") get two extra, dated sources:
//  - Leaders on file: President / Deputy / Vice Presidents, names only, read by the daily collection
//    from the organisation's own leadership page (update-19.sql, collector/leaders.py)
//  - the lines the daily page watch saved from that leadership page
// Both are public pages; nothing else about the people is stored or shown.

export const LEADERSHIP_Q = new RegExp(
  "\\b(presidents?|vice[\\s-]?presidents?|deputy presidents?|vps?|chair(?:man|person|woman)?|ceo|chief executive|" +
    "secretary[\\s-]general|director[\\s-]general|leaders?|leadership|council|board|office[\\s-]?bearers?|" +
    "who (?:runs|leads|heads))\\b",
  "i",
);

export function isLeadershipQuestion(...texts: (string | undefined | null)[]): boolean {
  return texts.some((t) => !!t && LEADERSHIP_Q.test(t));
}

export type Leader = { pao_id: string; role: string; name: string; source_url?: string | null; as_of?: string | null };
export type LeaderPage = { url: string; snapshot?: string | null; last_checked_at?: string | null };

const ROLE_ORDER = ["President", "Deputy President", "Vice President"];
const PAGE_CHARS = 1200;   // keeps the prompt inside Groq's per-minute token allowance
const byRole = (a: Leader, b: Leader) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role);

const HOW_TO_USE = `For questions about who leads an organisation: answer from the leaders on file (and any saved page \
text) and write "(leadership page, read <date>)" instead of an item number. If a numbered news item or the background on \
file gives a different or newer name, give both with their dates and point out the difference - an organisation's website \
can lag behind an election. If nothing here names the person asked about, say you don't know rather than guessing.`;

/** One organisation: its leaders on file plus the newest saved leadership page text. */
export function leadersBlock(name: string, leaders: Leader[], pages: LeaderPage[]): string {
  const lines = [...leaders].sort(byRole)
    .map((l) => `- ${l.role}: ${l.name} (from ${l.source_url || "its leadership page"}, read ${l.as_of || "on an unknown date"})`);
  const page = pages.filter((p) => p.snapshot?.trim())
    .sort((a, b) => (b.last_checked_at ?? "").localeCompare(a.last_checked_at ?? ""))[0];
  let out = `
Leaders on file for ${name} (names only, read automatically from the organisation's own leadership page; may be out of date):
${lines.length ? lines.join("\n") : "(none on file yet)"}
`;
  if (page) {
    out += `
Lines saved from ${name}'s leadership page ${page.url} (last checked ${(page.last_checked_at ?? "").slice(0, 10) || "on an unknown date"}):
${page.snapshot!.trim().slice(0, PAGE_CHARS)}
`;
  }
  return out + "\n" + HOW_TO_USE + "\n";
}

/** Whole region: one compact line per organisation, names only. */
export function regionLeadersBlock(leaders: Leader[], abbr: Map<string, string>): string {
  if (!leaders.length) return "";
  const by = new Map<string, Leader[]>();
  for (const l of leaders) {
    if (!by.has(l.pao_id)) by.set(l.pao_id, []);
    by.get(l.pao_id)!.push(l);
  }
  const lines = [...by.entries()]
    .sort(([a], [b]) => (abbr.get(a) ?? a).localeCompare(abbr.get(b) ?? b))
    .map(([pid, ls]) => {
      const read = ls.map((l) => l.as_of ?? "").sort().at(-1) || "on an unknown date";
      return `- ${abbr.get(pid) ?? pid}: ${ls.sort(byRole).map((l) => `${l.role} ${l.name}`).join("; ")} (read ${read})`;
    });
  return `
Leaders on file (names only, read automatically from each organisation's own leadership page; may be out of date; \
organisations not listed have none on file):
${lines.join("\n")}

${HOW_TO_USE}
`;
}

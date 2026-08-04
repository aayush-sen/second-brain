const crypto = require("crypto");

function auth(req) {
  const got = Buffer.from((req.headers.authorization || "").replace(/^Bearer\s+/i, ""));
  const want = Buffer.from(process.env.PHONE_TOKEN || "");
  return want.length > 0 && got.length === want.length && crypto.timingSafeEqual(got, want);
}

async function sb(method, path, body) {
  const r = await fetch(process.env.SUPABASE_URL.replace(/\/$/, "") + path, {
    method,
    headers: {
      apikey: process.env.SUPABASE_SERVICE_KEY,
      Authorization: "Bearer " + process.env.SUPABASE_SERVICE_KEY,
      "Content-Type": "application/json",
      ...(method === "POST" ? { Prefer: "return=minimal" } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`supabase ${r.status}: ${await r.text()}`);
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}

module.exports = { auth, sb };

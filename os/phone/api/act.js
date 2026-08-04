const { auth, sb } = require("./_lib");
const KINDS = new Set(["status", "note", "log", "deadline", "deadline_add"]);

module.exports = async (req, res) => {
  if (!auth(req)) return res.status(401).json({ err: "unauthorized" });
  if (req.method !== "POST") return res.status(405).json({ err: "POST only" });
  const { kind, payload } = req.body || {};
  if (!KINDS.has(kind) || typeof payload !== "object" || payload === null)
    return res.status(400).json({ err: "bad kind or payload" });
  try {
    await sb("POST", "/rest/v1/actions", { kind, payload });
    const pending = await sb("GET", "/rest/v1/actions?applied_at=is.null&select=id");
    return res.status(200).json({ ok: true, queued: pending.length });
  } catch (e) {
    return res.status(502).json({ err: String(e) });
  }
};

const { auth, sb } = require("./_lib");

module.exports = async (req, res) => {
  if (!auth(req)) return res.status(401).json({ err: "unauthorized" });
  try {
    const rows = await sb("GET", "/rest/v1/snapshot?id=eq.1&select=data,updated_at");
    if (!rows || !rows.length)
      return res.status(503).json({ err: "no snapshot yet — is phone_sync running?" });
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json(rows[0]);
  } catch (e) {
    return res.status(502).json({ err: String(e) });
  }
};

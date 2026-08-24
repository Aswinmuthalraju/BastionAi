import express from "express";
import path from "node:path";
import http from "node:http";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;
const BACKEND_HOST = process.env.BACKEND_HOST || "localhost";
const BACKEND_PORT = process.env.BACKEND_PORT || 8000;

const DIST_DIR = path.join(__dirname, "dist");

app.use(express.static(DIST_DIR));

// Proxy API requests to the FastAPI backend — streamed both ways so large
// uploads and file downloads (document previews) aren't buffered in memory.
app.use("/v1", (req, res) => {
  const proxyReq = http.request(
    { hostname: BACKEND_HOST, port: BACKEND_PORT, path: "/v1" + req.url, method: req.method, headers: { ...req.headers, host: `${BACKEND_HOST}:${BACKEND_PORT}` } },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res, { end: true });
    },
  );

  proxyReq.on("error", () => {
    res.status(503).json({ detail: `Backend API unreachable at http://${BACKEND_HOST}:${BACKEND_PORT}` });
  });

  req.pipe(proxyReq, { end: true });
});

// SPA fallback — client-side routing handles everything else. (Express 5's
// path-to-regexp no longer accepts a bare "*" route pattern, so this is a
// path-less middleware instead.)
app.use((_req, res) => {
  res.sendFile(path.join(DIST_DIR, "index.html"));
});

app.listen(PORT, () => {
  console.log(`BastionAI frontend listening on http://localhost:${PORT}`);
});

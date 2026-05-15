import http from "node:http";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  actions,
  buildStatus,
  gatewayControllerActionBlocked,
  getGatewayControllerDiagnostics,
  getGatewayControllerPac,
  getGatewayControllerPhoneSetup,
  getGatewayControllerStatus,
  getNetworkEvents,
  getSelfCheck,
  resolveNetworkEvent,
  runAction,
  runBenchmark
} from "./links.js";
import { linuxDesktopPackageStatus } from "./linux-desktop-status.js";
import { importLinuxProfileUpload } from "./linux-profile-import.js";
import { buildLinuxProxyUnification, knownExternalProxyServices } from "./linux-proxy-unification.js";

const host = "127.0.0.1";
const port = Number(process.env.PORT || "4077");
const rootDir = resolve(fileURLToPath(new URL("..", import.meta.url)));
const distDir = join(rootDir, "dist");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".json": "application/json; charset=utf-8"
};

function publicJsonBody(value) {
  if (value instanceof Error) {
    return { error: "Internal server error" };
  }
  if (Array.isArray(value)) {
    return value.map((item) => publicJsonBody(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !/^(stack|stackTrace|trace)$/i.test(key))
        .map(([key, item]) => [key, publicJsonBody(item)])
    );
  }
  return value;
}

function sendJson(res, statusCode, body) {
  const payload = JSON.stringify(publicJsonBody(body), null, 2);
  res.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  });
  // publicJsonBody removes Error instances and stack-like fields before output.
  // codeql[js/stack-trace-exposure]
  res.end(payload);
}

function sendText(res, statusCode, body, contentType) {
  res.writeHead(statusCode, {
    "content-type": contentType,
    "cache-control": "no-store"
  });
  res.end(body);
}

async function readJson(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  if (chunks.length === 0) {
    return {};
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function staticPath(pathname) {
  const requested = pathname === "/" ? "/index.html" : pathname;
  const safePath = normalize(decodeURIComponent(requested)).replace(/^(\.\.[/\\])+/, "");
  const fullPath = join(distDir, safePath);
  if (!fullPath.startsWith(distDir)) {
    return "";
  }
  if (existsSync(fullPath) && statSync(fullPath).isFile()) {
    return fullPath;
  }
  const fallback = join(distDir, "index.html");
  return existsSync(fallback) ? fallback : "";
}

function sendStatic(req, res, pathname) {
  const filePath = staticPath(pathname);
  if (!filePath) {
    sendJson(res, 404, { error: "Not found; run npm run build first for the UI bundle" });
    return;
  }
  const stat = statSync(filePath);
  res.writeHead(200, {
    "content-type": contentTypes[extname(filePath)] || "application/octet-stream",
    "content-length": stat.size,
    "cache-control": filePath.endsWith("index.html") ? "no-store" : "public, max-age=3600"
  });
  if (req.method === "HEAD") {
    res.end();
    return;
  }
  createReadStream(filePath).pipe(res);
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${host}:${port}`);

    if (req.method === "GET" && url.pathname === "/api/status") {
      sendJson(res, 200, await buildStatus());
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/actions") {
      sendJson(res, 200, { actions });
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/network-events") {
      sendJson(res, 200, await getNetworkEvents());
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/self-check") {
      sendJson(res, 200, await getSelfCheck());
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/gateway/v2/status") {
      sendJson(res, 200, await getGatewayControllerStatus());
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/gateway/v2/phone-setup") {
      sendJson(res, 200, await getGatewayControllerPhoneSetup());
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/gateway/v2/pac") {
      const pac = await getGatewayControllerPac();
      sendText(res, pac.statusCode, pac.content, pac.mimeType);
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/gateway/v2/diagnostics") {
      sendJson(res, 200, getGatewayControllerDiagnostics());
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/gateway/v2/unlock") {
      sendJson(res, 403, gatewayControllerActionBlocked("unlock"));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/gateway/v2/lock") {
      sendJson(res, 403, gatewayControllerActionBlocked("lock"));
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/gateway/v2/profile/export") {
      sendJson(res, 403, gatewayControllerActionBlocked("profile-export"));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/gateway/v2/profile/import") {
      sendJson(res, 403, gatewayControllerActionBlocked("profile-import"));
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/linux/desktop-package") {
      sendJson(res, 200, await linuxDesktopPackageStatus());
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/linux/proxy-unification") {
      const status = await buildStatus();
      sendJson(
        res,
        200,
        buildLinuxProxyUnification(status.runtime || {}, {
          externalServices: knownExternalProxyServices()
        })
      );
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/linux/profile/import") {
      const body = await readJson(req);
      sendJson(res, 200, await importLinuxProfileUpload(body));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/actions/run") {
      const body = await readJson(req);
      sendJson(res, 200, await runAction(String(body.actionId || "")));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/network-events/resolve") {
      const body = await readJson(req);
      sendJson(res, 200, await resolveNetworkEvent(String(body.eventId || ""), String(body.decision || "")));
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/benchmark") {
      sendJson(res, 200, await runBenchmark());
      return;
    }

    if ((req.method === "GET" || req.method === "HEAD") && !url.pathname.startsWith("/api/")) {
      sendStatic(req, res, url.pathname);
      return;
    }

    sendJson(res, 404, { error: "Not found" });
  } catch (error) {
    sendJson(res, 500, { error: "Internal server error" });
  }
});

server.listen(port, host, () => {
  console.log(`Proxy Gateway Console API listening on http://${host}:${port}`);
});

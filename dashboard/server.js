import { Buffer } from 'node:buffer';
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const applicationDirectory = resolve(fileURLToPath(new URL('.', import.meta.url)));
const distDirectory = resolve(applicationDirectory, 'dist');
const indexHtmlPath = resolve(distDirectory, 'index.html');
const port = Number.parseInt(process.env.PORT ?? process.env.WEBSITES_PORT ?? '8080', 10);

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

function ensureTrailingSlash(value) {
  return value.endsWith('/') ? value : `${value}/`;
}

function getDataEndpoints() {
  const configuredEndpoints = process.env.DASHBOARD_DATA_ENDPOINTS?.split(',')
    .map((value) => value.trim())
    .filter((value) => value.length > 0);

  if (configuredEndpoints && configuredEndpoints.length > 0) {
    return [...new Set(configuredEndpoints)];
  }

  return ['/api/data', '/data'];
}

function getCacheControl(pathname) {
  if (pathname.endsWith('.html') || pathname.endsWith('.json')) {
    return 'no-cache';
  }

  if (pathname.includes('/assets/')) {
    return 'public, max-age=31536000, immutable';
  }

  return 'public, max-age=3600';
}

function getMimeType(pathname) {
  return MIME_TYPES[extname(pathname).toLowerCase()] ?? 'application/octet-stream';
}

function resolveStaticAsset(pathname) {
  const normalizedPath = pathname === '/' ? '/index.html' : pathname;
  const assetPath = resolve(distDirectory, `.${normalizedPath}`);

  if (!assetPath.startsWith(distDirectory)) {
    return null;
  }

  return assetPath;
}

function sendJson(response, statusCode, payload, cacheControl = 'no-cache') {
  response.statusCode = statusCode;
  response.setHeader('Cache-Control', cacheControl);
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.end(JSON.stringify(payload));
}

async function sendIndexHtml(response, method) {
  const html = await readFile(indexHtmlPath);
  response.statusCode = 200;
  response.setHeader('Cache-Control', 'no-cache');
  response.setHeader('Content-Type', 'text/html; charset=utf-8');

  if (method === 'HEAD') {
    response.end();
    return;
  }

  response.end(html);
}

function sendNotFound(response) {
  response.statusCode = 404;
  response.setHeader('Content-Type', 'text/plain; charset=utf-8');
  response.end('Not found');
}

async function proxyDashboardData(request, response, requestUrl) {
  const proxyBaseUrl = process.env.DASHBOARD_DATA_PROXY_BASE_URL?.trim();
  if (!proxyBaseUrl) {
    sendNotFound(response);
    return;
  }

  const fileName = requestUrl.pathname.replace(/^\/api\/data\//, '');
  if (fileName.length === 0) {
    sendNotFound(response);
    return;
  }

  const upstreamUrl = new URL(fileName, ensureTrailingSlash(proxyBaseUrl));
  upstreamUrl.search = requestUrl.search;

  let upstreamResponse;
  try {
    upstreamResponse = await globalThis.fetch(upstreamUrl, {
      method: request.method,
      headers: {
        Accept: 'application/json',
      },
    });
  } catch {
    response.statusCode = 502;
    response.setHeader('Content-Type', 'text/plain; charset=utf-8');
    response.end('Unable to reach the dashboard data endpoint.');
    return;
  }

  response.statusCode = upstreamResponse.status;
  response.setHeader(
    'Cache-Control',
    upstreamResponse.headers.get('cache-control') ?? 'no-cache',
  );
  response.setHeader(
    'Content-Type',
    upstreamResponse.headers.get('content-type') ?? 'application/json; charset=utf-8',
  );

  if (request.method === 'HEAD') {
    response.end();
    return;
  }

  response.end(Buffer.from(await upstreamResponse.arrayBuffer()));
}

const server = createServer(async (request, response) => {
  const method = request.method ?? 'GET';

  if (method !== 'GET' && method !== 'HEAD') {
    response.statusCode = 405;
    response.setHeader('Allow', 'GET, HEAD');
    response.end();
    return;
  }

  const requestUrl = new URL(request.url ?? '/', `http://${request.headers.host ?? 'localhost'}`);
  const pathname = requestUrl.pathname;
  const staticPathname = pathname === '/' ? '/index.html' : pathname;

  if (pathname === '/healthz') {
    sendJson(response, 200, { ok: true });
    return;
  }

  if (pathname === '/runtime-config.json') {
    sendJson(response, 200, { dataEndpoints: getDataEndpoints() }, 'no-store');
    return;
  }

  if (pathname.startsWith('/api/data/')) {
    await proxyDashboardData(request, response, requestUrl);
    return;
  }

  const assetPath = resolveStaticAsset(pathname);

  if (assetPath && existsSync(assetPath) && statSync(assetPath).isFile()) {
    response.statusCode = 200;
    response.setHeader('Cache-Control', getCacheControl(staticPathname));
    response.setHeader('Content-Type', getMimeType(staticPathname));

    if (method === 'HEAD') {
      response.end();
      return;
    }

    createReadStream(assetPath).pipe(response);
    return;
  }

  if (pathname.startsWith('/api/') || extname(pathname) !== '') {
    sendNotFound(response);
    return;
  }

  try {
    await sendIndexHtml(response, method);
  } catch {
    response.statusCode = 500;
    response.setHeader('Content-Type', 'text/plain; charset=utf-8');
    response.end('Unable to load the dashboard application.');
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`Dashboard server listening on port ${port}`);
});

'use strict';

/**
 * Tillu Browser — embedded Express API server
 *
 * Implements the exact same /api/browser-control/* surface the brain's
 * internal_rpc module calls. The brain sets:
 *
 *   TILLU_RUNTIME_URL=http://localhost:7788
 *   service_role=brain   (already the default)
 *
 * and every browser_start / browser_navigate / browser_action proposal
 * routes here instead of the remote Render runtime.
 *
 * Endpoints mirror apps/api/app/main.py browser-control routes:
 *   POST   /api/browser-control/sessions           → start session
 *   DELETE /api/browser-control/sessions/:sid      → close session
 *   GET    /api/browser-control/sessions/:sid      → state snapshot
 *   POST   /api/browser-control/navigate           → navigate
 *   POST   /api/browser-control/sessions/:sid/go-back
 *   POST   /api/browser-control/sessions/:sid/go-forward
 *   POST   /api/browser-control/sessions/:sid/reload
 *   POST   /api/browser-control/sessions/:sid/screenshot  → base64 JPEG
 *   GET    /api/browser-control/sessions/:sid/stream      → MJPEG stream
 *   POST   /api/browser-control/mouse/click
 *   POST   /api/browser-control/mouse/move
 *   POST   /api/browser-control/mouse/scroll
 *   POST   /api/browser-control/keyboard/press
 *   POST   /api/browser-control/keyboard/type
 *   POST   /api/browser-control/action             → selector-based action
 *   GET    /api/browser-control/history            → history list
 *   DELETE /api/browser-control/history            → clear history
 *   GET    /health                                  → liveness
 */

const express = require('express');
const cors    = require('cors');
const { v4: uuidv4 } = require('uuid');

// Netpolicy: block private/loopback targets (mirrors netpolicy.py)
const BLOCKED_HOSTS = /^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1|0\.0\.0\.0)/i;
function validateUrl(url) {
  try {
    const u = new URL(url);
    if (!['http:', 'https:'].includes(u.protocol)) throw new Error('Only http/https allowed');
    if (BLOCKED_HOSTS.test(u.hostname))            throw new Error('Private network targets are blocked');
  } catch (e) {
    throw Object.assign(new Error(e.message), { status: 400 });
  }
}

// In-memory session store { sid: { userId, history: [] } }
const sessions = {};
// Navigation history [ { url, title, visitedAt } ]
const history  = [];
const MAX_HISTORY = 500;

function recordHistory(url, title) {
  if (!url || url === 'about:blank') return;
  history.unshift({ url, title: title || url, visited_at: new Date().toISOString() });
  if (history.length > MAX_HISTORY) history.length = MAX_HISTORY;
}

// ── Element snapshot via executeJavaScript ────────────────────────────────────
const SNAPSHOT_JS = `(function() {
  let n = 0;
  const q = 'a,button,input,textarea,select,[role],[contenteditable=true],[tabindex]';
  return [...document.querySelectorAll(q)].filter(e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 &&
           s.visibility !== 'hidden' && s.display !== 'none';
  }).slice(0, 300).map(e => {
    const ref = 'e' + (++n);
    e.setAttribute('data-tillu-ref', ref);
    const label = e.getAttribute('aria-label') || e.getAttribute('title') ||
                  e.innerText || e.value || e.getAttribute('placeholder') || '';
    const r = e.getBoundingClientRect();
    return {
      ref, tag: e.tagName.toLowerCase(),
      role: e.getAttribute('role') || null,
      name: String(label).trim().slice(0, 300),
      type: e.getAttribute('type') || null,
      value: ('value' in e ? String(e.value).slice(0, 300) : null),
      disabled: !!e.disabled,
      checked: 'checked' in e ? !!e.checked : null,
      href: e.href || null,
      x: Math.round(r.left), y: Math.round(r.top),
      w: Math.round(r.width), h: Math.round(r.height)
    };
  });
})()`;

const TEXT_JS = `document.body ? document.body.innerText.slice(0, 30000) : ''`;

async function pageState(wc, sid, statusCode) {
  const [elements, text] = await Promise.all([
    wc.executeJavaScript(SNAPSHOT_JS).catch(() => []),
    wc.executeJavaScript(TEXT_JS).catch(() => ''),
  ]);
  return {
    session_id: sid,
    url:        wc.getURL(),
    title:      wc.getTitle(),
    status:     statusCode || null,
    text,
    elements,
    screen_mode: 'dom_electron',
    viewport: { width: 1280, height: 800 },
  };
}

// ── MJPEG stream helpers ──────────────────────────────────────────────────────
const BOUNDARY = 'tilluboundary';

async function* mjpegFrames(wc, fps) {
  const interval = Math.max(100, Math.round(1000 / Math.min(fps, 30)));
  while (true) {
    try {
      const img  = await wc.capturePage();
      const jpeg = img.toJPEG(75);
      const header = Buffer.from(
        `--${BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ${jpeg.length}\r\n\r\n`
      );
      yield Buffer.concat([header, jpeg, Buffer.from('\r\n')]);
    } catch { break; }
    await new Promise(r => setTimeout(r, interval));
  }
}

// ── Auth middleware (optional bearer token) ───────────────────────────────────
function makeAuthMiddleware(secret) {
  if (!secret) return (req, res, next) => next();
  return (req, res, next) => {
    const auth = req.headers['authorization'] || '';
    if (auth === `Bearer ${secret}`) return next();
    // Also allow query param _t= (matches runtime_ui.html pattern)
    if (req.query._t === secret) return next();
    res.status(401).json({ detail: 'Unauthorized' });
  };
}

// ── Build and start ───────────────────────────────────────────────────────────
async function startApiServer({ port, secret, getAgentView, getControlPanel, viewportW, viewportH }) {
  const app   = express();
  const auth  = makeAuthMiddleware(secret);

  app.use(cors());
  app.use(express.json({ limit: '2mb' }));
  app.use(auth);

  // Helper to get webContents or 404
  function wc(res) {
    const av = getAgentView();
    if (!av) { res.status(503).json({ detail: 'Agent view not initialised' }); return null; }
    return av.webContents;
  }

  // ── Health ────────────────────────────────────────────────────────────────
  app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: 'tillu-browser', sessions: Object.keys(sessions).length });
  });

  // ── Sessions ──────────────────────────────────────────────────────────────
  app.post('/api/browser-control/sessions', (req, res) => {
    const sid    = uuidv4();
    const userId = req.body?.user_id || 'local';
    sessions[sid] = { userId, createdAt: new Date().toISOString() };
    // Tell the control panel a session started (it can show session id)
    getControlPanel()?.webContents.send('session:started', { session_id: sid });
    res.json({ session_id: sid });
  });

  app.delete('/api/browser-control/sessions/:sid', (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    delete sessions[sid];
    // Navigate agent view back to blank
    const w = getAgentView();
    if (w) w.webContents.loadURL('about:blank').catch(() => {});
    getControlPanel()?.webContents.send('session:closed', { session_id: sid });
    res.json({ closed: true });
  });

  app.get('/api/browser-control/sessions/:sid', async (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    try { res.json(await pageState(w, sid)); }
    catch (e) { res.status(500).json({ detail: e.message }); }
  });

  // ── Navigate ──────────────────────────────────────────────────────────────
  app.post('/api/browser-control/navigate', async (req, res) => {
    const { session_id: sid, url } = req.body || {};
    if (!sid || !sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    if (!url) return res.status(400).json({ detail: 'url required' });
    try { validateUrl(url); } catch (e) { return res.status(e.status || 400).json({ detail: e.message }); }
    const w = wc(res); if (!w) return;
    try {
      // loadURL resolves when navigation commits; domready fires later
      await w.loadURL(url);
      // brief settle wait for dynamic pages
      await new Promise(r => setTimeout(r, 600));
      const state = await pageState(w, sid);
      recordHistory(state.url, state.title);
      getControlPanel()?.webContents.send('agent:navigated', { url: state.url, title: state.title });
      res.json(state);
    } catch (e) { res.status(502).json({ detail: e.message }); }
  });

  // ── Back / Forward / Reload ───────────────────────────────────────────────
  app.post('/api/browser-control/sessions/:sid/go-back', async (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    w.goBack();
    await new Promise(r => setTimeout(r, 600));
    try { res.json(await pageState(w, sid)); } catch (e) { res.status(500).json({ detail: e.message }); }
  });

  app.post('/api/browser-control/sessions/:sid/go-forward', async (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    w.goForward();
    await new Promise(r => setTimeout(r, 600));
    try { res.json(await pageState(w, sid)); } catch (e) { res.status(500).json({ detail: e.message }); }
  });

  app.post('/api/browser-control/sessions/:sid/reload', async (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    w.reload();
    await new Promise(r => setTimeout(r, 800));
    try { res.json(await pageState(w, sid)); } catch (e) { res.status(500).json({ detail: e.message }); }
  });

  // ── Screenshot ────────────────────────────────────────────────────────────
  app.post('/api/browser-control/sessions/:sid/screenshot', async (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    try {
      const img  = await getAgentView().webContents.capturePage();
      const jpeg = img.toJPEG(85);
      const name = `${sid}__${uuidv4().replace(/-/g,'')}.jpg`;
      res.json({ name, data: jpeg.toString('base64'), mime: 'image/jpeg' });
    } catch (e) { res.status(500).json({ detail: e.message }); }
  });

  // ── MJPEG stream ──────────────────────────────────────────────────────────
  app.get('/api/browser-control/sessions/:sid/stream', async (req, res) => {
    const { sid } = req.params;
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const av = getAgentView(); if (!av) return res.status(503).end();
    const fps = parseInt(req.query.fps || '15', 10);

    res.setHeader('Content-Type',  `multipart/x-mixed-replace; boundary=${BOUNDARY}`);
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection',    'keep-alive');
    res.flushHeaders();

    for await (const frame of mjpegFrames(av.webContents, fps)) {
      if (res.destroyed) break;
      res.write(frame);
    }
    res.end();
  });

  // ── Mouse ─────────────────────────────────────────────────────────────────
  app.post('/api/browser-control/mouse/click', async (req, res) => {
    const { session_id: sid, x, y, button = 'left' } = req.body || {};
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    try {
      const btn = button === 'right' ? 'right' : 'left';
      w.sendInputEvent({ type: 'mouseDown', x, y, button: btn, clickCount: 1 });
      w.sendInputEvent({ type: 'mouseUp',   x, y, button: btn, clickCount: 1 });
      await new Promise(r => setTimeout(r, 200));
      res.json(await pageState(w.webContents || w, sid));
    } catch (e) { res.status(500).json({ detail: e.message }); }
  });

  app.post('/api/browser-control/mouse/move', async (req, res) => {
    const { session_id: sid, x, y } = req.body || {};
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    w.sendInputEvent({ type: 'mouseMove', x, y });
    res.json({ ok: true });
  });

  app.post('/api/browser-control/mouse/scroll', async (req, res) => {
    const { session_id: sid, x = 0, y = 0, delta_x = 0, delta_y = 0 } = req.body || {};
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    w.sendInputEvent({ type: 'mouseWheel', x, y, deltaX: delta_x, deltaY: delta_y });
    res.json({ ok: true });
  });

  // ── Keyboard ──────────────────────────────────────────────────────────────
  // Key name map: agent sends Playwright-style names, we translate to Electron
  const KEY_MAP = {
    'Enter':'Return','Backspace':'BackSpace','Delete':'Delete','Escape':'Escape',
    'Tab':'Tab','ArrowUp':'Up','ArrowDown':'Down','ArrowLeft':'Left','ArrowRight':'Right',
    'Home':'Home','End':'End','PageUp':'Prior','PageDown':'Next',
    'F5':'F5','F12':'F12','Space':' ',
    'Control+A':'ctrl+a','Control+C':'ctrl+c','Control+V':'ctrl+v',
    'Control+Z':'ctrl+z','Control+X':'ctrl+x','Control+L':'ctrl+l',
  };

  app.post('/api/browser-control/keyboard/press', async (req, res) => {
    const { session_id: sid, key } = req.body || {};
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    const mapped = KEY_MAP[key] || key;
    // Handle ctrl+X combos
    if (mapped.startsWith('ctrl+')) {
      const k = mapped.slice(5);
      w.sendInputEvent({ type: 'keyDown', modifiers: ['control'], keyCode: k.toUpperCase() });
      w.sendInputEvent({ type: 'keyUp',   modifiers: ['control'], keyCode: k.toUpperCase() });
    } else {
      w.sendInputEvent({ type: 'keyDown', keyCode: mapped });
      w.sendInputEvent({ type: 'keyUp',   keyCode: mapped });
    }
    await new Promise(r => setTimeout(r, 100));
    res.json({ ok: true });
  });

  app.post('/api/browser-control/keyboard/type', async (req, res) => {
    const { session_id: sid, text } = req.body || {};
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    for (const ch of String(text || '').slice(0, 500)) {
      w.sendInputEvent({ type: 'char', keyCode: ch });
      await new Promise(r => setTimeout(r, 15));
    }
    res.json({ ok: true });
  });

  // ── Selector-based action (mirrors browser_action in main.py) ─────────────
  app.post('/api/browser-control/action', async (req, res) => {
    const { session_id: sid, action, selector, text, key } = req.body || {};
    if (!sessions[sid]) return res.status(404).json({ detail: 'Session not found' });
    const w = wc(res); if (!w) return;
    // Resolve data-tillu-ref shortcuts
    const css = String(selector || '').startsWith('@')
      ? `[data-tillu-ref="${selector.slice(1)}"]`
      : selector;
    try {
      const js = (() => {
        switch (action) {
          case 'click':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(!e) throw new Error('not found'); e.click(); })()`;
          case 'type':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(!e) throw new Error('not found'); e.focus(); e.value=${JSON.stringify(String(text||''))}; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); })()`;
          case 'check':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(!e) throw new Error('not found'); e.checked=true; e.dispatchEvent(new Event('change',{bubbles:true})); })()`;
          case 'uncheck':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(!e) throw new Error('not found'); e.checked=false; e.dispatchEvent(new Event('change',{bubbles:true})); })()`;
          case 'select':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(!e) throw new Error('not found'); const o=[...e.options].find(o=>o.text===${JSON.stringify(String(text||''))}||o.value===${JSON.stringify(String(text||''))}); if(o){e.value=o.value;e.dispatchEvent(new Event('change',{bubbles:true}));} })()`;
          case 'press':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(e){e.focus();} document.dispatchEvent(new KeyboardEvent('keydown',{key:${JSON.stringify(String(key||'Enter'))},bubbles:true})); })()`;
          case 'scroll':
            return `(function(){ const e=document.querySelector(${JSON.stringify(css)}); if(!e) throw new Error('not found'); e.scrollIntoView({behavior:'smooth',block:'center'}); })()`;
          default:
            throw Object.assign(new Error(`Unsupported action: ${action}`), { status: 400 });
        }
      })();
      await w.executeJavaScript(js);
      await new Promise(r => setTimeout(r, 300));
      res.json(await pageState(w, sid));
    } catch (e) { res.status(e.status || 500).json({ detail: e.message }); }
  });

  // ── Browser history ───────────────────────────────────────────────────────
  app.get('/api/browser-control/history', (req, res) => {
    res.json({ history: history.slice(0, 100) });
  });

  app.delete('/api/browser-control/history', (req, res) => {
    history.length = 0;
    res.json({ cleared: true });
  });

  // ── Artifacts: serve screenshot files (matches /api/browser-artifacts/:name) 
  // Not needed for local mode but keeps compatibility if brain requests one.
  app.get('/api/browser-artifacts/:name', (req, res) => {
    res.status(404).json({ detail: 'Artifacts endpoint not applicable in local Electron mode' });
  });

  return new Promise((resolve, reject) => {
    const server = app.listen(port, '127.0.0.1', () => resolve(server));
    server.on('error', reject);
  });
}

module.exports = { startApiServer };

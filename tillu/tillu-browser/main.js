'use strict';

/**
 * Tillu Browser — Electron main process
 *
 * Architecture:
 *   - Two BrowserWindows:
 *       1. controlPanel  — runtime_ui.html (the agent cycle / manual control UI)
 *       2. agentView     — the actual web page the agent navigates/controls
 *   - An embedded Express server (api.js) runs in the main process and is
 *     exposed on a configurable port (default 7788). The Tillu brain's
 *     internal_rpc points TILLU_RUNTIME_URL=http://localhost:7788 at this.
 *   - The agent view is hidden by default; the control panel shows the MJPEG
 *     stream of it (or can reveal it with --show-agent-view flag).
 */

const { app, BrowserWindow, ipcMain, screen, nativeTheme } = require('electron');
const path  = require('path');
const { startApiServer } = require('./api');

// ── Config ────────────────────────────────────────────────────────────────────
const DEV          = process.argv.includes('--dev');
const SHOW_AGENT   = process.argv.includes('--show-agent-view');
const API_PORT     = parseInt(process.env.TILLU_BROWSER_PORT || '7788', 10);
const SECRET       = process.env.TILLU_BROWSER_SECRET || '';  // optional bearer token check
const VIEWPORT_W   = 1280;
const VIEWPORT_H   = 800;

nativeTheme.themeSource = 'dark';

let controlPanel = null;   // The operator UI window
let agentView    = null;   // The headless-ish browsing window

// ── Agent-view window ─────────────────────────────────────────────────────────
function createAgentView() {
  agentView = new BrowserWindow({
    width:  VIEWPORT_W,
    height: VIEWPORT_H,
    show:   SHOW_AGENT,
    frame:  SHOW_AGENT,
    title:  'Tillu Agent View',
    webPreferences: {
      nodeIntegration:    false,
      contextIsolation:   true,
      sandbox:            true,
      webSecurity:        true,
      allowRunningInsecureContent: false,
    },
  });

  agentView.loadURL('about:blank');

  agentView.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  // Forward navigation events to the control panel so it can update its URL bar
  agentView.webContents.on('did-navigate', (_, url) => {
    controlPanel?.webContents.send('agent:navigated', {
      url,
      title: agentView.webContents.getTitle(),
    });
  });
  agentView.webContents.on('did-navigate-in-page', (_, url) => {
    controlPanel?.webContents.send('agent:navigated', {
      url,
      title: agentView.webContents.getTitle(),
    });
  });
  agentView.webContents.on('page-title-updated', (_, title) => {
    controlPanel?.webContents.send('agent:title', title);
  });
  agentView.webContents.on('did-start-loading', () => {
    controlPanel?.webContents.send('agent:loading', true);
  });
  agentView.webContents.on('did-stop-loading', () => {
    controlPanel?.webContents.send('agent:loading', false);
  });

  agentView.on('closed', () => { agentView = null; });
  return agentView;
}

// ── Control-panel window ──────────────────────────────────────────────────────
function createControlPanel() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  controlPanel = new BrowserWindow({
    width:           Math.min(1400, width),
    height:          Math.min(900, height),
    minWidth:        800,
    minHeight:       600,
    title:           'Tillu Runtime',
    backgroundColor: '#0d0b14',
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      sandbox:          false,   // preload needs fs access
      preload:          path.join(__dirname, 'preload.js'),
    },
  });

  controlPanel.loadFile(path.join(__dirname, 'ui', 'index.html'));

  if (DEV) controlPanel.webContents.openDevTools({ mode: 'detach' });

  controlPanel.on('closed', () => {
    controlPanel = null;
    agentView?.close();
    app.quit();
  });
}

// ── IPC: renderer → main ──────────────────────────────────────────────────────
// The control panel's renderer calls these via contextBridge (preload.js).

ipcMain.handle('browser:navigate', async (_, url) => {
  if (!agentView) return { error: 'no_session' };
  try {
    await agentView.webContents.loadURL(url);
    return { url: agentView.webContents.getURL(), title: agentView.webContents.getTitle() };
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('browser:goBack', async () => {
  if (!agentView) return { error: 'no_session' };
  agentView.webContents.goBack();
  return { ok: true };
});

ipcMain.handle('browser:goForward', async () => {
  if (!agentView) return { error: 'no_session' };
  agentView.webContents.goForward();
  return { ok: true };
});

ipcMain.handle('browser:reload', async () => {
  if (!agentView) return { error: 'no_session' };
  agentView.webContents.reload();
  return { ok: true };
});

ipcMain.handle('browser:getState', async () => {
  if (!agentView) return { error: 'no_session' };
  return {
    url:   agentView.webContents.getURL(),
    title: agentView.webContents.getTitle(),
  };
});

ipcMain.handle('browser:screenshot', async () => {
  if (!agentView) return null;
  try {
    const img = await agentView.webContents.capturePage();
    return img.toJPEG(80).toString('base64');
  } catch { return null; }
});

ipcMain.handle('browser:getApiPort', () => API_PORT);

ipcMain.handle('browser:revealAgentView', () => {
  agentView?.show();
});

ipcMain.handle('browser:hideAgentView', () => {
  if (SHOW_AGENT) return; // keep visible if explicitly requested
  agentView?.hide();
});

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(async () => {
  createAgentView();
  createControlPanel();

  // Start the REST API server that the Tillu brain calls
  await startApiServer({
    port:        API_PORT,
    secret:      SECRET,
    getAgentView: () => agentView,
    getControlPanel: () => controlPanel,
    viewportW:   VIEWPORT_W,
    viewportH:   VIEWPORT_H,
  });

  console.log(`[tillu-browser] API listening on http://localhost:${API_PORT}`);
  console.log(`[tillu-browser] Set TILLU_RUNTIME_URL=http://localhost:${API_PORT} in the brain's .env`);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (!controlPanel) {
    createAgentView();
    createControlPanel();
  }
});

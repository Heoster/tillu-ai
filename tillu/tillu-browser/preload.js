'use strict';

/**
 * Tillu Browser — preload script
 *
 * Runs in the control-panel renderer with Node access.
 * Exposes a safe contextBridge API so the UI can:
 *   - Drive the agent view (navigate, back, fwd, reload, screenshot)
 *   - Receive push events from the main process (navigation, loading state)
 *   - Know the API port (for direct fetch to the Express server)
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('tillu', {

  // ── Agent-view control ──────────────────────────────────────────────────
  navigate:       (url)  => ipcRenderer.invoke('browser:navigate', url),
  goBack:         ()     => ipcRenderer.invoke('browser:goBack'),
  goForward:      ()     => ipcRenderer.invoke('browser:goForward'),
  reload:         ()     => ipcRenderer.invoke('browser:reload'),
  getState:       ()     => ipcRenderer.invoke('browser:getState'),
  screenshot:     ()     => ipcRenderer.invoke('browser:screenshot'),  // → base64 JPEG string
  getApiPort:     ()     => ipcRenderer.invoke('browser:getApiPort'),
  revealAgentView: ()    => ipcRenderer.invoke('browser:revealAgentView'),
  hideAgentView:  ()     => ipcRenderer.invoke('browser:hideAgentView'),

  // ── Event subscriptions ─────────────────────────────────────────────────
  // Returns an unsubscribe function.
  on: (channel, fn) => {
    const allowed = ['agent:navigated', 'agent:title', 'agent:loading', 'session:started', 'session:closed'];
    if (!allowed.includes(channel)) return () => {};
    const handler = (_, ...args) => fn(...args);
    ipcRenderer.on(channel, handler);
    return () => ipcRenderer.removeListener(channel, handler);
  },
});

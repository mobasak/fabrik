// preload.js — runs in an isolated world before the page; the ONLY bridge between the
// sandboxed renderer and the main process (.windsurf/rules/desktop-app/72-desktop.md,
// § Preload + contextBridge). Expose a narrow, named API — never ipcRenderer itself.
//
// This starter exposes static values only, so there is no IPC channel yet. When you add
// one, expose a single named function per action here (e.g. `saveNote: (n) =>
// ipcRenderer.invoke('note:save', n)`) and make its ipcMain.handle in main.js check
// event.senderFrame.origin and validate the payload before acting (72-desktop.md).
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('api', {
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node,
  },
});

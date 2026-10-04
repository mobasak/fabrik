const path = require('path');
const { app, BrowserWindow } = require('electron');
const { autoUpdater } = require('electron-updater');

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      // Security trio — all three mandatory per .windsurf/rules/desktop-app/72-desktop.md
      // (missing any one is a CVE). Renderer runs sandboxed; main↔renderer only
      // via the preload's contextBridge.exposeInMainWorld bridge.
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js'),
    }
  });

  win.loadFile('index.html');

  // Updates come from your own update domain (package.json build.publish, URL from
  // UPDATE_FEED_URL — 72-desktop.md § Auto-Update). An unpackaged dev run has no
  // app-update.yml, so check only in a packaged build, and never let a failed check
  // become an unhandled rejection.
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      console.error('update check failed:', err);
    });
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

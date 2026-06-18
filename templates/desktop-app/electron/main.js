const { app, BrowserWindow } = require('electron');
const { autoUpdater } = require('electron-updater');

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      // Security trio — all three mandatory per .windsurf/rules/desktop-app/72-desktop.md
      // (missing any one is a CVE). Renderer runs sandboxed; main↔renderer only
      // via a preload + contextBridge.exposeInMainWorld bridge.
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    }
  });

  win.loadFile('index.html');
  
  // Automation: Check for updates from your VPS
  autoUpdater.checkForUpdatesAndNotify();
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

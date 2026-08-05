const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("graphcoder", {
  request: (method, params) => ipcRenderer.invoke("gc:request", method, params),
  onNotification: (callback) => {
    const listener = (_event, method, params) => callback(method, params);
    ipcRenderer.on("gc:notification", listener);
    return () => ipcRenderer.removeListener("gc:notification", listener);
  },
  selectWorkspace: () => ipcRenderer.invoke("gc:select-workspace"),
  revealPath: (target) => ipcRenderer.invoke("gc:reveal-path", target),
  openPath: (target) => ipcRenderer.invoke("gc:open-path", target),
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    node: process.versions.node,
  },
});

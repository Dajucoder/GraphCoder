const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("graphcoder", {
  request: (method, params) => ipcRenderer.invoke("gc:request", method, params),
  onNotification: (callback) => {
    ipcRenderer.on("gc:notification", (_event, method, params) => callback(method, params));
  },
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    node: process.versions.node,
  },
});

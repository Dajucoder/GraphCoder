const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const readline = require("readline");
const path = require("path");

const DEV = process.argv.includes("--dev");
const REPO = path.join(__dirname, "..");
const RPC_TIMEOUT_MS = 120000;

let runtime = null;
let mainWindow = null;
let workspace = REPO;
let seq = 0;
let isQuitting = false;
const pending = new Map();

function runtimeCommand() {
  if (app.isPackaged) {
    const executable = process.platform === "win32" ? "graphcoder-runtime.exe" : "graphcoder-runtime";
    return {
      command: path.join(process.resourcesPath, "runtime", executable),
      args: ["--home", app.getPath("userData")],
      cwd: app.getPath("userData"),
      env: process.env,
    };
  }
  const python = process.env.GRAPHCODER_RUNTIME_PYTHON || "python3";
  return {
    command: python,
    args: ["-m", "src.api.app_server", "--home", app.getPath("userData")],
    cwd: REPO,
    env: { ...process.env, PYTHONPATH: REPO },
  };
}

function rejectPending(message) {
  for (const request of pending.values()) {
    clearTimeout(request.timer);
    request.reject(new Error(message));
  }
  pending.clear();
}

function notify(method, params = {}) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("gc:notification", method, params);
  }
}

function startRuntime() {
  if (runtime) return;
  const config = runtimeCommand();
  runtime = spawn(config.command, config.args, {
    cwd: config.cwd,
    env: config.env,
    stdio: ["pipe", "pipe", "pipe"],
  });

  runtime.once("error", (error) => {
    notify("server/error", { message: `无法启动 GraphCoder Runtime: ${error.message}` });
    rejectPending("运行时启动失败");
    runtime = null;
  });

  readline.createInterface({ input: runtime.stdout }).on("line", (line) => {
    try {
      const message = JSON.parse(line);
      if (message.id != null) {
        const request = pending.get(message.id);
        if (!request) return;
        pending.delete(message.id);
        clearTimeout(request.timer);
        if (message.error) request.reject(new Error(message.error.message || "RPC error"));
        else request.resolve(message.result);
        return;
      }
      if (message.method === "server/ready" && message.params?.workspace) {
        workspace = message.params.workspace;
      }
      if (message.method === "workspace/changed" && message.params?.path) {
        workspace = message.params.path;
      }
      notify(message.method, message.params || {});
    } catch {
      // Runtime logs use stderr; malformed stdout frames are intentionally ignored.
    }
  });

  runtime.stderr.on("data", (data) => console.log("[runtime]", String(data).trimEnd()));
  runtime.once("exit", (code, signal) => {
    const expected = isQuitting;
    runtime = null;
    if (!expected) {
      notify("server/error", {
        message: `GraphCoder Runtime 已退出 (${signal || code || "unknown"})`,
      });
    }
    rejectPending("运行时已退出");
  });
}

function stopRuntime() {
  if (!runtime) return;
  runtime.kill("SIGTERM");
  runtime = null;
  rejectPending("应用正在退出");
}

function requestRuntime(method, params = {}) {
  if (!runtime) startRuntime();
  return new Promise((resolve, reject) => {
    if (!runtime?.stdin?.writable) {
      reject(new Error("运行时尚未就绪"));
      return;
    }
    const id = ++seq;
    const timer = setTimeout(() => {
      if (pending.delete(id)) reject(new Error(`RPC 超时: ${method}`));
    }, RPC_TIMEOUT_MS);
    pending.set(id, { resolve, reject, timer });
    runtime.stdin.write(`${JSON.stringify({ id, method, params })}\n`);
  });
}

ipcMain.handle("gc:request", (_event, method, params) => requestRuntime(method, params));

ipcMain.handle("gc:select-workspace", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: "选择项目文件夹",
    defaultPath: workspace,
    properties: ["openDirectory", "createDirectory"],
  });
  return result.canceled ? null : result.filePaths[0];
});

function resolveWorkspacePath(target) {
  const value = String(target || "");
  return path.isAbsolute(value) ? value : path.join(workspace, value);
}

ipcMain.handle("gc:reveal-path", (_event, target) => {
  shell.showItemInFolder(resolveWorkspacePath(target));
});

ipcMain.handle("gc:open-path", (_event, target) => shell.openPath(resolveWorkspacePath(target)));

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 820,
    minHeight: 600,
    title: "GraphCoder",
    titleBarStyle: process.platform === "darwin" ? "hiddenInset" : "default",
    trafficLightPosition: { x: 16, y: 18 },
    backgroundColor: "#f5f5f6",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  startRuntime();
  if (DEV) {
    await mainWindow.loadURL(process.env.GRAPHCODER_WEB_URL || "http://localhost:5173");
  } else {
    await mainWindow.loadFile(path.join(process.resourcesPath, "web", "index.html"));
  }
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on("before-quit", () => {
  isQuitting = true;
  stopRuntime();
});

const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const readline = require("readline");
const path = require("path");

const DEV = process.argv.includes("--dev");
const REPO = path.join(__dirname, "..");

let runtime = null;
let mainWindow = null;
let seq = 0;
const pending = new Map();

function runtimePython() {
  if (process.env.GRAPHCODER_RUNTIME_PYTHON) return process.env.GRAPHCODER_RUNTIME_PYTHON;
  return "python3";
}

function startRuntime() {
  const python = runtimePython();
  runtime = spawn(
    python,
    ["-m", "src.api.app_server", "--workspace", REPO],
    {
      cwd: REPO,
      env: {
        ...process.env,
        PYTHONPATH: REPO,
      },
      stdio: ["pipe", "pipe", "pipe"],
    }
  );
  readline
    .createInterface({ input: runtime.stdout })
    .on("line", (line) => {
      try {
        const msg = JSON.parse(line);
        if (msg.id) {
          const p = pending.get(msg.id);
          if (p) {
            pending.delete(msg.id);
            msg.error ? p.reject(new Error(msg.error.message || "RPC error")) : p.resolve(msg.result);
          }
        } else if (msg.method && mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("gc:notification", msg.method, msg.params || {});
        }
      } catch {
        /* ignore malformed frame */
      }
    });
  runtime.stderr.on("data", (d) => console.log("[runtime]", String(d).trimEnd()));
  runtime.on("exit", (code) => {
    console.log("[runtime] exited:", code);
    runtime = null;
    for (const p of pending.values()) p.reject(new Error("运行时已退出"));
    pending.clear();
  });
}

ipcMain.handle("gc:request", (_event, method, params) => {
  if (!runtime) startRuntime();
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    const payload = JSON.stringify({ id, method, params: params || {} });
    runtime.stdin.write(payload + "\n");
    setTimeout(() => {
      if (pending.delete(id)) reject(new Error(`RPC 超时: ${method}`));
    }, 120000);
  });
});

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: "GraphCoder",
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  startRuntime();
  if (DEV) {
    await mainWindow.loadURL("http://localhost:5173");
  } else {
    await mainWindow.loadFile(path.join(REPO, "web", "dist", "index.html"));
  }
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (runtime) runtime.kill("SIGTERM");
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

app.on("before-quit", () => {
  if (runtime) runtime.kill("SIGTERM");
});

const $ = (id) => document.getElementById(id);

const state = {
  port: null,
  reader: null,
  writer: null,
  readLoopActive: false,
  pending: [],
  rxBuffer: "",
  lastSystem: null,
  lastUart: null,
  lastSocket: null,
  backend: false,
};

const systemFields = [
  "passwd",
  "linkled",
  "noNetRst",
  "simEXT",
  "apnName",
  "apnUser",
  "apnPass",
  "apnAuth",
  "ntpHost",
  "ntpTime",
  "fota",
  "rst",
];

const readonlySystemFields = {
  sn: "sn",
  softwareName: "sfn",
  softwareVersion: "sfv",
  firmwareVersion: "frv",
};

const simOperatorPrefixes = [
  { prefix: "8957101", name: "Claro Colombia", apn: "internet.comcel.com.co" },
  { prefix: "8957732", name: "Tigo Colombia", apn: "web.colombiamovil.com.co" },
  { prefix: "8950604", name: "Movistar", apn: "internet.movistar.com.co" },
  { prefix: "898608", name: "China Mobile IoT", apn: "cmiotshkyrjb.js" },
];

const networkOperatorNames = {
  732101: "Claro Colombia",
  732103: "Tigo Colombia",
  732111: "Tigo Colombia",
  732123: "Movistar Colombia",
  732130: "WOM Colombia",
};

function log(message, direction = "info") {
  const ts = new Date().toLocaleTimeString();
  const prefix = direction === "tx" ? "TX" : direction === "rx" ? "RX" : "INFO";
  $("log").textContent += `[${ts}] ${prefix} ${message}\n`;
  $("log").scrollTop = $("log").scrollHeight;
}

function setConnected(connected) {
  $("connectBtn").disabled = connected;
  $("disconnectBtn").disabled = !connected;
  $("readSystemBtn").disabled = !connected;
  $("writeSystemBtn").disabled = !connected;
  $("readUartBtn").disabled = !connected;
  $("writeUartBtn").disabled = !connected;
  $("readSocketBtn").disabled = !connected;
  $("writeSocketBtn").disabled = !connected;
  $("sendRawBtn").disabled = !connected;
  $("statusPill").textContent = connected ? "Conectado" : "Sin conexion";
  $("statusPill").className = `pill ${connected ? "on" : "off"}`;
}

function requireSerialSupport() {
  if (!("serial" in navigator)) {
    throw new Error("Web Serial no esta disponible. Usa Chrome o Edge desde http://localhost.");
  }
}

async function connect() {
  if (await connectBackend()) return;
  requireSerialSupport();
  const baudRate = Number($("baudRate").value);
  state.port = await navigator.serial.requestPort();
  await state.port.open({
    baudRate,
    dataBits: 8,
    stopBits: 1,
    parity: "none",
    flowControl: "none",
  });
  state.writer = state.port.writable.getWriter();
  state.readLoopActive = true;
  readLoop();
  setConnected(true);
  log(`Puerto abierto a ${baudRate} 8N1`);
}

async function connectBackend() {
  try {
    const response = await fetch("/api/ports", { cache: "no-store" });
    if (!response.ok) return false;
    const data = await response.json();
    state.backend = true;
    const select = $("serialPort");
    const current = select.value;
    select.innerHTML = "";
    for (const port of data.ports || []) {
      const option = document.createElement("option");
      option.value = port.device;
      option.textContent = `${port.device} - ${port.description || "Serial"}`;
      select.append(option);
    }
    if ([...select.options].some((option) => option.value === current)) select.value = current;
    setConnected(true);
    log("Backend local conectado. Los comandos se enviaran desde Windows al puerto seleccionado.");
    return true;
  } catch (_) {
    return false;
  }
}

async function disconnect() {
  if (state.backend) {
    state.backend = false;
    setConnected(false);
    log("Backend local desconectado");
    return;
  }
  state.readLoopActive = false;
  for (const pending of state.pending.splice(0)) {
    clearTimeout(pending.timer);
    pending.reject(new Error("Puerto desconectado"));
  }
  if (state.reader) {
    try {
      await state.reader.cancel();
    } catch (_) {}
  }
  if (state.writer) {
    state.writer.releaseLock();
    state.writer = null;
  }
  if (state.port) {
    await state.port.close();
    state.port = null;
  }
  setConnected(false);
  log("Puerto cerrado");
}

async function readLoop() {
  const decoder = new TextDecoder();
  while (state.port && state.readLoopActive) {
    try {
      state.reader = state.port.readable.getReader();
      while (state.readLoopActive) {
        const { value, done } = await state.reader.read();
        if (done) break;
        if (value) handleIncoming(decoder.decode(value, { stream: true }));
      }
    } catch (error) {
      if (state.readLoopActive) log(error.message);
    } finally {
      if (state.reader) {
        state.reader.releaseLock();
        state.reader = null;
      }
    }
  }
}

function handleIncoming(chunk) {
  state.rxBuffer += chunk;
  const frames = extractJsonFrames();
  for (const frame of frames) {
    log(frame, "rx");
    let parsed;
    try {
      parsed = JSON.parse(frame);
    } catch (error) {
      log(`JSON invalido recibido: ${error.message}`);
      continue;
    }
    const pending = state.pending.shift();
    if (pending) {
      clearTimeout(pending.timer);
      pending.resolve(parsed);
    }
    routeResponse(parsed);
  }
}

function extractJsonFrames() {
  const frames = [];
  let start = -1;
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = 0; i < state.rxBuffer.length; i += 1) {
    const char = state.rxBuffer[i];
    if (start === -1) {
      if (char === "{") {
        start = i;
        depth = 1;
      }
      continue;
    }
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === '"') {
        inString = false;
      }
      continue;
    }
    if (char === '"') inString = true;
    if (char === "{") depth += 1;
    if (char === "}") depth -= 1;
    if (depth === 0) {
      frames.push(state.rxBuffer.slice(start, i + 1));
      state.rxBuffer = state.rxBuffer.slice(i + 1);
      i = -1;
      start = -1;
    }
  }
  if (start > 0) state.rxBuffer = state.rxBuffer.slice(start);
  return frames;
}

async function sendCommand(command, timeoutMs = 5000) {
  if (state.backend) {
    const payload = typeof command === "string" ? command : JSON.stringify(command);
    log(payload, "tx");
    const response = await fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        moduleMode: $("moduleMode").value,
        port: $("serialPort").value,
        baudRate: Number($("baudRate").value),
        command,
        timeoutMs,
      }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Error enviando comando");
    log(JSON.stringify(body.response), "rx");
    routeResponse(body.response);
    return body.response;
  }
  if (!state.writer) throw new Error("Puerto no conectado");
  const payload = typeof command === "string" ? command : JSON.stringify(command);
  const bytes = new TextEncoder().encode(payload);
  log(payload, "tx");
  const responsePromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      const index = state.pending.findIndex((item) => item.timer === timer);
      if (index >= 0) state.pending.splice(index, 1);
      reject(new Error("Tiempo de espera agotado"));
    }, timeoutMs);
    state.pending.push({ resolve, reject, timer });
  });
  await state.writer.write(bytes);
  return responsePromise;
}

function routeResponse(response) {
  if (response.type === "getSystemInfoRsp" && response.data) {
    state.lastSystem = structuredClone(response);
    fillSystem(response.data);
  }
  if (response.type === "getUartInfoRsp" && response.data) {
    state.lastUart = structuredClone(response);
    fillUart(response.data);
  }
  if (response.type === "getSocketInfoRsp" && response.data) {
    state.lastSocket = structuredClone(response);
    fillSocket(response.data);
  }
}

function fillSystem(data) {
  $("simStatus").textContent = formatSim(data.sim);
  $("simOperator").textContent = inferSimOperator(data.iccid, data.operator);
  $("iccid").textContent = data.iccid ?? "-";
  $("regStatus").textContent = formatReg(data.reg);
  $("ipAddress").textContent = data.ip ?? "-";
  $("apnStatus").textContent = formatApn(data);
  $("csq").textContent = data.csq ?? "-";
  $("signal").textContent = data.signal ?? "-";

  for (const [elementId, key] of Object.entries(readonlySystemFields)) {
    $(elementId).value = data[key] ?? "";
  }
  for (const key of systemFields) {
    const element = $(key);
    if (!element) continue;
    if (key === "simEXT") {
      element.value = String(Boolean(data[key]));
    } else {
      element.value = data[key] ?? "";
    }
  }
}

function fillUart(data) {
  $("uartBr").value = String(data.br ?? 9600);
  $("uartDb").value = String(data.db ?? 8);
  $("uartPa").value = String(data.pa ?? 0);
  $("uartSb").value = String(data.sb ?? 1);
  $("uartRt").value = data.rt ?? "";
  $("uartSt").value = data.st ?? "";
}

function fillSocket(data) {
  $("socketEnable").value = String(Boolean(data.enable));
  $("tcpDomain").value = data.domain ?? data.server ?? "";
  $("tcpPort").value = data.tcpPort ?? 4000;
  $("tcpRecon").value = data.recon ?? "";
  $("tcpRegMode").value = String(data.regMode ?? 0);
  $("tcpRegPkg").value = data.regPkg ?? "";
  $("tcpHbtMode").value = data.hbtMode ?? 0;
  $("tcpHbtPkg").value = data.hbtPkg ?? "";
  const firstFlow = Array.isArray(data.ds) && data.ds.length ? data.ds[0]?.q : "";
  if (firstFlow && [...$("tcpDataFlow").options].some((option) => option.value === firstFlow)) {
    $("tcpDataFlow").value = firstFlow;
  }
}

function formatSim(value) {
  const map = {
    "-1": "API异常",
    0: "No existe",
    1: "Lista",
    18: "Inicializando",
    20: "Invalida",
    21: "Desconocida",
  };
  return `${value ?? "-"} ${map[value] ? `- ${map[value]}` : ""}`.trim();
}

function formatReg(value) {
  const map = {
    0: "No registrado",
    1: "Registrado local",
    2: "Buscando",
    3: "Rechazado",
    4: "Desconocido",
    5: "Registrado roaming",
  };
  return `${value ?? "-"} ${map[value] ? `- ${map[value]}` : ""}`.trim();
}

function inferSimOperator(iccid, operator) {
  const normalizedOperator = String(operator ?? "").replace(/\D/g, "");
  const operatorText =
    operator && operator !== -1 && operator !== "-1"
      ? networkOperatorNames[normalizedOperator]
        ? `${networkOperatorNames[normalizedOperator]} (${normalizedOperator})`
        : String(operator)
      : "";
  if (!iccid) return operatorText || "-";
  const normalized = String(iccid).replace(/\D/g, "");
  const match = simOperatorPrefixes.find((item) => normalized.startsWith(item.prefix));
  if (!match) return operatorText || "No identificado";
  return `${match.name} (${match.prefix})`;
}

function inferDefaultApn(iccid) {
  if (!iccid) return null;
  const normalized = String(iccid).replace(/\D/g, "");
  return simOperatorPrefixes.find((item) => normalized.startsWith(item.prefix))?.apn ?? null;
}

function formatApn(data) {
  if (data.apnActive) return `${data.apnActive} (activo)`;
  if (data.apnName) return data.apnName;
  const inferred = inferDefaultApn(data.iccid);
  return inferred ? `${inferred} (default)` : "Default no identificado";
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  return Number(value);
}

function buildSystemWrite() {
  if (!state.lastSystem?.data) {
    throw new Error("Lee sistema antes de guardar para conservar todos los campos.");
  }
  const next = structuredClone(state.lastSystem);
  next.type = "setSystemInfo";
  const data = next.data;
  data.passwd = $("passwd").value;
  data.linkled = numberOrNull($("linkled").value);
  data.noNetRst = numberOrNull($("noNetRst").value);
  data.simEXT = $("simEXT").value === "true";
  data.apnName = $("apnName").value;
  data.apnUser = $("apnUser").value;
  data.apnPass = $("apnPass").value;
  data.apnAuth = numberOrNull($("apnAuth").value);
  data.ntpHost = $("ntpHost").value;
  data.ntpTime = numberOrNull($("ntpTime").value);
  data.fota = $("fota").value;
  data.rst = $("rst").value;
  return next;
}

function buildUartWrite() {
  const data = state.lastUart?.data ? structuredClone(state.lastUart.data) : { ds: [] };
  data.br = Number($("uartBr").value);
  data.db = Number($("uartDb").value);
  data.pa = Number($("uartPa").value);
  data.sb = Number($("uartSb").value);
  data.rt = numberOrNull($("uartRt").value) ?? 0;
  data.st = numberOrNull($("uartSt").value) ?? 0;
  return { type: "setUartInfo", data };
}

function buildSocketWrite() {
  const socket = Number($("socketNumber").value);
  const data = state.lastSocket?.data ? structuredClone(state.lastSocket.data) : {};
  data.socket = socket;
  data.enable = $("socketEnable").value === "true";
  data.mode = "TCP";
  data.domain = $("tcpDomain").value;
  data.tcpPort = numberOrNull($("tcpPort").value) ?? 4000;
  data.recon = numberOrNull($("tcpRecon").value) ?? 0;
  data.regMode = numberOrNull($("tcpRegMode").value) ?? 0;
  data.regPkg = $("tcpRegPkg").value;
  data.hbtMode = numberOrNull($("tcpHbtMode").value) ?? 0;
  data.hbtPkg = $("tcpHbtPkg").value;
  data.ds = [
    {
      q: $("tcpDataFlow").value,
      t: { q: 0, t: "", r: false },
    },
  ];
  return { type: "setSocketInfo", data };
}

function buildNetworkPortWrite() {
  const data = state.lastSocket?.data ? structuredClone(state.lastSocket.data) : {};
  data.socket = Number($("socketNumber").value);
  data.tcpPort = numberOrNull($("tcpPort").value) ?? 4000;
  if (data.enable === undefined) data.enable = false;
  if (!data.mode) data.mode = "TCP";
  if (!data.ds) {
    data.ds = [
      {
        q: $("tcpDataFlow")?.value || "uart_send",
        t: { q: 0, t: "", r: false },
      },
    ];
  }
  return { type: "setSocketInfo", data };
}

async function guarded(action) {
  try {
    await action();
  } catch (error) {
    log(`ERROR ${error.message}`);
  }
}

$("connectBtn").addEventListener("click", () => guarded(connect));
$("disconnectBtn").addEventListener("click", () => guarded(disconnect));
$("readSystemBtn").addEventListener("click", () => guarded(() => sendCommand({ type: "getSystemInfo", data: {} })));
$("readUartBtn").addEventListener("click", () => guarded(() => sendCommand({ type: "getUartInfo", data: {} })));
$("readSocketBtn").addEventListener("click", () => guarded(() => {
  const socket = Number($("socketNumber").value);
  return sendCommand({ type: "getSocketInfo", data: { socket } });
}));
$("writeSystemBtn").addEventListener("click", () => guarded(async () => {
  const response = await sendCommand(buildSystemWrite(), 7000);
  if (response?.data?.code === 0) log("Sistema guardado");
}));
$("writeUartBtn").addEventListener("click", () => guarded(async () => {
  const uartResponse = await sendCommand(buildUartWrite(), 7000);
  if (uartResponse?.data?.code === 0) log("UART guardado");
  const socketResponse = await sendCommand(buildNetworkPortWrite(), 7000);
  if (socketResponse?.data?.code === 0) log("Puerto de salida red guardado");
}));
$("writeSocketBtn").addEventListener("click", () => guarded(async () => {
  const response = await sendCommand(buildSocketWrite(), 7000);
  if (response?.data?.code === 0) log("TCP socket guardado");
}));
$("sendRawBtn").addEventListener("click", () => guarded(async () => {
  JSON.parse($("rawCommand").value);
  await sendCommand($("rawCommand").value);
}));
$("clearLogBtn").addEventListener("click", () => {
  $("log").textContent = "";
});

document.querySelectorAll(".quick").forEach((button) => {
  button.addEventListener("click", () => {
    $("rawCommand").value = button.dataset.command;
  });
});

window.addEventListener("beforeunload", () => {
  if (state.port) disconnect();
});

setConnected(false);
log("Listo. Conecta el adaptador USB-RS485 y abre el puerto correspondiente.");

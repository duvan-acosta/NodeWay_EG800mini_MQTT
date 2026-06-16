import json
import os
import re
import time
from ast import literal_eval
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import serial
from serial.tools import list_ports


ROOT = os.path.dirname(os.path.abspath(__file__))


def extract_json_frame(text):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def send_serial_command(port, baudrate, payload, timeout=5.0):
    raw = bytearray()
    with serial.Serial(
        port=port,
        baudrate=int(baudrate),
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.1,
        write_timeout=2,
    ) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        if not payload.endswith("\r\n"):
            payload = f"{payload}\r\n"
        ser.write(payload.encode("utf-8"))
        ser.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                raw.extend(chunk)
                text = raw.decode("utf-8", errors="replace")
                frame = extract_json_frame(text)
                if frame:
                    return json.loads(frame), text
            time.sleep(0.03)
        text = raw.decode("utf-8", errors="replace")
        raise TimeoutError(f"Sin respuesta del equipo. Bytes recibidos: {len(raw)}. {text!r}")


def find_port(description):
    description = description.lower()
    for port in list_ports.comports():
        if description in (port.description or "").lower():
            return port.device
    return None


def find_quectel_at_port(preferred=None):
    if preferred:
        for port in list_ports.comports():
            if port.device == preferred and "quectel" in (port.description or "").lower():
                return port.device
    exact = find_port("Quectel USB AT Port")
    if exact:
        return exact
    for port in list_ports.comports():
        text = f"{port.description} {port.hwid}".lower()
        if "quectel" in text and (" at " in f" {text} " or "usb at port" in text):
            return port.device
    return None


def send_at(port, command, timeout=1.0):
    with serial.Serial(port, 115200, timeout=0.15, write_timeout=1) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(f"{command}\r\n".encode("utf-8"))
        ser.flush()
        deadline = time.monotonic() + timeout
        raw = bytearray()
        while time.monotonic() < deadline:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                raw.extend(chunk)
                text = raw.decode("utf-8", errors="replace")
                if "\r\nOK\r\n" in text or "\r\nERROR\r\n" in text:
                    return text
            time.sleep(0.03)
        return raw.decode("utf-8", errors="replace")


def clean_at_response(text, command):
    lines = []
    for line in text.replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line or line == command or line in {"OK", "ERROR"}:
            continue
        lines.append(line)
    return lines


def first_match(text, pattern, default=""):
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else default


def quectel_model_from_ati(ati):
    lines = clean_at_response(ati, "ATI")
    model = ""
    revision = first_match(ati, r"Revision:\s*([^\r\n]+)", "")
    for line in lines:
        if line.upper().startswith(("EC", "EG", "BG", "RG")):
            model = line
            break
    return model, revision


def read_repl_value(port, expression, timeout=3.0):
    with serial.Serial(port, 115200, timeout=0.15, write_timeout=1) as ser:
        ser.reset_input_buffer()
        ser.write(b"\r\n")
        ser.flush()
        time.sleep(0.15)
        ser.read(4096)
        marker = "__EP100_VALUE__"
        ser.write(f"print('{marker}', {expression})\r\n".encode("utf-8"))
        ser.flush()
        deadline = time.monotonic() + timeout
        raw = bytearray()
        while time.monotonic() < deadline:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                raw.extend(chunk)
                if raw.endswith(b">>> "):
                    break
            time.sleep(0.03)
        text = raw.decode("utf-8", errors="replace")
        for line in text.replace("\r", "\n").split("\n"):
            line = line.strip()
            if line.startswith(marker):
                return line[len(marker) :].strip()
    return ""


def read_quectel_system_info(selected_port=None, module_mode="auto"):
    at_port = find_quectel_at_port(selected_port)
    repl_port = find_port("Quectel USB REPL Port")
    if not at_port:
        raise RuntimeError("No se encontro el puerto AT Quectel para lectura fallback")

    ati = send_at(at_port, "ATI")
    cpin = send_at(at_port, "AT+CPIN?")
    cimi = send_at(at_port, "AT+CIMI")
    csq_text = send_at(at_port, "AT+CSQ")
    cops = send_at(at_port, "AT+COPS?")
    cereg = send_at(at_port, "AT+CEREG?")
    creg = send_at(at_port, "AT+CREG?")
    cgatt = send_at(at_port, "AT+CGATT?")
    cgdcont = send_at(at_port, "AT+CGDCONT?")
    cgpaddr = send_at(at_port, "AT+CGPADDR")
    qccid = send_at(at_port, "AT+QCCID")
    ccid = send_at(at_port, "AT+CCID")

    model, firmware = quectel_model_from_ati(ati)
    imsi_lines = clean_at_response(cimi, "AT+CIMI")
    imsi = imsi_lines[0] if imsi_lines else ""
    csq = first_match(csq_text, r"\+CSQ:\s*(\d+)", "99")
    reg = first_match(cereg, r"\+CEREG:\s*\d+,(\d+)", "") or first_match(creg, r"\+CREG:\s*\d+,(\d+)", "0")
    operator = first_match(cops, r'\+COPS:\s*\d+,\d+,"([^"]+)"', "")
    apn = first_match(cgdcont, r'\+CGDCONT:\s*1,"[^"]+","([^"]*)"', "")
    ip = first_match(cgdcont, r'\+CGDCONT:\s*1,"[^"]+","[^"]*","([^"]*)"', "")
    if not ip or ip == " ":
        ip = first_match(cgpaddr, r'\+CGPADDR:\s*1,\s*"?([^"\r\n, ]+)"?', "")
    attached = first_match(cgatt, r"\+CGATT:\s*(\d+)", "0")
    sim_ready = "+CPIN: READY" in cpin
    at_iccid = first_match(qccid, r"\+QCCID:\s*([0-9A-Fa-f]+)", "") or first_match(ccid, r"\+CCID:\s*([0-9A-Fa-f]+)", "")

    iccid = ""
    imei = ""
    signal = ""
    config = {}
    net_state = None
    data_call = None
    sim_status = None
    if repl_port:
        try:
            sim_status = int(read_repl_value(repl_port, "__import__('sim').getStatus()") or 0)
        except Exception:
            sim_status = None
        iccid = read_repl_value(repl_port, "__import__('sim').getIccid()")
        imei = read_repl_value(repl_port, "__import__('modem').getDevImei()")
        signal = read_repl_value(repl_port, "__import__('net').getSignal()[1]")
        try:
            net_state = literal_eval(read_repl_value(repl_port, "__import__('net').getState()"))
        except Exception:
            net_state = None
        try:
            data_call = literal_eval(read_repl_value(repl_port, "__import__('dataCall').getInfo(1,0)"))
        except Exception:
            data_call = None
        config_text = read_repl_value(
            repl_port,
            "__import__('usr.a_network').a_network.netManager._system_config",
        )
        try:
            config = json.loads(config_text.replace("'", '"').replace("None", "null").replace("True", "true").replace("False", "false"))
        except Exception:
            config = {}
    if not imei:
        imei = first_match(send_at(at_port, "AT+CGSN"), r"([0-9]{14,17})", "")

    if isinstance(net_state, tuple) and len(net_state) > 1 and isinstance(net_state[1], (list, tuple)) and net_state[1] and net_state[1][0]:
        reg = str(net_state[1][0])
    if isinstance(data_call, tuple) and len(data_call) > 2:
        attached = str(data_call[0])
        if isinstance(data_call[2], (list, tuple)) and len(data_call[2]) > 2 and data_call[2][2] and data_call[2][2] != "0.0.0.0":
            ip = data_call[2][2]

    data = {
        "sn": config.get("sn") or imei,
        "sfn": config.get("sfn") or model or ("EC200-A-AU" if module_mode == "ec200a" else "Quectel"),
        "sfv": config.get("sfv") or "",
        "frv": firmware or config.get("frv") or "",
        "passwd": config.get("passwd") or "",
        "linkled": config.get("linkled", 0),
        "noNetRst": config.get("noNetRst", 0),
        "simEXT": config.get("simEXT", True),
        "apnName": config.get("apnName") or "",
        "apnUser": config.get("apnUser") or "",
        "apnPass": config.get("apnPass") or "",
        "apnAuth": config.get("apnAuth", 0),
        "ntpHost": config.get("ntpHost") or "",
        "ntpTime": config.get("ntpTime", 0),
        "fota": config.get("fota") or "",
        "rst": config.get("rst") or "0",
        "sim": sim_status if sim_status is not None else (1 if sim_ready else 0),
        "iccid": iccid or config.get("iccid") or at_iccid or imsi,
        "imsi": imsi,
        "operator": operator,
        "reg": int(reg) if str(reg).isdigit() else 0,
        "attached": int(attached) if str(attached).isdigit() else 0,
        "ip": ip,
        "apnActive": apn,
        "csq": int(csq) if str(csq).isdigit() else 99,
        "signal": signal or config.get("signal") or "",
        "moduleMode": module_mode,
        "model": model,
        "source": f"AT:{at_port}" + (f", REPL:{repl_port}" if repl_port else ""),
    }
    return {"type": "getSystemInfoRsp", "data": data}


def write_quectel_system_info(data, selected_port=None):
    at_port = find_quectel_at_port(selected_port)
    if not at_port:
        raise RuntimeError("No se encontro el puerto AT Quectel para configurar APN")
    apn = (data or {}).get("apnName", "")
    user = (data or {}).get("apnUser", "")
    password = (data or {}).get("apnPass", "")
    auth = int((data or {}).get("apnAuth") or 0)
    pdp_type = "IPV4V6"
    commands = []
    if apn:
        commands.append(f'AT+CGDCONT=1,"{pdp_type}","{apn}"')
    else:
        commands.append(f'AT+CGDCONT=1,"{pdp_type}",""')
    if user or password or auth:
        commands.append(f'AT+CGAUTH=1,{auth},"{password}","{user}"')
    raw = []
    for command in commands:
        raw.append(send_at(at_port, command, timeout=2.0))
    return {"type": "setSystemInfoRsp", "data": {"code": 0, "source": f"AT:{at_port}", "raw": "\n".join(raw)}}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def send_json(self, status, body):
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/api/ports":
            ports = [
                {
                    "device": port.device,
                    "description": port.description,
                    "hwid": port.hwid,
                }
                for port in list_ports.comports()
            ]
            self.send_json(200, {"ports": ports})
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/command":
            self.send_json(404, {"error": "Ruta no encontrada"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            port = body.get("port") or "COM9"
            baudrate = body.get("baudRate") or 9600
            module_mode = body.get("moduleMode") or "ep100"
            command = body.get("command")
            if isinstance(command, dict):
                payload = json.dumps(command, separators=(",", ":"))
            elif isinstance(command, str):
                payload = command
            else:
                raise ValueError("command debe ser objeto JSON o string")
            if isinstance(command, dict) and command.get("type") == "getSystemInfo" and module_mode in {"ec200a", "auto"}:
                response = read_quectel_system_info(port, module_mode)
                self.send_json(200, {"response": response, "raw": "Quectel USB AT/REPL"})
                return
            if isinstance(command, dict) and command.get("type") == "setSystemInfo" and module_mode in {"ec200a", "auto"}:
                response = write_quectel_system_info(command.get("data") or {}, port)
                self.send_json(200, {"response": response, "raw": "Quectel USB AT"})
                return
            try:
                response, raw = send_serial_command(port, baudrate, payload, float(body.get("timeoutMs") or 5000) / 1000)
            except Exception:
                if isinstance(command, dict) and command.get("type") == "getSystemInfo":
                    response = read_quectel_system_info(port, module_mode)
                    raw = "Fallback Quectel USB AT/REPL"
                else:
                    raise
            self.send_json(200, {"response": response, "raw": raw})
        except Exception as exc:
            print(f"API ERROR: {exc}", flush=True)
            self.send_json(500, {"error": str(exc)})


if __name__ == "__main__":
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", 5173), Handler)
    print("EP100 web app: http://localhost:5173")
    server.serve_forever()

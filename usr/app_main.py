import _thread
import gc
import log
import ujson
import usocket
import utime
from machine import UART
from misc import Power
try:
    from misc import USBNET
except:
    USBNET = None
import dataCall
import modem
import net
import sim
from usr.WebSrv import WebSrv

log.basicConfig(level=log.INFO)
logger = log.getLogger("MAIN")

CONFIG_PATH = "/usr/config.json"
WEB_PORT = 8080
FIRMWARE_VERSION = "EG800K-EP100-0.1.0"
CONFIG_VERSION = 4
USB_BOOT_GPIO = None
AUTH_REALM = "NodeWay EG800K"
SESSION_COOKIE = "nodeway_session"
SESSION_TTL_MS = 24 * 3600 * 1000
auth_sessions = {}

uart1 = None
uart2 = None
uart_lock = _thread.allocate_lock()
mqtt_lock = _thread.allocate_lock()
fota_state = {"status": "idle", "message": "Sin actividad", "progress": 0, "result": ""}
boot_ms = utime.ticks_ms()
sim_state = {
    "ready": False,
    "error": "",
    "iccid": "",
    "cpin": "",
    "qsimdet": "",
    "qsimstat": "",
    "qinistat": "",
}
runtime_state = {
    "registered": False,
    "ip": "",
}

OPERATOR_NAMES = {
    "732101": "Claro Colombia",
    "732103": "Tigo Colombia",
    "732111": "Tigo Colombia",
    "732123": "Movistar Colombia",
    "732130": "WOM Colombia",
}

SIM_PROVIDER_ALIASES = (
    ("imsi", "240075", "LaSeleNosLlama"),
    ("iccid", "894620", "LaSeleNosLlama"),
)


def read_config():
    with open(CONFIG_PATH, "r") as f:
        config = ujson.load(f)
    if "RS485_2" in config and "RS485" not in config:
        config["RS485"] = config["RS485_2"]
    if "RS485_1" in config and "RS485" not in config:
        config["RS485"] = config["RS485_1"]
    config = normalize_config(config)
    if apply_config_migrations(config):
        persist_config(config)
        config = normalize_config(config)
    return config


def persist_config(config):
    config = normalize_config(config)
    with open(CONFIG_PATH, "w") as f:
        f.write(ujson.dumps(config))


def write_config(config):
    persist_config(config)


def default_config():
    return {
        "CONFIG_VERSION": CONFIG_VERSION,
        "AUTH": {"User": "admin", "Pass": "admin"},
        "APN": {"Cid": 1, "PdpType": "IP", "Apn": "", "User": "", "Pass": "", "Auth": 0},
        "NETMODE": {"Mode": 12},
        "RS485": {
            "UARTn": 2,
            "group": 0,
            "GPIO_DIR": 25,
            "Puerto": 5000,
            "Vel": 9600,
            "DataBit": 8,
            "Paridad": 0,
            "StopBit": 1,
            "Timeout": 5000,
        },
        "RESTART": {"Enabled": True, "IntervalHours": 12, "MinUptimeSec": 600},
        "LEDS": {
            "Enabled": True,
            "NetStatusGpio": 29,
            "StatusGpio": 36,
            "ActiveLevel": 1,
            "StatusMode": "heartbeat",
        },
        "NETWORK": {
            "RegistrationTimeoutSec": 120,
            "PdpTimeoutSec": 60,
            "MonitorIntervalSec": 15,
            "StackRestartAfterNoNetworkSec": 300,
            "PowerRestartAfterNoNetworkSec": 900,
            "ResetPdpOnBoot": True,
        },
        "LOCAL_USB": {
            "Enabled": True,
            "Mode": "RNDIS",
            "OpenAfterPdp": True,
            "RestartAfterModeChange": False,
        },
        "MQTT": {
            "Enabled": True,
            "Host": "185.187.170.193",
            "Port": 1883,
            "IntervalSec": 300,
            "KeepAliveSec": 60,
            "TopicPrefix": "MetaSense/ModemEGmini",
            "ClientPrefix": "EG800K",
            "User": "",
            "Pass": "",
        },
        "MODEM_INIT": {
            "Enabled": True,
            "BootDelaySec": 10,
            "SimTimeoutSec": 30,
            "DisableSimHotplug": True,
            "RestartAfterQsimdet": False,
            "UsbBootGpio": None,
            "ExternalSim": True,
            "SimSwitchGpio": 28,
            "SimExternalLevel": 1,
            "RestartStackAfterSimSwitch": True,
        },
    }


def merge_dict(base, override):
    out = {}
    for k in base:
        if isinstance(base[k], dict):
            out[k] = merge_dict(base[k], override.get(k, {}) if isinstance(override, dict) else {})
        else:
            out[k] = override.get(k, base[k]) if isinstance(override, dict) else base[k]
    if isinstance(override, dict):
        for k in override:
            if k not in out:
                out[k] = override[k]
    return out


def normalize_config(config):
    if not isinstance(config, dict):
        config = {}
    defaults = default_config()
    if "RS485_2" in config and "RS485" not in config:
        config["RS485"] = config["RS485_2"]
    if "RS485_1" in config and "RS485" not in config:
        config["RS485"] = config["RS485_1"]
    merged = merge_dict(defaults, config)
    try:
        merged["CONFIG_VERSION"] = int(merged.get("CONFIG_VERSION", CONFIG_VERSION) or CONFIG_VERSION)
    except:
        merged["CONFIG_VERSION"] = CONFIG_VERSION
    return merged


def apply_config_migrations(config):
    changed = False
    try:
        version = int(config.get("CONFIG_VERSION", 1) or 1)
    except:
        version = 1

    network = config.setdefault("NETWORK", {})
    stack = int(network.get("StackRestartAfterNoNetworkSec", 0) or 0)
    power = int(network.get("PowerRestartAfterNoNetworkSec", 0) or 0)

    if version < 2:
        usb = config.setdefault("LOCAL_USB", {})
        if usb.get("RestartAfterModeChange", True):
            logger.info("CONFIG migration: RestartAfterModeChange -> false")
            usb["RestartAfterModeChange"] = False
            changed = True
        config["CONFIG_VERSION"] = 2
        changed = True
        version = 2

    if version < 3:
        if stack == 0 and power == 0:
            network["StackRestartAfterNoNetworkSec"] = 300
            network["PowerRestartAfterNoNetworkSec"] = 900
            logger.info(
                "CONFIG migration v3: network recovery enabled stack=300s power=900s"
            )
            changed = True
        config["CONFIG_VERSION"] = 3
        changed = True
        version = 3

    if version < CONFIG_VERSION:
        netmode = config.setdefault("NETMODE", {})
        if int(netmode.get("Mode", 5) or 5) == 5:
            netmode["Mode"] = 12
            logger.info("CONFIG migration v4: NETMODE.Mode 5 (4G default) -> 12 (Auto)")
            changed = True
        config["CONFIG_VERSION"] = CONFIG_VERSION
        changed = True

    return changed


def restart_policy_payload(config):
    restart = config.get("RESTART", {})
    network = config.get("NETWORK", {})
    stack = int(network.get("StackRestartAfterNoNetworkSec", 0) or 0)
    power = int(network.get("PowerRestartAfterNoNetworkSec", 0) or 0)
    return {
        "Enabled": bool(restart.get("Enabled", True)),
        "IntervalHours": float(restart.get("IntervalHours", 12) or 12),
        "IntervalSeconds": int(restart.get("IntervalSeconds", 0) or 0),
        "MinUptimeSec": int(restart.get("MinUptimeSec", 600) or 600),
        "NetworkRecoveryEnabled": stack > 0 or power > 0,
        "StackRestartAfterNoNetworkSec": stack,
        "PowerRestartAfterNoNetworkSec": power,
        "ConfigVersion": int(config.get("CONFIG_VERSION", CONFIG_VERSION) or CONFIG_VERSION),
    }


def mqtt_config_payload(config):
    mqtt = config.get("MQTT", {})
    imei = safe_call(modem.getDevImei, "") or "unknown"
    topic_prefix = str(mqtt.get("TopicPrefix", "MetaSense/ModemEGmini"))
    return {
        "Enabled": bool(mqtt.get("Enabled", True)),
        "Host": str(mqtt.get("Host", "")),
        "Port": int(mqtt.get("Port", 1883) or 1883),
        "IntervalSec": int(mqtt.get("IntervalSec", 300) or 300),
        "KeepAliveSec": int(mqtt.get("KeepAliveSec", 60) or 60),
        "TopicPrefix": topic_prefix,
        "Topic": "{}/{}".format(topic_prefix, imei),
        "ClientPrefix": str(mqtt.get("ClientPrefix", "EG800K")),
        "User": str(mqtt.get("User", "")),
        "Pass": str(mqtt.get("Pass", "")),
    }


def json_response(response, payload, code=200, extra_headers=None):
    headers = {"Access-Control-Allow-Origin": "*"}
    if extra_headers:
        for key in extra_headers:
            headers[key] = extra_headers[key]
    response.WriteResponse(
        code,
        headers,
        "application/json",
        "UTF-8",
        ujson.dumps(payload),
    )


def get_cookie(headers, name):
    cookie_header = headers.get("cookie", "")
    if not cookie_header:
        return ""
    target = name + "="
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(target):
            return part[len(target) :]
    return ""


def parse_basic_auth(headers):
    auth = headers.get("authorization", "")
    if not auth or auth[:6].lower() != "basic ":
        return "", ""
    try:
        import ubinascii

        raw = auth[6:].strip()
        padding = (-len(raw)) % 4
        if padding:
            raw += "=" * padding
        decoded = ubinascii.a2b_base64(raw).decode()
        sep = decoded.find(":")
        if sep < 0:
            return decoded, ""
        return decoded[:sep], decoded[sep + 1 :]
    except Exception as e:
        logger.error("basic auth parse error {}".format(e))
        return "", ""


def get_auth_credentials():
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = ujson.load(f)
        auth = cfg.get("AUTH", {})
        return str(auth.get("User", "admin")).strip(), str(auth.get("Pass", "admin"))
    except:
        return "admin", "admin"


def credentials_valid(user, password):
    expected_user, expected_pass = get_auth_credentials()
    return str(user).strip() == expected_user and str(password) == expected_pass


def create_session_token(user):
    imei = safe_call(modem.getDevImei, "0")
    return "{:08x}{:08x}{:08x}".format(
        utime.ticks_ms() & 0xFFFFFFFF,
        utime.time() & 0xFFFFFFFF,
        (len(user) * 131 + len(imei) * 17 + (ord(user[0]) if user else 0)) & 0xFFFFFFFF,
    )


def register_session(token):
    auth_sessions[token] = utime.time() + 86400


def session_valid(token):
    if not token:
        return False
    expiry = auth_sessions.get(token)
    if not expiry:
        return False
    if utime.time() >= expiry:
        auth_sessions.pop(token, None)
        return False
    return True


def invalidate_session(token):
    if token:
        auth_sessions.pop(token, None)


def is_authenticated(client):
    headers = client.GetRequestHeaders()
    token = get_cookie(headers, SESSION_COOKIE)
    if session_valid(token):
        return True
    user, password = parse_basic_auth(headers)
    return credentials_valid(user, password)


def require_auth(client, response):
    if is_authenticated(client):
        return True
    response.WriteResponseUnauthorized(AUTH_REALM)
    return False


def auth_route(url, method="GET"):
    def decorator(func):
        @WebSrv.route(url, method)
        def wrapped(client, response, *args):
            if not require_auth(client, response):
                return
            return func(client, response, *args)

        return func

    return decorator


def serve_www_file(response, filename, content_type):
    response.WriteResponseFile(
        "/usr/www/" + filename,
        content_type,
        headers={"Cache-Control": "no-cache"},
    )


def ok_response(response, content):
    response.WriteResponse(
        200,
        {"Cache-Control": "no-cache"},
        "text/html",
        "UTF-8",
        content,
    )


def get_uart(conf):
    global uart1, uart2
    u_id = conf.get("UARTn", 1)
    if u_id == 1:
        if uart1 is None:
            uart1 = UART(
                UART.UART1,
                conf.get("Vel", 9600),
                conf.get("DataBit", 8),
                conf.get("Paridad", 0),
                conf.get("StopBit", 1),
                0,
                conf.get("group", 0),
            )
            uart1.control_485(conf.get("GPIO_DIR", 24), 1)
        return uart1

    if uart2 is None:
        uart2 = UART(
            UART.UART2,
            conf.get("Vel", 9600),
            conf.get("DataBit", 8),
            conf.get("Paridad", 0),
            conf.get("StopBit", 1),
            0,
        )
        uart2.control_485(conf.get("GPIO_DIR", 25), 1)
    return uart2


def socket_tcp_server():
    try:
        return usocket.socket(
            usocket.AF_INET, usocket.SOCK_STREAM, usocket.IPPROTO_TCP_SER
        )
    except:
        return usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)


def socket_tcp_client(local_ip):
    try:
        sock = usocket.socket(
            usocket.AF_INET, usocket.SOCK_STREAM, usocket.TCP_CUSTOMIZE_PORT
        )
    except:
        sock = usocket.socket(usocket.AF_INET, usocket.SOCK_STREAM)
    if local_ip:
        sock.bind((local_ip, 0))
    return sock


def resolve_host_addr(host, port):
    host = str(host or "").strip()
    port = int(port)
    parts = host.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return (host, port)
    return usocket.getaddrinfo(host, port)[0][-1]


def mqtt_connect_retriable_errno(errno):
    try:
        return int(errno) in (103, 104, 107, 110, 111, 113, 116)
    except:
        return False


def client_conn_proc(conn, ip_addr, port, conf):
    u_inst = get_uart(conf)
    timeout = conf.get("Timeout", 500)
    try:
        conn.settimeout(30)
        while True:
            data = conn.recv(1024)
            if not data:
                break

            with uart_lock:
                u_inst.write(data)
                start = utime.ticks_ms()
                resp = b""
                while utime.ticks_diff(utime.ticks_ms(), start) < timeout:
                    pending = u_inst.any()
                    if pending:
                        resp += u_inst.read(pending)
                        utime.sleep_ms(10)
                    elif resp:
                        break

                if resp:
                    conn.send(resp)
                else:
                    conn.send(b"")
            gc.collect()
    except Exception as e:
        logger.error("TCP client {}:{} error {}".format(ip_addr, port, e))
    finally:
        try:
            conn.close()
        except:
            pass


def tcp_server(address, port, conf):
    try:
        sock = socket_tcp_server()
        sock.setsockopt(usocket.SOL_SOCKET, usocket.SO_REUSEADDR, 1)
        sock.bind((address, port))
        sock.listen(5)
        logger.info("TCP bridge listening on {}:{}".format(address, port))
        while True:
            cli_conn, cli_addr = sock.accept()
            try:
                cli_ip, cli_port = cli_addr
            except:
                cli_ip, cli_port = "unknown", 0
            _thread.start_new_thread(client_conn_proc, (cli_conn, cli_ip, cli_port, conf))
    except Exception as e:
        logger.error("TCP server {}:{} error {}".format(address, port, e))


def at_response_text(resp):
    try:
        if isinstance(resp, (bytes, bytearray)):
            return resp.decode()
    except:
        pass
    try:
        return str(resp)
    except:
        return ""


def send_at(cmd, timeout=2):
    try:
        atcmd = __import__("atcmd")
    except Exception as e:
        logger.error("AT backend unavailable for {}: {}".format(cmd, e))
        return ""

    methods = ("sendSync", "send", "cmd", "at")
    payloads = (cmd, cmd + "\r\n")
    for name in methods:
        fn = getattr(atcmd, name, None)
        if not fn:
            continue
        for payload in payloads:
            if name == "sendSync":
                try:
                    resp = bytearray(512)
                    ret = fn(payload, resp, "", int(timeout))
                    text = at_response_text(resp).strip("\x00")
                    logger.info("AT {} -> ret {} {}".format(cmd, ret, text))
                    if ret == 0:
                        return text
                except:
                    pass
            try:
                resp = fn(payload, timeout)
                text = at_response_text(resp)
                logger.info("AT {} -> {}".format(cmd, text))
                return text
            except TypeError:
                try:
                    resp = fn(payload)
                    text = at_response_text(resp)
                    logger.info("AT {} -> {}".format(cmd, text))
                    return text
                except:
                    pass
            except:
                pass
    logger.error("AT command failed or unsupported: {}".format(cmd))
    return ""


def ensure_usb_boot_safe(init_cfg):
    gpio = init_cfg.get("UsbBootGpio", USB_BOOT_GPIO)
    if gpio is None or gpio == "":
        logger.info("USB_BOOT: not controlled by firmware")
        return
    try:
        from machine import Pin
        pin = Pin(int(gpio), Pin.IN)
        logger.info("USB_BOOT GPIO {} configured as input".format(gpio))
        return pin
    except Exception as e:
        logger.error("USB_BOOT GPIO {} safe config error {}".format(gpio, e))


def set_sim_slot(init_cfg):
    if not init_cfg.get("ExternalSim", True):
        logger.info("SIM slot: internal SIM selected by config")
        return
    gpio = init_cfg.get("SimSwitchGpio", 28)
    level = int(init_cfg.get("SimExternalLevel", 1))
    try:
        from machine import Pin
        pin_name = "GPIO{}".format(int(gpio))
        pin_id = getattr(Pin, pin_name)
        pin = Pin(pin_id, Pin.OUT, Pin.PULL_DISABLE, level)
        pin.write(level)
        logger.info("SIM slot: external SIM selected on {} level {}".format(pin_name, level))
        if init_cfg.get("RestartStackAfterSimSwitch", True):
            try:
                logger.info("SIM slot: restarting modem stack after SIM switch")
                net.setModemFun(0, 0)
                utime.sleep(2)
                net.setModemFun(1, 0)
                utime.sleep(6)
            except Exception as e:
                logger.error("SIM slot modem stack restart error {}".format(e))
    except Exception as e:
        logger.error("SIM slot select error GPIO{} level {}: {}".format(gpio, level, e))


def extract_iccid(text):
    if not text:
        return ""
    raw = str(text)
    digits = ""
    best = ""
    for ch in raw:
        if ch >= "0" and ch <= "9":
            digits += ch
        else:
            if len(digits) > len(best):
                best = digits
            digits = ""
    if len(digits) > len(best):
        best = digits
    if len(best) >= 10:
        return best
    return ""


def is_sim_ready():
    if sim_state.get("ready"):
        return True
    try:
        return sim.getStatus() == 1
    except:
        return False


def format_operator(mcc, mnc):
    if not mcc or not mnc:
        return "N/A"
    plmn = str(mcc) + str(mnc)
    name = OPERATOR_NAMES.get(plmn, "")
    if name:
        return "{} ({})".format(name, plmn)
    return plmn


def sim_provider_alias():
    imsi = str(safe_call(sim.getImsi, "") or "")
    iccid = str(safe_call(sim.getIccid, "") or sim_state.get("iccid", "") or "")
    for field, prefix, name in SIM_PROVIDER_ALIASES:
        value = imsi if field == "imsi" else iccid
        if value.startswith(prefix):
            return name
    return ""


def extract_quoted_plmn(text):
    raw = str(text)
    start = raw.find('"')
    if start < 0:
        return ""
    end = raw.find('"', start + 1)
    if end < 0:
        return ""
    value = raw[start + 1 : end]
    if len(value) >= 5:
        return value
    return ""


def is_valid_plmn(value):
    value = str(value or "")
    if len(value) < 5 or len(value) > 6:
        return False
    for ch in value:
        if ch < "0" or ch > "9":
            return False
    return True


def network_operator():
    cops = send_at("AT+COPS?", 2)
    plmn = extract_quoted_plmn(cops)
    if is_valid_plmn(plmn):
        return format_operator(plmn[0:3], plmn[3:])

    mode = safe_call(net.getNetMode, None)
    if isinstance(mode, (tuple, list)) and len(mode) > 2:
        mcc = mode[1]
        mnc = mode[2]
        if is_valid_plmn(str(mcc) + str(mnc)):
            return format_operator(mcc, mnc)

    operator = safe_call(net.operatorName, "")
    if isinstance(operator, (tuple, list)) and len(operator) > 1:
        operator = operator[1]
    if operator not in ("", -1, "-1", None) and operator != sim_provider_alias():
        return operator
    return "N/A"


def modem_init(init_cfg):
    ensure_usb_boot_safe(init_cfg)
    set_sim_slot(init_cfg)
    boot_delay = int(init_cfg.get("BootDelaySec", 10))
    if boot_delay < 8:
        boot_delay = 8
    logger.info("MODEM_INIT: waiting {} seconds before SIM query".format(boot_delay))
    utime.sleep(boot_delay)

    send_at("AT", 2)
    send_at("ATE0", 2)
    send_at("AT+CMEE=2", 2)
    send_at("AT+CFUN?", 2)
    sim_state["qsimdet"] = send_at("AT+QSIMDET?", 2)

    if init_cfg.get("DisableSimHotplug", True):
        sim_state["qsimdet"] = send_at("AT+QSIMDET=0,0", 2) or sim_state["qsimdet"]
        send_at("AT&W", 3)
        if init_cfg.get("RestartAfterQsimdet", False):
            logger.info("MODEM_INIT: restarting modem after QSIMDET change")
            send_at("AT+CFUN=1,1", 2)
            utime.sleep(12)


def wait_sim_ready(timeout=30):
    deadline = utime.ticks_add(utime.ticks_ms(), int(timeout) * 1000)
    last_error = "SIM not ready"
    while utime.ticks_diff(deadline, utime.ticks_ms()) > 0:
        cpin = send_at("AT+CPIN?", 2)
        qccid = send_at("AT+QCCID", 2)
        ccid = ""
        if not extract_iccid(qccid):
            ccid = send_at("AT+CCID", 2)
        qinistat = send_at("AT+QINISTAT", 2)
        qsimstat = send_at("AT+QSIMSTAT?", 2)

        sim_state["cpin"] = cpin
        sim_state["qinistat"] = qinistat
        sim_state["qsimstat"] = qsimstat

        iccid = extract_iccid(qccid)
        if not iccid:
            iccid = extract_iccid(ccid)
        if not iccid:
            try:
                iccid = extract_iccid(sim.getIccid())
            except:
                iccid = ""
        sim_state["iccid"] = iccid

        ready_by_at = "+CPIN: READY" in str(cpin)
        ready_by_api = False
        try:
            ready_by_api = sim.getStatus() == 1
        except:
            pass

        logger.info("SIM check CPIN={} ICCID={} QINISTAT={} QSIMSTAT={}".format(cpin, iccid, qinistat, qsimstat))
        if (ready_by_at or ready_by_api) and iccid:
            sim_state["ready"] = True
            sim_state["error"] = ""
            logger.info("SIM_READY ICCID={}".format(iccid))
            return True

        if "SIM not inserted" in str(cpin) or "NOT READY" in str(cpin) or "CME ERROR" in str(cpin):
            last_error = str(cpin)
        elif not iccid:
            last_error = "ICCID not available"
        utime.sleep(2)

    sim_state["ready"] = False
    sim_state["error"] = last_error
    logger.error("SIM_ERROR {}".format(last_error))
    return False


def eg800k_modem_startup(config):
    init_cfg = config.get("MODEM_INIT", {})
    if not init_cfg.get("Enabled", True):
        logger.info("MODEM_INIT disabled by config")
        return True
    modem_init(init_cfg)
    return wait_sim_ready(int(init_cfg.get("SimTimeoutSec", 30)))


def modem_status_payload():
    signal = ([99, 99, 255, 255], [99, 99, 255, 255, 255])
    state = None
    ip = "0.0.0.0"
    try:
        signal = net.getSignal()
    except:
        pass
    try:
        state = net.getState()
    except:
        pass
    try:
        ip = dataCall.getInfo(1, 0)[2][2]
    except:
        pass

    lte = signal[1] if signal and len(signal) > 1 else [99, 99, 255, 255, 255]
    operator = network_operator()

    net_mode = safe_call(net.getNetMode, None)
    net_mode_value = None
    if isinstance(net_mode, (tuple, list)) and len(net_mode) > 3:
        net_mode_value = net_mode[3]
    elif isinstance(net_mode, int):
        net_mode_value = net_mode

    try:
        saved_mode = int(read_config().get("NETMODE", {}).get("Mode", 12))
    except:
        saved_mode = 12
    net_config_value = saved_mode

    local_usb = {"available": USBNET is not None, "worktype": None, "status": None}
    if USBNET is not None:
        try:
            local_usb["worktype"] = USBNET.get_worktype()
        except:
            pass
        try:
            local_usb["status"] = USBNET.get_status()
        except:
            pass

    return {
        "IMEI": safe_call(modem.getDevImei, ""),
        "Serial": safe_call(modem.getDevSN, ""),
        "Firmware": FIRMWARE_VERSION,
        "ModemFirmware": safe_call(modem.getDevFwVersion, ""),
        "Modelo": safe_call(modem.getDevModel, ""),
        "SIM_Status": safe_call(sim.getStatus, -1),
        "SIM_Init": "SIM_READY" if sim_state.get("ready") else "SIM_ERROR",
        "SIM_Init_Error": sim_state.get("error", ""),
        "SIM_CPIN": sim_state.get("cpin", ""),
        "SIM_QSIMDET": sim_state.get("qsimdet", ""),
        "SIM_QINISTAT": sim_state.get("qinistat", ""),
        "SIM_QSIMSTAT": sim_state.get("qsimstat", ""),
        "ICCID": safe_call(sim.getIccid, "") or sim_state.get("iccid", ""),
        "IMSI": safe_call(sim.getImsi, ""),
        "ProveedorSIM": sim_provider_alias(),
        "Operador": operator,
        "Registro": state,
        "IP_SIM": ip,
        "NetMode": net_mode_value,
        "NetModeText": net_mode_to_text(net_mode_value),
        "NetModeConfig": net_config_value,
        "LocalUSB": local_usb,
        "RSSI": lte[0] if len(lte) > 0 else 99,
        "RSRP": lte[1] if len(lte) > 1 else 99,
        "RSRQ": lte[2] if len(lte) > 2 else 255,
        "CQI": lte[3] if len(lte) > 3 else 255,
        "SINR": lte[4] if len(lte) > 4 else 255,
        "UptimeSec": int(utime.ticks_diff(utime.ticks_ms(), boot_ms) / 1000),
        "Motivo_Arranque": safe_call(Power.powerOnReason, ""),
        "Motivo_Apagado": safe_call(Power.powerDownReason, ""),
        "Estado_Supercondensador": "",
    }


def mqtt_test_payload():
    status = modem_status_payload()
    return {
        "event": "test",
        "imei": status.get("IMEI", ""),
        "ip": runtime_state.get("ip") or status.get("IP_SIM", ""),
        "firmware": status.get("Firmware", ""),
        "operator": status.get("Operador", ""),
        "net_mode": status.get("NetModeText", ""),
        "rssi": status.get("RSSI", 99),
        "rsrp": status.get("RSRP", 99),
        "rsrq": status.get("RSRQ", 255),
        "cqi": status.get("CQI", 255),
        "sinr": status.get("SINR", 255),
        "timestamp": utime.time(),
    }


def merge_mqtt_request(body, base=None):
    if base is None:
        base = read_config().get("MQTT", {})
    mqtt = {
        "Host": str(base.get("Host", "")).strip(),
        "Port": int(base.get("Port", 1883) or 1883),
        "KeepAliveSec": int(base.get("KeepAliveSec", 60) or 60),
        "TopicPrefix": str(base.get("TopicPrefix", "MetaSense/ModemEGmini")).strip(),
        "ClientPrefix": str(base.get("ClientPrefix", "EG800K")).strip(),
        "User": str(base.get("User", "")).strip(),
        "Pass": str(base.get("Pass", "")),
    }
    if isinstance(body, dict):
        if "Host" in body:
            mqtt["Host"] = str(body.get("Host", mqtt["Host"])).strip()
        if "Port" in body:
            mqtt["Port"] = int(body.get("Port", mqtt["Port"]) or mqtt["Port"])
        if "KeepAliveSec" in body:
            mqtt["KeepAliveSec"] = int(body.get("KeepAliveSec", mqtt["KeepAliveSec"]) or mqtt["KeepAliveSec"])
        if "TopicPrefix" in body:
            mqtt["TopicPrefix"] = str(body.get("TopicPrefix", mqtt["TopicPrefix"])).strip()
        if "ClientPrefix" in body:
            mqtt["ClientPrefix"] = str(body.get("ClientPrefix", mqtt["ClientPrefix"])).strip()
        if "User" in body:
            mqtt["User"] = str(body.get("User", mqtt["User"])).strip()
        if "Pass" in body:
            mqtt["Pass"] = str(body.get("Pass", mqtt["Pass"]))
    return mqtt


def telemetry_payload():
    status = modem_status_payload()
    uptime = int(utime.ticks_diff(utime.ticks_ms(), boot_ms) / 1000)
    payload = {
        "imei": status.get("IMEI", ""),
        "serial": status.get("Serial", ""),
        "model": status.get("Modelo", ""),
        "firmware": status.get("Firmware", ""),
        "modem_firmware": status.get("ModemFirmware", ""),
        "uptime_sec": uptime,
        "sim_status": status.get("SIM_Status", -1),
        "sim_init": status.get("SIM_Init", ""),
        "iccid": status.get("ICCID", ""),
        "imsi": status.get("IMSI", ""),
        "operator": status.get("Operador", ""),
        "registered": bool(runtime_state.get("registered")),
        "registration": status.get("Registro", ""),
        "ip": runtime_state.get("ip") or status.get("IP_SIM", ""),
        "net_mode": status.get("NetMode", ""),
        "net_mode_text": status.get("NetModeText", ""),
        "local_usb": status.get("LocalUSB", {}),
        "rssi": status.get("RSSI", 99),
        "rsrp": status.get("RSRP", 99),
        "rsrq": status.get("RSRQ", 255),
        "cqi": status.get("CQI", 255),
        "sinr": status.get("SINR", 255),
        "boot_reason": status.get("Motivo_Arranque", ""),
        "shutdown_reason": status.get("Motivo_Apagado", ""),
    }
    try:
        cfg = read_config()
        payload["rs485"] = cfg.get("RS485", {})
        payload["mqtt_interval_sec"] = cfg.get("MQTT", {}).get("IntervalSec", 0)
    except:
        pass
    return payload


def safe_call(fn, default):
    try:
        return fn()
    except:
        return default


def ui_config_payload(config):
    return {
        "RS485": config.get("RS485", {}),
        "RS485_2": config.get("RS485", {}),
    }


def net_mode_to_text(mode):
    if mode in (0, 1, 3):
        return "2G"
    if mode in (2, 4, 5, 6, 8):
        return "3G"
    if mode in (7, 9):
        return "4G"
    return "UNKNOWN"


def pdp_type_to_int(value):
    if isinstance(value, int):
        return value
    text = str(value).upper()
    if text == "IPV6":
        return 1
    if text == "IPV4V6":
        return 2
    return 0


def pdp_type_to_str(value):
    if value == 1:
        return "IPV6"
    if value == 2:
        return "IPV4V6"
    return "IP"


def sanitize_apn_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        if not value or b"\x00" in value:
            return ""
        try:
            value = value.decode("utf-8")
        except:
            try:
                value = value.decode("latin-1")
            except:
                return ""
    text = str(value).strip()
    if not text:
        return ""
    for ch in text:
        code = ord(ch)
        if code < 32 or code == 127 or code == 0xFFFD:
            return ""
    return text


def get_apn_payload():
    config = read_config()
    cfg = config.get("APN", {})
    cid = int(cfg.get("Cid", 1))
    apn = sanitize_apn_text(cfg.get("Apn", ""))
    user = sanitize_apn_text(cfg.get("User", ""))
    password = sanitize_apn_text(cfg.get("Pass", ""))
    auth = int(cfg.get("Auth", 0) or 0)
    pdp_type = pdp_type_to_int(cfg.get("PdpType", "IP"))

    try:
        raw = dataCall.getPDPContext(cid)
        if raw and len(raw) > 1:
            pdp_type = raw[0]
            modem_apn = sanitize_apn_text(raw[1])
            if modem_apn:
                apn = modem_apn
            if len(raw) > 4:
                auth = int(raw[4] or 0)
            if auth > 0:
                modem_user = sanitize_apn_text(raw[2] if len(raw) > 2 else "")
                modem_pass = sanitize_apn_text(raw[3] if len(raw) > 3 else "")
                if modem_user:
                    user = modem_user
                if modem_pass:
                    password = modem_pass
    except:
        pass

    if auth <= 0:
        user = ""
        password = ""

    return {
        "cid": cid,
        "pdp_type": pdp_type,
        "pdp_type_str": pdp_type_to_str(pdp_type),
        "apn": apn,
        "user": user,
        "password": password,
        "auth": auth,
    }


@WebSrv.route("/login", "GET")
def route_login_page(client, response):
    serve_www_file(response, "login.html", "text/html")


@WebSrv.route("/login.css", "GET")
def route_login_css(client, response):
    serve_www_file(response, "login.css", "text/css")


@WebSrv.route("/login.js", "GET")
def route_login_js(client, response):
    serve_www_file(response, "login.js", "application/javascript")


@WebSrv.route("/favicon.svg", "GET")
def route_favicon(client, response):
    serve_www_file(response, "favicon.svg", "image/svg+xml")


@WebSrv.route("/command/login", "POST")
def route_login(client, response):
    try:
        body = client.ReadRequestContentAsJSON() or {}
        user = str(body.get("user", body.get("User", ""))).strip()
        password = str(body.get("pass", body.get("Pass", body.get("password", ""))))
        if not credentials_valid(user, password):
            json_response(response, {"status": "error", "message": "Credenciales invalidas"}, 401)
            return
        token = create_session_token(user)
        register_session(token)
        json_response(
            response,
            {"status": "success"},
            extra_headers={
                "Set-Cookie": "{}={}; Path=/; Max-Age=86400; HttpOnly".format(SESSION_COOKIE, token)
            },
        )
    except Exception as exc:
        logger.info("login error: {}".format(exc))
        json_response(response, {"status": "error", "message": "Error interno de autenticacion"}, 500)


@WebSrv.route("/command/auth-check", "GET")
def route_auth_check(client, response):
    if is_authenticated(client):
        json_response(response, {"status": "authenticated"})
    else:
        json_response(response, {"status": "unauthenticated"}, 401)


@auth_route("/command/logout", "POST")
def route_logout(client, response):
    token = get_cookie(client.GetRequestHeaders(), SESSION_COOKIE)
    invalidate_session(token)
    json_response(
        response,
        {"status": "success"},
        extra_headers={"Set-Cookie": "{}=; Path=/; Max-Age=0".format(SESSION_COOKIE)},
    )


@auth_route("/command/getmodemstatus", "GET")
def route_get_modem_status(client, response):
    json_response(response, modem_status_payload())


@WebSrv.route("/", "GET")
def route_root(client, response):
    if not is_authenticated(client):
        response.WriteResponseRedirect("/login")
        return
    serve_www_file(response, "index.html", "text/html")


@auth_route("/index.html", "GET")
def route_index_html(client, response):
    serve_www_file(response, "index.html", "text/html")


@auth_route("/index.css", "GET")
def route_index_css(client, response):
    serve_www_file(response, "index.css", "text/css")


@auth_route("/index.js", "GET")
def route_index_js(client, response):
    serve_www_file(response, "index.js", "application/javascript")


@auth_route("/command/getconfig", "GET")
def route_get_config(client, response):
    try:
        json_response(response, ui_config_payload(read_config()))
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/setconfig", "POST")
def route_set_config(client, response):
    try:
        body = client.ReadRequestContentAsJSON()
        config = read_config()
        if body:
            if "RS485" in body:
                config["RS485"].update(body["RS485"])
            if "RS485_2" in body:
                config["RS485"].update(body["RS485_2"])
        write_config(config)
        json_response(response, {"status": "success", "config": ui_config_payload(config)})
        logger.info("RESTART_REASON=config_change RS485")
        utime.sleep(1)
        Power.powerRestart()
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/restartmodem", "POST")
def route_restart_modem(client, response):
    json_response(response, {"status": "success"})
    logger.info("RESTART_REASON=manual_web")
    utime.sleep(1)
    Power.powerRestart()


@auth_route("/command/getapn", "GET")
def route_get_apn(client, response):
    json_response(response, get_apn_payload())


@auth_route("/command/setapn", "POST")
def route_set_apn(client, response):
    try:
        if not is_sim_ready():
            json_response(
                response,
                {"status": "error", "message": "SIM no esta READY; APN/PDP bloqueado"},
                409,
            )
            return
        body = client.ReadRequestContentAsJSON() or {}
        cid = int(body.get("cid", 1))
        pdp_type = pdp_type_to_int(body.get("pdp_type", "IP"))
        apn = sanitize_apn_text(body.get("apn", ""))
        user = sanitize_apn_text(body.get("user", ""))
        password = sanitize_apn_text(body.get("password", ""))
        auth = int(body.get("auth", 0))
        if auth <= 0:
            user = ""
            password = ""

        config = read_config()
        config["APN"] = {
            "Cid": cid,
            "PdpType": pdp_type_to_str(pdp_type),
            "Apn": apn,
            "User": user,
            "Pass": password,
            "Auth": auth,
        }
        write_config(config)

        try:
            dataCall.deactivate(cid)
        except:
            pass
        if apn:
            ret = dataCall.setPDPContext(cid, pdp_type, apn, user, password, auth)
        else:
            ret = dataCall.setPDPContext(cid, pdp_type, "", "", "", 0)
        try:
            dataCall.activate(cid)
        except:
            pass
        json_response(response, {"status": "success", "result": ret, "apn": get_apn_payload()})
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/getrestart", "GET")
def route_get_restart(client, response):
    json_response(response, restart_policy_payload(read_config()))


@auth_route("/command/setrestart", "POST")
def route_set_restart(client, response):
    try:
        body = client.ReadRequestContentAsJSON() or {}
        config = read_config()
        config["RESTART"].update(
            {
                "Enabled": bool(body.get("Enabled", True)),
                "IntervalHours": float(body.get("IntervalHours", 12)),
                "MinUptimeSec": int(
                    body.get("MinUptimeSec", config["RESTART"].get("MinUptimeSec", 600))
                ),
            }
        )
        if "IntervalSeconds" in body:
            config["RESTART"]["IntervalSeconds"] = int(body.get("IntervalSeconds") or 0)

        network = config.setdefault("NETWORK", {})
        if "NetworkRecoveryEnabled" in body:
            if bool(body.get("NetworkRecoveryEnabled")):
                network["StackRestartAfterNoNetworkSec"] = int(
                    body.get("StackRestartAfterNoNetworkSec", 300) or 300
                )
                network["PowerRestartAfterNoNetworkSec"] = int(
                    body.get("PowerRestartAfterNoNetworkSec", 900) or 900
                )
            else:
                network["StackRestartAfterNoNetworkSec"] = 0
                network["PowerRestartAfterNoNetworkSec"] = 0
        else:
            if "StackRestartAfterNoNetworkSec" in body:
                network["StackRestartAfterNoNetworkSec"] = int(
                    body.get("StackRestartAfterNoNetworkSec") or 0
                )
            if "PowerRestartAfterNoNetworkSec" in body:
                network["PowerRestartAfterNoNetworkSec"] = int(
                    body.get("PowerRestartAfterNoNetworkSec") or 0
                )

        write_config(config)
        json_response(
            response,
            {"status": "success", "RESTART": restart_policy_payload(config)},
        )
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/getmqtt", "GET")
def route_get_mqtt(client, response):
    json_response(response, mqtt_config_payload(read_config()))


@auth_route("/command/setmqtt", "POST")
def route_set_mqtt(client, response):
    try:
        body = client.ReadRequestContentAsJSON() or {}
        config = read_config()
        mqtt = config.setdefault("MQTT", {})
        mqtt.update(
            {
                "Enabled": bool(body.get("Enabled", mqtt.get("Enabled", True))),
                "Host": str(body.get("Host", mqtt.get("Host", ""))).strip(),
                "Port": int(body.get("Port", mqtt.get("Port", 1883)) or 1883),
                "IntervalSec": int(body.get("IntervalSec", mqtt.get("IntervalSec", 300)) or 300),
                "KeepAliveSec": int(body.get("KeepAliveSec", mqtt.get("KeepAliveSec", 60)) or 60),
                "TopicPrefix": str(body.get("TopicPrefix", mqtt.get("TopicPrefix", "MetaSense/ModemEGmini"))).strip(),
                "ClientPrefix": str(body.get("ClientPrefix", mqtt.get("ClientPrefix", "EG800K"))).strip(),
                "User": str(body.get("User", mqtt.get("User", ""))).strip(),
                "Pass": str(body.get("Pass", mqtt.get("Pass", ""))),
            }
        )
        write_config(config)
        json_response(response, {"status": "success", "MQTT": mqtt_config_payload(config)})
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/mqtt-test", "POST")
def route_mqtt_test(client, response):
    try:
        body = client.ReadRequestContentAsJSON() or {}
        mqtt_cfg = merge_mqtt_request(body)
        payload_obj = mqtt_test_payload()
        result = mqtt_publish_with_payload(mqtt_cfg, payload_obj)
        if result.get("ok"):
            json_response(
                response,
                {
                    "status": "success",
                    "message": "Mensaje de prueba enviado",
                    "topic": result.get("topic", ""),
                    "payload": payload_obj,
                },
            )
            return
        json_response(
            response,
            {"status": "error", "message": result.get("message", "No se pudo publicar el mensaje MQTT")},
            502,
        )
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/setnetmode", "POST")
def route_set_net_mode(client, response):
    try:
        body = client.ReadRequestContentAsJSON() or {}
        mode = int(body.get("mode", 12))
        config = read_config()
        config["NETMODE"] = {"Mode": mode}
        write_config(config)
        _thread.start_new_thread(net_mode_worker, (mode,))
        json_response(response, {"status": "success", "mode": mode, "pending": True})
    except Exception as e:
        json_response(response, {"status": "error", "message": repr(e)}, 500)


@auth_route("/command/fota-status", "GET")
def route_fota_status(client, response):
    json_response(response, fota_state)


@auth_route("/command/start-fota", "POST")
def route_start_fota(client, response):
    fota_state["status"] = "unsupported"
    fota_state["message"] = "FOTA aun no esta implementado para EG800K"
    fota_state["progress"] = 0
    ok_response(response, "<h2>FOTA aun no esta implementado para EG800K.</h2>")


@auth_route("/start-fota", "POST")
def route_start_fota_legacy(client, response):
    route_start_fota(client, response)


def wait_for_network(seconds):
    logger.info("Waiting for cellular registration")
    runtime_state["registered"] = False
    for _ in range(seconds):
        try:
            state = net.getState()
            if state[1][0] in (1, 5):
                runtime_state["registered"] = True
                logger.info("Cellular registered state={}".format(state))
                return True
        except:
            pass
        utime.sleep(1)
    logger.error("Cellular registration timeout")
    return False


def apply_pdp_config(config):
    cfg = config.get("APN", {})
    net_cfg = config.get("NETWORK", {})
    cid = int(cfg.get("Cid", 1))
    apn = sanitize_apn_text(cfg.get("Apn", ""))
    user = sanitize_apn_text(cfg.get("User", ""))
    password = sanitize_apn_text(cfg.get("Pass", ""))
    auth = int(cfg.get("Auth", 0) or 0)
    if auth <= 0:
        user = ""
        password = ""
    pdp_type = pdp_type_to_int(cfg.get("PdpType", "IP"))

    try:
        current = dataCall.getPDPContext(cid)
        logger.info("Current PDP context {}: {}".format(cid, current))
    except Exception as e:
        logger.error("PDP context read error {}".format(e))
        current = None

    if net_cfg.get("ResetPdpOnBoot", True):
        try:
            dataCall.deactivate(cid)
            logger.info("PDP deactivated before redial cid {}".format(cid))
            utime.sleep(1)
        except Exception as e:
            logger.error("PDP deactivate before redial error {}".format(e))

    if apn:
        try:
            ret = dataCall.setPDPContext(cid, pdp_type, apn, user, password, auth)
            logger.info("PDP context configured cid {} apn {} ret {}".format(cid, apn, ret))
        except Exception as e:
            logger.error("PDP context set error {}".format(e))
    elif current:
        logger.info("PDP context kept from modem because APN config is empty")

    ensure_pdp_auto_reconnect(cid)
    try:
        ret = dataCall.activate(cid)
        logger.info("PDP activate cid {} ret {}".format(cid, ret))
    except Exception as e:
        logger.error("PDP activate error {}".format(e))
    return cid


def is_cellular_registered():
    try:
        state = net.getState()
        registered = state[1][0] in (1, 5)
        runtime_state["registered"] = registered
        return registered
    except:
        runtime_state["registered"] = False
        return False


def get_valid_pdp_ip(cid):
    if not is_cellular_registered():
        runtime_state["ip"] = ""
        return ""
    try:
        info = dataCall.getInfo(cid, 0)
        nic = info[2]
        if nic[0] != 1:
            runtime_state["ip"] = ""
            return ""
        ip = nic[2]
        if ip and ip != "0.0.0.0":
            runtime_state["ip"] = ip
            return ip
    except:
        pass
    runtime_state["ip"] = ""
    return ""


def ensure_pdp_auto_reconnect(cid):
    try:
        dataCall.setAutoActivate(cid, 1)
        dataCall.setAutoConnect(cid, 1)
    except Exception as e:
        logger.error("PDP auto reconnect config error {}".format(e))


def wait_for_ip(cid, seconds):
    logger.info("Waiting for PDP IP on cid {}".format(cid))
    for _ in range(seconds):
        ip = get_valid_pdp_ip(cid)
        if ip:
            logger.info("PDP IP ready {}".format(ip))
            return ip
        utime.sleep(1)
    logger.error("PDP IP not assigned")
    return ""


def usbnet_mode_value(mode):
    text = str(mode or "RNDIS").upper()
    if USBNET is None:
        return None
    if text == "ECM":
        return USBNET.Type_ECM
    return USBNET.Type_RNDIS


def ensure_local_usb_network(config):
    usb_cfg = config.get("LOCAL_USB", {})
    if not usb_cfg.get("Enabled", True):
        logger.info("Local USB network disabled")
        return False
    if USBNET is None:
        logger.error("Local USB network unavailable: misc.USBNET import failed")
        return False

    target = usbnet_mode_value(usb_cfg.get("Mode", "RNDIS"))
    try:
        current = USBNET.get_worktype()
    except Exception as e:
        logger.error("USBNET get_worktype error {}".format(e))
        current = -1
    logger.info("USBNET worktype current={} target={}".format(current, target))

    if target is not None and current != target:
        try:
            ret = USBNET.set_worktype(target)
            logger.info("USBNET set_worktype ret {}".format(ret))
            if ret == 0 and usb_cfg.get("RestartAfterModeChange", False):
                logger.info("RESTART_REASON=usb_mode_change; restarting module to apply")
                utime.sleep(1)
                Power.powerRestart()
                return False
        except Exception as e:
            logger.error("USBNET set_worktype error {}".format(e))

    if not usb_cfg.get("OpenAfterPdp", True):
        return True
    try:
        ret = USBNET.open()
        logger.info("USBNET open ret {}".format(ret))
    except Exception as e:
        logger.error("USBNET open error {}".format(e))
        return False

    try:
        logger.info("USBNET status {}".format(USBNET.get_status()))
    except Exception as e:
        logger.error("USBNET get_status error {}".format(e))
    return ret == 0


def make_gpio_output(gpio, pull, initial):
    try:
        from machine import Pin
        pin_id = getattr(Pin, "GPIO{}".format(int(gpio)))
        return Pin(pin_id, Pin.OUT, pull, initial)
    except Exception as e:
        logger.error("GPIO{} init error {}".format(gpio, e))
        return None


def led_write(pin, active_level, on):
    if not pin:
        return
    try:
        pin.write(active_level if on else 1 - active_level)
    except Exception as e:
        logger.error("LED write error {}".format(e))


def led_worker(config):
    led_cfg = config.get("LEDS", {})
    if not led_cfg.get("Enabled", True):
        logger.info("LED worker disabled")
        return
    try:
        from machine import Pin
        active = int(led_cfg.get("ActiveLevel", 1))
        net_led = make_gpio_output(led_cfg.get("NetStatusGpio", 29), Pin.PULL_DISABLE, 1 - active)
        status_led = make_gpio_output(led_cfg.get("StatusGpio", 36), Pin.PULL_PD, active)
        status_mode = led_cfg.get("StatusMode", "heartbeat")
        led_write(status_led, active, True)
        logger.info(
            "LED worker enabled NET_STATUS=GPIO{} STATUS=GPIO{}".format(
                led_cfg.get("NetStatusGpio", 29), led_cfg.get("StatusGpio", 36)
            )
        )
        tick = 0
        while True:
            if status_mode == "solid":
                led_write(status_led, active, True)
            else:
                led_write(status_led, active, tick % 20 < 10)
            has_ip = bool(runtime_state.get("ip"))
            registered = bool(runtime_state.get("registered"))
            sim_ready = bool(sim_state.get("ready"))
            if has_ip:
                led_write(net_led, active, tick % 20 < 2)
            elif registered:
                led_write(net_led, active, tick % 10 < 2)
            elif sim_ready:
                led_write(net_led, active, tick % 4 < 2)
            else:
                led_write(net_led, active, False)
            tick = (tick + 1) % 120
            utime.sleep_ms(100)
    except Exception as e:
        logger.error("LED worker error {}".format(e))


def apply_net_mode(mode):
    try:
        ret = net.setConfig(int(mode))
        logger.info("Network mode applied: {} ret {}".format(mode, ret))
        return ret
    except Exception as e:
        logger.error("Network mode apply error {}".format(e))
        return repr(e)


def net_mode_worker(mode):
    apply_net_mode(mode)


def apply_saved_net_mode(config):
    mode = int(config.get("NETMODE", {}).get("Mode", 12))
    apply_net_mode(mode)


def start_tcp_bridges(config):
    ports = {}
    for key in ("RS485",):
        conf = config.get(key)
        if not conf:
            continue
        port = int(conf.get("Puerto", 0))
        if port <= 0 or port in ports:
            continue
        ports[port] = key
        _thread.start_new_thread(tcp_server, ("0.0.0.0", port, conf))


def restart_interval_seconds(restart_cfg):
    interval_seconds = int(restart_cfg.get("IntervalSeconds", 0) or 0)
    if interval_seconds > 0:
        return interval_seconds
    hours = float(restart_cfg.get("IntervalHours", 0) or 0)
    if hours <= 0:
        return 0
    return int(hours * 3600)


def scheduled_restart_worker(config):
    restart_cfg = config.get("RESTART", {})
    if not restart_cfg.get("Enabled", False):
        logger.info("Scheduled restart disabled")
        return
    interval_seconds = restart_interval_seconds(restart_cfg)
    min_uptime = int(restart_cfg.get("MinUptimeSec", 600) or 0)
    if interval_seconds <= 0:
        logger.info("Scheduled restart has no valid interval")
        return

    logger.info(
        "Scheduled restart enabled interval={}s min_uptime={}s".format(
            interval_seconds, min_uptime
        )
    )
    while True:
        uptime_seconds = int(utime.ticks_diff(utime.ticks_ms(), boot_ms) / 1000)
        if uptime_seconds >= min_uptime and uptime_seconds >= interval_seconds:
            logger.info(
                "RESTART_REASON=scheduled interval={}s uptime={}s".format(
                    interval_seconds, uptime_seconds
                )
            )
            utime.sleep(1)
            Power.powerRestart()
        utime.sleep(10)


def network_monitor_worker(config):
    if not sim_state.get("ready"):
        logger.error("Network monitor not started because SIM is not ready")
        return
    net_cfg = config.get("NETWORK", {})
    cid = int(config.get("APN", {}).get("Cid", 1))
    interval = int(net_cfg.get("MonitorIntervalSec", 15) or 15)
    stack_restart_sec = int(net_cfg.get("StackRestartAfterNoNetworkSec", 300) or 0)
    power_restart_sec = int(net_cfg.get("PowerRestartAfterNoNetworkSec", 900) or 0)
    recovery_enabled = stack_restart_sec > 0 or power_restart_sec > 0
    lost_since = None
    stack_restarted = False
    if recovery_enabled:
        logger.info(
            "Network monitor enabled interval={}s stack_restart={}s power_restart={}s".format(
                interval, stack_restart_sec, power_restart_sec
            )
        )
    else:
        logger.info("Network monitor enabled interval={}s without auto-restart".format(interval))
    while True:
        registered = is_cellular_registered()
        ip = get_valid_pdp_ip(cid) if registered else ""
        if registered and ip:
            lost_since = None
            stack_restarted = False
        else:
            now = utime.ticks_ms()
            if lost_since is None:
                lost_since = now
                logger.error("Network monitor detected no LTE/IP registered={} ip={}".format(registered, ip))
            if recovery_enabled:
                lost_sec = int(utime.ticks_diff(now, lost_since) / 1000)
                if stack_restart_sec and lost_sec >= stack_restart_sec and not stack_restarted:
                    logger.error(
                        "RESTART_REASON=network_stack lost_sec={}s".format(lost_sec)
                    )
                    try:
                        net.setModemFun(0, 0)
                        utime.sleep(3)
                        net.setModemFun(1, 0)
                        apply_saved_net_mode(config)
                        wait_for_network(int(net_cfg.get("RegistrationTimeoutSec", 120) or 120))
                        apply_pdp_config(config)
                        wait_for_ip(cid, int(net_cfg.get("PdpTimeoutSec", 60) or 60))
                    except Exception as e:
                        logger.error("Network monitor stack restart error {}".format(e))
                    stack_restarted = True
                if power_restart_sec and lost_sec >= power_restart_sec:
                    logger.error(
                        "RESTART_REASON=network_power lost_sec={}s".format(lost_sec)
                    )
                    utime.sleep(1)
                    Power.powerRestart()
        utime.sleep(interval)


def mqtt_encode_string(value):
    if value is None:
        value = ""
    if not isinstance(value, bytes):
        value = str(value).encode()
    return bytes([len(value) >> 8, len(value) & 0xFF]) + value


def mqtt_remaining_length(length):
    out = b""
    while True:
        digit = length % 128
        length = int(length / 128)
        if length > 0:
            digit |= 0x80
        out += bytes([digit])
        if length == 0:
            return out


def mqtt_packet(packet_type, variable_payload):
    return bytes([packet_type]) + mqtt_remaining_length(len(variable_payload)) + variable_payload


def mqtt_connect(sock, client_id, keepalive, user="", password=""):
    flags = 0x02
    payload = mqtt_encode_string(client_id)
    if user:
        flags |= 0x80
        payload += mqtt_encode_string(user)
        if password:
            flags |= 0x40
            payload += mqtt_encode_string(password)
    variable = mqtt_encode_string("MQTT") + bytes([4, flags, keepalive >> 8, keepalive & 0xFF])
    sock.send(mqtt_packet(0x10, variable + payload))
    resp = sock.recv(4)
    if len(resp) >= 4 and resp[0] == 0x20 and resp[3] == 0:
        return True
    logger.error("MQTT connect refused response={}".format(resp))
    return False


def mqtt_publish(sock, topic, payload):
    if not isinstance(payload, bytes):
        payload = str(payload).encode()
    sock.send(mqtt_packet(0x30, mqtt_encode_string(topic) + payload))


def mqtt_disconnect(sock):
    try:
        sock.send(b"\xE0\x00")
    except:
        pass


def mqtt_publish_with_payload(mqtt_cfg, payload_obj):
    if not str(mqtt_cfg.get("Host", "")).strip():
        return {"ok": False, "message": "Broker MQTT no configurado"}
    if not is_cellular_registered():
        return {"ok": False, "message": "Modem sin registro en red celular"}
    cid = int(read_config().get("APN", {}).get("Cid", 1))
    pdp_ip = get_valid_pdp_ip(cid)
    if not pdp_ip:
        return {"ok": False, "message": "IP de datos no disponible"}

    imei = safe_call(modem.getDevImei, "") or "unknown"
    host = mqtt_cfg.get("Host", "185.187.170.193")
    port = int(mqtt_cfg.get("Port", 1883))
    keepalive = int(mqtt_cfg.get("KeepAliveSec", 60))
    topic_prefix = mqtt_cfg.get("TopicPrefix", "MetaSense/ModemEGmini")
    topic = "{}/{}".format(topic_prefix, imei)
    client_id = "{}_{}".format(mqtt_cfg.get("ClientPrefix", "EG800K"), imei)
    payload = ujson.dumps(payload_obj)

    with mqtt_lock:
        last_error = "Error MQTT desconocido"
        for attempt in range(2):
            sock = None
            try:
                pdp_ip = get_valid_pdp_ip(cid)
                if not pdp_ip:
                    return {"ok": False, "message": "IP de datos no disponible"}
                addr = resolve_host_addr(host, port)
                sock = socket_tcp_client(pdp_ip)
                sock.settimeout(20)
                logger.info(
                    "MQTT connect attempt={} local={} broker={}:{}".format(
                        attempt + 1, pdp_ip, host, port
                    )
                )
                sock.connect(addr)
                if not mqtt_connect(
                    sock, client_id, keepalive, mqtt_cfg.get("User", ""), mqtt_cfg.get("Pass", "")
                ):
                    return {"ok": False, "message": "Conexion MQTT rechazada por el broker"}
                mqtt_publish(sock, topic, payload)
                mqtt_disconnect(sock)
                logger.info("MQTT published topic={} bytes={}".format(topic, len(payload)))
                return {"ok": True, "topic": topic, "bytes": len(payload), "payload": payload_obj}
            except Exception as e:
                last_error = "Error MQTT: {}".format(e)
                logger.error("MQTT publish error attempt={} {}".format(attempt + 1, e))
                errno = e.args[0] if getattr(e, "args", None) else 0
                if attempt == 0 and mqtt_connect_retriable_errno(errno):
                    utime.sleep(1)
                    continue
                return {"ok": False, "message": last_error}
            finally:
                try:
                    if sock:
                        sock.close()
                except:
                    pass
        return {"ok": False, "message": last_error}


def mqtt_publish_once(mqtt_cfg):
    return mqtt_publish_with_payload(mqtt_cfg, telemetry_payload()).get("ok", False)


def mqtt_worker(config):
    utime.sleep(10)
    while True:
        mqtt_cfg = read_config().get("MQTT", {})
        if not mqtt_cfg.get("Enabled", False):
            utime.sleep(30)
            continue
        interval = int(mqtt_cfg.get("IntervalSec", 300) or 300)
        if interval < 30:
            interval = 30
        mqtt_publish_once(mqtt_cfg)
        gc.collect()
        utime.sleep(interval)


def main():
    try:
        config = read_config()
    except Exception as e:
        logger.error("config read error {}".format(e))
        return

    sim_ok = eg800k_modem_startup(config)
    if sim_ok:
        apply_saved_net_mode(config)
        net_cfg = config.get("NETWORK", {})
        registered = wait_for_network(int(net_cfg.get("RegistrationTimeoutSec", 120) or 120))
        cid = int(config.get("APN", {}).get("Cid", 1))
        if registered:
            cid = apply_pdp_config(config)
            wait_for_ip(cid, int(net_cfg.get("PdpTimeoutSec", 60) or 60))
            ensure_local_usb_network(config)
        else:
            logger.error("Network not registered at boot; stale PDP IP ignored")
        start_tcp_bridges(config)
    else:
        logger.error("SIM_ERROR: network, PDP and TCP bridges not started")

    srv = WebSrv(
        ip="0.0.0.0",
        port=WEB_PORT,
        templatePath="/usr/www/",
        staticPath="/usr/www/",
        staticPrefix="/__protected_static__/",
    )
    _thread.start_new_thread(srv.Start, ())
    _thread.start_new_thread(scheduled_restart_worker, (config,))
    _thread.start_new_thread(led_worker, (config,))
    _thread.start_new_thread(network_monitor_worker, (config,))
    _thread.start_new_thread(mqtt_worker, (config,))

    logger.info("System ready")
    while True:
        gc.collect()
        utime.sleep(10)


if __name__ == "__main__":
    main()

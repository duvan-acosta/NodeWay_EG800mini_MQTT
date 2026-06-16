import base64
import os
import sys
import time

import serial


BAUD = 115200
PORTS = ["COM7", "COM5"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_USR = os.path.join(ROOT, "usr")
REMOTE_USR = "/usr"


def read_all(ser, delay=0.2):
    time.sleep(delay)
    return ser.read_all()


def find_repl():
    for port in PORTS:
        try:
            ser = serial.Serial(port, BAUD, timeout=1)
            ser.reset_input_buffer()
            ser.write(b"\r\x03\x03")
            out = read_all(ser, 1.0)
            ser.write(b"\x02\r\n")
            out += read_all(ser, 0.5)
            if b">>>" in out or b"KeyboardInterrupt" in out or b"QuecPython" in out:
                print("REPL found on {}".format(port))
                return ser
            ser.close()
            print("{} opened but no REPL response: {!r}".format(port, out[:120]))
        except Exception as exc:
            print("{} not available: {}".format(port, exc))
    return None


def raw_exec(ser, code, wait=0.6, deadline=8):
    ser.write(b"\x01")
    read_all(ser, 0.2)
    ser.write(code.encode("utf-8") + b"\x04")
    end = time.time() + deadline
    out = b""
    while time.time() < end:
        out += ser.read_all()
        if b"\x04>" in out or b"Traceback" in out:
            break
        time.sleep(wait)
    ser.write(b"\x02")
    read_all(ser, 0.2)
    return out


def ensure_dir(ser, path):
    code = (
        "import uos\n"
        "try:\n"
        "    uos.mkdir('{}')\n"
        "except Exception as e:\n"
        "    pass\n"
        "print('DIR_OK')\n"
    ).format(path)
    out = raw_exec(ser, code)
    if b"DIR_OK" not in out:
        raise RuntimeError("mkdir failed for {}: {!r}".format(path, out[:200]))


def upload_file(ser, local_path, remote_path):
    with open(local_path, "rb") as fh:
        data = fh.read()

    b64 = base64.b64encode(data).decode("ascii")
    chunks = [b64[i:i + 360] for i in range(0, len(b64), 360)]
    print("Uploading {} -> {} ({} bytes, {} chunks)".format(local_path, remote_path, len(data), len(chunks)))

    out = raw_exec(
        ser,
        "import ubinascii\nf=open('{}','wb')\nprint('OPEN_OK')".format(remote_path),
        deadline=8,
    )
    if b"OPEN_OK" not in out:
        raise RuntimeError("open failed for {}: {!r}".format(remote_path, out[:300]))

    for idx, chunk in enumerate(chunks, 1):
        out = raw_exec(ser, "f.write(ubinascii.a2b_base64(b'{}'))".format(chunk), wait=0.05, deadline=8)
        if b"Traceback" in out:
            raise RuntimeError("write failed for {} chunk {}: {!r}".format(remote_path, idx, out[:300]))
        if idx == len(chunks) or idx % 25 == 0:
            print("  {}/{}".format(idx, len(chunks)))

    out = raw_exec(ser, "f.close()\nprint('CLOSE_OK')", deadline=8)
    if b"CLOSE_OK" not in out:
        raise RuntimeError("close failed for {}: {!r}".format(remote_path, out[:300]))

    out = raw_exec(ser, "import uos\nprint(uos.stat('{}')[6])".format(remote_path), deadline=8)
    text = out.decode(errors="ignore")
    if str(len(data)) not in text:
        raise RuntimeError("verify failed for {} expected {} got {!r}".format(remote_path, len(data), text[:300]))


def iter_files():
    for base, _, files in os.walk(LOCAL_USR):
        rel_dir = os.path.relpath(base, LOCAL_USR)
        remote_dir = REMOTE_USR if rel_dir == "." else REMOTE_USR + "/" + rel_dir.replace("\\", "/")
        yield ("dir", None, remote_dir)
        for name in files:
            local = os.path.join(base, name)
            remote = remote_dir + "/" + name
            yield ("file", local, remote)


def main():
    if not os.path.isdir(LOCAL_USR):
        print("Local usr not found: {}".format(LOCAL_USR))
        return 1
    ser = find_repl()
    if not ser:
        print("No REPL port found")
        return 2
    try:
        for kind, local, remote in iter_files():
            if kind == "dir":
                ensure_dir(ser, remote)
            else:
                upload_file(ser, local, remote)
        out = raw_exec(
            ser,
            "import uos\nprint('USR_LIST', uos.listdir('/usr'))\nprint('WWW_LIST', uos.listdir('/usr/www'))",
            deadline=10,
        )
        print(out.decode(errors="replace"))
        raw_exec(ser, "from misc import Power\nPower.powerRestart()", deadline=3)
        print("Upload complete. Module restart requested.")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    sys.exit(main())

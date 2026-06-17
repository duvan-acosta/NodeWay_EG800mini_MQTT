import sys
import time

import serial

PORTS = [("COM7", (921600, 115200))]

EXPECTED = {
    "/usr/www/index.html": 15031,
    "/usr/www/index.js": 22828,
    "/usr/www/index.css": 9396,
    "/usr/www/login.html": 1098,
    "/usr/www/login.js": 1618,
    "/usr/www/login.css": 1732,
    "/usr/app_main.py": 56340,
    "/usr/config.json": 1524,
}


def read_all(ser, delay=0.3):
    time.sleep(delay)
    return ser.read_all()


def raw_exec(ser, code, deadline=12):
    ser.reset_input_buffer()
    ser.write(b"\x01")
    read_all(ser, 0.15)
    ser.write(code.encode("utf-8") + b"\x04")
    end = time.time() + deadline
    out = b""
    while time.time() < end:
        out += ser.read_all()
        if b"\x04>" in out:
            break
        time.sleep(0.25)
    ser.write(b"\x02")
    read_all(ser, 0.15)
    return out


def find_repl():
    for port, bauds in PORTS:
        for baud in bauds:
            try:
                ser = serial.Serial(port, baud, timeout=1)
                ser.reset_input_buffer()
                for _ in range(6):
                    ser.write(b"\r\x03")
                    read_all(ser, 0.4)
                ser.write(b"\x02\r\n")
                out = read_all(ser, 2.0)
                if b">>>" in out or b"KeyboardInterrupt" in out:
                    print("REPL on {} @ {}".format(port, baud))
                    return ser
                ser.close()
            except Exception as exc:
                print("{} @ {}: {}".format(port, baud, exc))
    return None


def main():
    ser = find_repl()
    if not ser:
        return 2
    lines = ["import uos"]
    for path in EXPECTED:
        lines.append("print('{}', uos.stat('{}')[6])".format(path, path))
    out = raw_exec(ser, "\n".join(lines), 20)
    text = out.decode("utf-8", errors="replace")
    print(text)
    ok = True
    for path, size in EXPECTED.items():
        if str(size) in text:
            print("OK", path, size)
        else:
            print("CHECK", path, "expected", size)
            ok = False
    ser.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

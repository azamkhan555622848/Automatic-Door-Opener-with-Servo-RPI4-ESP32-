#!/usr/bin/env python3
"""Person detector + TCP line server for the door-lock bench demo.

Pi side of the link. Watches the USB webcam with the OpenCV HOG
people detector and streams state changes to the ESP32:

    ESP32 -> Pi : HELLO <id>
    Pi -> ESP32 : PERSON 1 | PERSON 0 | PING

A person is asserted after two consecutive positive frames and cleared
after --hold seconds without a detection. The Pi owns the hold timer;
the ESP32 has its own 10 s link watchdog as the fail-safe.
"""

import argparse
import logging
import signal
import socket
import threading
import time

import cv2

import faceid

LOG = logging.getLogger("detector")

FORCE = {"state": None}


def _on_force(signum, _frame):
    FORCE["state"] = signum == signal.SIGUSR1
    LOG.info("force person=%s", FORCE["state"])


class Link:
    """Single-client TCP link. Safe to call send() from the detector thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sock = None
        self._addr = None

    def attach(self, sock, addr):
        with self._lock:
            old = self._sock
            self._sock = sock
            self._addr = addr
        if old is not None:
            try:
                old.close()
            except OSError:
                pass
        LOG.info("client connected: %s", addr)

    def detach(self, sock):
        with self._lock:
            if self._sock is sock:
                self._sock = None
                self._addr = None
        LOG.info("client disconnected")

    @property
    def connected(self):
        with self._lock:
            return self._sock is not None

    def send(self, line):
        with self._lock:
            if self._sock is None:
                return False
            try:
                self._sock.sendall((line + "\n").encode("ascii"))
                return True
            except OSError as exc:
                LOG.warning("send failed: %s", exc)
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
                self._addr = None
                return False


class SerialLink:
    """USB serial link to the ESP32 (Pi ttyUSB0 <-> CP2102)."""

    RETRY_S = 3.0

    def __init__(self, port, baud=115200):
        self._lock = threading.Lock()
        self._port = port
        self._baud = baud
        self._ser = None
        self._next_try = 0.0
        self._open()

    def _open(self):
        import serial

        now = time.monotonic()
        if now < self._next_try:
            return
        self._next_try = now + self.RETRY_S
        try:
            ser = serial.Serial()
            ser.port = self._port
            ser.baudrate = self._baud
            ser.timeout = 0.2
            ser.dtr = False
            ser.rts = False
            ser.open()
        except Exception as exc:  # serial.SerialException, OSError
            LOG.warning("serial open failed: %s", exc)
            return
        self._ser = ser
        LOG.info("serial open: %s @ %d", self._port, self._baud)

    @property
    def connected(self):
        with self._lock:
            return self._ser is not None

    def send(self, line):
        with self._lock:
            if self._ser is None:
                self._open()
                if self._ser is None:
                    return False
            try:
                self._ser.write((line + "\n").encode("ascii"))
                self._ser.flush()
                return True
            except Exception as exc:
                LOG.warning("serial write failed: %s", exc)
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                return False

    def readline(self):
        with self._lock:
            ser = self._ser
            if ser is None:
                self._open()
                return None
            try:
                return ser.readline()
            except Exception as exc:
                LOG.warning("serial read failed: %s", exc)
                try:
                    ser.close()
                except Exception:
                    pass
                self._ser = None
                return None


def serial_reader(link, stop):
    while not stop.is_set():
        line = link.readline()
        if not line:
            continue
        LOG.info("serial rx: %s", line.decode("ascii", "replace").strip())


def serve(link, port, stop):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(4)
    srv.settimeout(1.0)
    LOG.info("listening on 0.0.0.0:%d", port)

    while not stop.is_set():
        try:
            conn, addr = srv.accept()
        except socket.timeout:
            continue
        except OSError as exc:
            LOG.warning("accept failed: %s", exc)
            continue

        conn.settimeout(0.5)
        link.attach(conn, addr)
        threading.Thread(target=read_client, args=(link, conn), daemon=True).start()

    srv.close()


def read_client(link, conn):
    buf = b""
    try:
        while True:
            try:
                data = conn.recv(256)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                LOG.info("rx: %s", line.decode("ascii", "replace").strip())
    finally:
        link.detach(conn)
        try:
            conn.close()
        except OSError:
            pass


def heartbeat(link, period, stop):
    while not stop.is_set():
        link.send("PING")
        stop.wait(period)


def open_camera(index, width, height):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        cap.release()
        return None
    return cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--serial", default=None,
                    help="serial device to the ESP32, e.g. /dev/ttyUSB0 "
                         "(disables the TCP server)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--hold", type=float, default=5.0,
                    help="seconds without a detection before clearing")
    ap.add_argument("--detect-every", type=int, default=3)
    ap.add_argument("--models", default="/home/asus/pi/models")
    ap.add_argument("--faces", default="/home/asus/pi/faces")
    ap.add_argument("--match-threshold", type=float, default=0.363,
                    help="SFace cosine similarity needed to unlock")
    ap.add_argument("--cooldown", type=float, default=10.0,
                    help="seconds before the same door can unlock again")
    ap.add_argument("--ping", type=float, default=2.0)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    fid = faceid.FaceID(args.models, args.faces, threshold=args.match_threshold)

    signal.signal(signal.SIGUSR1, _on_force)
    signal.signal(signal.SIGUSR2, _on_force)

    link = Link()
    stop = threading.Event()
    if args.serial:
        link = SerialLink(args.serial)
        threading.Thread(target=serial_reader, args=(link, stop), daemon=True).start()
    else:
        threading.Thread(target=serve, args=(link, args.port, stop), daemon=True).start()
    threading.Thread(target=heartbeat, args=(link, args.ping, stop),
                     daemon=True).start()

    positive_streak = 0
    last_seen = 0.0
    last_unlock = 0.0
    last_unknown_log = 0.0
    last_name = ""
    last_score = 0.0
    frame_no = 0
    forced_prev = None

    while not stop.is_set():
        cap = open_camera(args.camera, args.width, args.height)
        if cap is None:
            LOG.error("camera %d not available, retrying in 5 s", args.camera)
            time.sleep(5)
            continue

        LOG.info("camera %d open at %dx%d", args.camera, args.width, args.height)
        try:
            while not stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    LOG.warning("frame read failed, reopening camera")
                    break

                frame_no += 1
                now = time.monotonic()

                if frame_no % max(args.detect_every, 1) == 0:
                    name, score = fid.recognize(frame)
                    if name is not None:
                        positive_streak += 1
                        last_seen = now
                        last_name, last_score = name, score
                    else:
                        positive_streak = 0
                        if score > 0 and now - last_unknown_log > 3.0:
                            last_unknown_log = now
                            LOG.info("unknown face, best %.3f < %.3f",
                                     score, args.match_threshold)

                if FORCE["state"] is not None:
                    if FORCE["state"] != forced_prev:
                        forced_prev = FORCE["state"]
                        LOG.info("forced %s", "person" if forced_prev else "clear")
                        link.send("PERSON 1" if forced_prev else "PERSON 0")
                elif positive_streak >= 2 and (now - last_unlock) > args.cooldown:
                    last_unlock = now
                    positive_streak = 0
                    LOG.info("allowed %s (score %.3f) -> unlock", last_name, last_score)
                    link.send("PERSON 1")
                elif last_seen and (now - last_seen) > args.hold:
                    LOG.info("face left")
                    last_seen = 0.0

        finally:
            cap.release()
            time.sleep(1)

    stop.set()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
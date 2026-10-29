# Automatic Door Opener — Raspberry Pi 4 + ESP32

A face-recognition door lock that turns an existing thumb-turn from the inside.
A Raspberry Pi 4 watches a webcam, recognises an enrolled face, and tells an
ESP32 to nudge a servo horn one full turn (and back) so it can operate the lock
and always return to its true zero position.

Bench prototype status: working end-to-end (recognise → turn → return), but
still on continuous-rotation servos and a shared 5 V rail. See
[Known limitations](#known-limitations).

```
                USB / 115200 8N1
  ┌──────────┐   PERSON 1      ┌───────────┐   50 Hz PWM    ┌──────────────┐
  │  Pi 4    │ ──────────────► │  ESP32    │ ─────────────► │ MG996R servo │
  │ webcam   │ ◄────────────── │ lock-node │  GPIO 18       │ thumb-turn   │
  │ YuNet +  │  PONG / STATUS  └───────────┘                └──────────────┘
  │ SFace    │
  └──────────┘
```

The Pi does all the machine vision; the ESP32 owns the timing-critical servo
pulse and the fail-safe behaviour. They speak one newline-terminated command
per line, so either side can be swapped out (the Wi-Fi/TCP transport is still
in the firmware under `LINK_SERIAL 0`).

---

## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi 4 (2 GB+) | Debian arm64; runs `detector.py` as a systemd service |
| Logitech C270 (or any UVC webcam) | 640×480 MJPEG is enough; 1280×720 also works |
| ESP32 DevKit (ESP32-D0WD, 4 MB) | Arduino framework via PlatformIO; CP2102 USB-UART |
| MG996R ×2 | **Continuous rotation** — 1500 µs = stop, no position feedback |
| PCA9685 | Unused in the current serial build; kept for the 12 V servo plan |
| 5 V supply for the servo | ≥2 A, **must not** come from the Pi or the ESP32 5 V pin |

### Wiring (bench build)

| ESP32 | Goes to |
|---|---|
| GPIO 18 | servo signal (orange) |
| GND | servo GND (brown) — common with the servo supply |
| USB | Pi USB port (`/dev/ttyUSB0`) |

Servo power: red wire to a **separate** 5–6 V supply, ground tied to the ESP32
ground. Powering the servo from the Pi's USB port browns out both the Pi and the
ESP32 mid-move — that is the source of the `frame read failed` messages and the
occasional ESP32 reset.

> Production plan is RS-485 over a ~4 m cable (12 V, GND, A, B) instead of USB,
> with the servo on its own supply inside the lock box.

---

## Repository layout

```
firmware/lock-node/     ESP32 firmware: serial/TCP link + turn-and-return state machine
firmware/servo-id/      sketch used to confirm the MG996R is continuous rotation
firmware/servo-test/    sweep/step test sketch
firmware/wifi-scan/     RSSI / Wi-Fi diagnostics
pi/detector.py          camera loop, face recognition, link to the ESP32
pi/faceid.py            YuNet detector + SFace embedder wrapper, gallery load/build
pi/enroll.py            capture enrolment shots, rebuild gallery.npz
pi/lockserver.service   systemd unit
hardware/door-lock/     KiCad schematic (ERC clean, pre-dates the serial link)
enclosure/              FreeCAD parametric boxes + STEP exports
shopping-list.md        BOM with verification status
```

---

## Firmware

```powershell
python -m platformio run -d firmware/lock-node
```

Build output: `firmware/lock-node/.pio/build/lock-node/firmware.bin`
(RAM ≈ 4 %, flash ≈ 16 %).

`firmware/lock-node/include/secrets.h` holds the Wi-Fi credentials and is
git-ignored. Copy the template before building:

```powershell
Copy-Item firmware/lock-node/include/secrets.example.h firmware/lock-node/include/secrets.h
```

The file is only needed when `LINK_SERIAL` is 0.

### Flashing

From a PC with PlatformIO:

```powershell
python -m platformio run -d firmware/lock-node -t upload
```

From the Pi over the same USB cable the link uses (the stub flasher is missing
from the Debian `esptool` package, hence `--no-stub`):

```bash
esptool --port /dev/ttyUSB0 --chip esp32 --baud 115200 --no-stub \
        write_flash -z 0x10000 firmware.bin
```

A full image needs `bootloader_dio_40m.bin` @ `0x1000`, `partitions.bin` @
`0x8000` and `boot_app0.bin` @ `0xe000` as well. `asus` must be in the
`dialout` group.

---

## Serial protocol

115200 8N1, one command per line, `\n` terminated. The ESP32 answers on the
same link; the Pi logs every reply.

### Pi → ESP32

| Command | Meaning |
|---|---|
| `PERSON 1` | Enrolled face present → run one turn-out-and-return cycle |
| `PERSON 0` | Person gone — logged only, no motion (the arm is already home) |
| `PING` | Liveness / status request |
| `MOVE <ms>` | Duration of one 290° nudge, `50…5000` |
| `SPEED <us>` | Offset from the 1500 µs stop point, `50…500` |
| `PAUSE <ms>` | Dwell at the far end before returning, `0…20000` |
| `HOME [ms]` | Creep into the lock-side end stop (`100…10000`, default 3000) |
| `ZERO` | Stop immediately and treat the current position as zero |

### ESP32 → Pi

| Line | Meaning |
|---|---|
| `HELLO lock1` | Printed once at boot after the servo is stopped |
| `PONG <uptime_ms>` | Answer to `PING`, followed by a `STATUS` line |
| `STATUS phase=<n> move_ms=<ms> speed_us=<us>` | Current state-machine phase and tuning |
| `turn unlock: <ms> ms out, then back` | Cycle started |
| `out` / `returning` / `at zero` | Phase transitions |
| `person cleared`, `busy, queued`, `homed`, `zero: stopped` | Ack / diagnostics |

`phase`: 0 idle, 1 out, 2 pause, 3 back, 4 homing.

### Fail-safe behaviour

- **Inactivity:** no command for `LINK_TIMEOUT_MS` (30 s) → servo stopped, phase
  forced to idle. In Wi-Fi mode it additionally drives back to zero.
- **Queueing:** a trigger arriving mid-cycle is stored in `pendingDir` and run
  after the current cycle finishes, so the arm is never left turned out.
- **Serial mode is not fatal:** the timeout never commands motion.

---

## Raspberry Pi setup

```bash
sudo apt install python3-opencv python3-serial
mkdir -p ~/pi/models ~/pi/faces
# YuNet + SFace ONNX models (opencv_zoo)
# yunet.onnx  232589 B   sha256 8f2383e4…  -> ~/pi/models/yunet.onnx
# sface.onnx         38696353 B  sha256 0ba9fbfa…  -> ~/pi/models/sface.onnx
cp detector.py faceid.py enroll.py lockserver.service ~/pi/
sudo cp ~/pi/lockserver.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now lockserver
```

Service command (as deployed):

```
/usr/bin/python3 /home/asus/pi/detector.py --camera 0 --port 5000 --hold 5 --serial /dev/ttyUSB0
```

### `detector.py` options

| Flag | Default | Meaning |
|---|---|---|
| `--camera` | `0` | V4L2 device index |
| `--serial` | off | Serial device for the link; **enables serial mode and disables the TCP server** |
| `--port` | `5000` | TCP port when `--serial` is absent |
| `--width` / `--height` | `640×480` | Capture size |
| `--hold` | `5.0` | Seconds a person must stay before triggering |
| `--detect-every` | `3` | Run recognition on every Nth frame |
| `--models` | `/home/asus/pi/models` | YuNet + SFace directory |
| `--faces` | `/home/asus/pi/faces` | Enrolment gallery |
| `--match-threshold` | `0.363` | SFace cosine distance to accept |
| `--cooldown` | `10.0` | Seconds of silence after one unlock |
| `--ping` | `2.0` | Heartbeat interval |

A face must match on **2 consecutive** recognition frames before `PERSON 1` is
sent, which kills single-frame flicker. Unknown faces are logged only.

Deeper diagnostics can be forced at any time:

```bash
PID=$(systemctl show -p MainPID --value lockserver)
sudo kill -USR1 $PID   # pretend an enrolled person is present
sudo kill -USR2 $PID   # clear
```

---

## Face recognition

OpenCV only — no dlib or `face_recognition` build needed.

- **Detect:** `FaceDetectorYN` (YuNet), 320×320, score ≥ 0.7, NMS 0.3.
- **Embed:** `FaceRecognizerSF` (SFace), 128-d, aligned crop.
- **Match:** cosine distance against `faces/gallery.npz`; accept at ≤ 0.363.
- **Speed:** ~40 ms per frame on the Pi 4 CPU, hence every 3rd frame.

Measured separation on the bench: enrolled face self-match **1.00**, live
walk-up match **0.758**, unrelated face (`lena.jpg`) **0.164**. The threshold
sits in a wide gap between them.

### Enrolling a person

```bash
sudo python3 /home/asus/pi/enroll.py --name azam     # 5 shots with countdown
sudo python3 /home/asus/pi/enroll.py --rebuild       # after dropping photos in
```

Photos live in `/home/asus/pi/faces/<name>/*.jpg`. The enroller stops and
restarts `lockserver` so the camera is free. `faces/` is git-ignored — it
contains photos of real people and must not be committed.

---

## Servo calibration

The MG996R is continuous rotation, so "angle" is really "how long to drive".
Measured against a full 360° turn (3400 ms):

| `MOVE_MS` | 400 | 1700 | 1890 | 2080 | 2360 | 2456 | 2550 | 2644 | **2739** |
|---|---|---|---|---|---|---|---|---|---|
| degrees | 45 | 180 | 200 | 220 | 250 | 260 | 270 | 280 | **290** |

≈ 9.4 ms per degree above ~45° (the first few degrees are lost to the start
ramp). Current setting is **2739 ms ≈ 290°**, with `RETURN_PAUSE_MS` 3000 ms of
dwell at the far end.

Re-calibrate in place without reflashing:

```bash
python3 ~/pi/servo_cmd.py "MOVE 2739" --wait 0.3
python3 ~/pi/servo_cmd.py "PAUSE 3000"
python3 ~/pi/servo_cmd.py "PERSON 1" --wait 12
```

Note: settings live in RAM — an ESP32 reset restores the compiled defaults.
Opening the serial port can reset the board via DTR/RTS; the sender leaves both
deasserted.

---

## Known limitations

- **No holding torque.** A continuous-rotation servo cannot hold a position and
  has no feedback, so the true resting angle drifts. A 180° positional servo
  (plus a 5 A-capable 5 V supply) is the intended fix.
- **Servo and camera share the Pi's 5 V** on the bench, so the camera drops out
  during a move (`frame read failed, reopening camera`). Harmless while the move
  is short, but it must be fixed before the arm has to move far.
- **No liveness detection.** A printed photo of an enrolled person will pass.
  Deliberate choice for the prototype; the hook is there to add anti-spoofing.
- **No encryption on the link.** Fine over a USB cable inside the box; needs
  attention before the link becomes a 4 m cable that leaves the enclosure.
- Enclosure, coupler geometry and thumb-turn measurements (protrusion,
  direction, travel) are not finalised.

## Roadmap

1. Positional servo + dedicated 5 V supply; retire the timed-nudge calibration.
2. Measure the thumb-turn and finalise the coupler.
3. RS-485 transport over the 4 m run; update the KiCad schematic.
4. Weatherproof both boxes and the camera cradle (gaskets, drain holes).
5. Liveness check as a pluggable step before `PERSON 1` is sent.

## Safety

This controls a physical lock. It is a prototype: it fails **open** on the
mechanical side (the thumb-turn is still reachable by hand) and has no audit
trail. Do not put it on a door that matters until the power path, the servo,
and the liveness check are all sorted.

## License

Not yet chosen.

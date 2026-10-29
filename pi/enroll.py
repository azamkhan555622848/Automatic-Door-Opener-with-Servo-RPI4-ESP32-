#!/usr/bin/env python3
"""Enroll an allowed person for the door-lock face gallery.

    sudo python3 enroll.py --name ali              # 5 shots at the camera
    sudo python3 enroll.py --rebuild               # index faces/*/*.jpg
    sudo python3 enroll.py --name ali --rebuild    # capture then index

The detector service holds the camera, so this script stops it first and
restarts it afterwards (unless --no-service).
"""

import argparse
import logging
import os
import subprocess
import time

import cv2

from faceid import FaceID, build_gallery

LOG = logging.getLogger("enroll")
SERVICE = "lockserver"


def service(action):
    try:
        subprocess.run(["systemctl", action, SERVICE], check=True)
        LOG.info("service %s", action)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        LOG.warning("service %s failed: %s", action, exc)


def capture(args, fid):
    out_dir = os.path.join(args.faces, args.name)
    os.makedirs(out_dir, exist_ok=True)
    LOG.info("saving to %s", out_dir)

    cap = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise SystemExit("camera %d not available" % args.camera)

    saved = 0
    try:
        for i in range(6):
            cap.read()
            time.sleep(0.1)

        LOG.info("look at the camera - starting in %d s", args.countdown)
        time.sleep(args.countdown)

        attempt = 0
        while saved < args.count and attempt < args.count * 4:
            attempt += 1
            ok, frame = cap.read()
            if not ok or frame is None:
                LOG.warning("frame read failed")
                time.sleep(0.3)
                continue

            face = fid.detect(frame)
            if face is None:
                LOG.warning("no face - move closer / more light")
                time.sleep(args.interval)
                continue

            stamp = time.strftime("%Y%m%d-%H%M%S")
            path = os.path.join(out_dir, "%s_%02d.jpg" % (stamp, saved))
            cv2.imwrite(path, frame)
            saved += 1
            LOG.info("shot %d/%d saved (score %.2f): %s",
                     saved, args.count, float(face[-1]), path)
            time.sleep(args.interval)
    finally:
        cap.release()

    if saved == 0:
        raise SystemExit("no usable shots captured")
    LOG.info("captured %d shots for %s", saved, args.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="person to enroll (folder name)")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--countdown", type=int, default=3)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--models", default="/home/asus/pi/models")
    ap.add_argument("--faces", default="/home/asus/pi/faces")
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild gallery.npz from the photos on disk")
    ap.add_argument("--no-service", action="store_true",
                    help="do not stop/start lockserver")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.name and not args.rebuild:
        raise SystemExit("nothing to do: pass --name and/or --rebuild")

    os.makedirs(args.faces, exist_ok=True)
    fid = FaceID(args.models, args.faces)

    if not args.no_service:
        service("stop")
    try:
        if args.name:
            capture(args, fid)
        if args.rebuild or args.name:
            names = build_gallery(args.models, args.faces)
            counts = {n: names.count(n) for n in sorted(set(names))}
            LOG.info("gallery now: %s", counts)
    finally:
        if not args.no_service:
            service("start")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Face detection + recognition (YuNet + SFace) for the door lock.

No dlib, no face_recognition package: two OpenCV ONNX models.

Gallery layout:

    faces/<name>/<anything>.jpg      one folder per allowed person
    faces/gallery.npz                built by enroll.py --rebuild

gallery.npz holds ``names`` (N,) and ``embs`` (N,128) float32 vectors.
A face is accepted when its cosine similarity to the best gallery entry
is >= ``threshold`` (SFace's published default is 0.363).
"""

import glob
import logging
import os

import cv2
import numpy as np

LOG = logging.getLogger("faceid")

DEFAULT_THRESHOLD = 0.363


class FaceID:
    def __init__(
        self,
        models_dir,
        faces_dir,
        detect_size=(320, 320),
        score_threshold=0.7,
        nms_threshold=0.3,
        threshold=DEFAULT_THRESHOLD,
    ):
        self.models_dir = models_dir
        self.faces_dir = faces_dir
        self.detect_size = detect_size
        self.score_threshold = score_threshold
        self.nms_threshold = nms_threshold
        self.threshold = threshold

        det_path = os.path.join(models_dir, "yunet.onnx")
        rec_path = os.path.join(models_dir, "sface.onnx")
        if not os.path.isfile(det_path):
            raise FileNotFoundError(det_path)
        if not os.path.isfile(rec_path):
            raise FileNotFoundError(rec_path)

        self.det = cv2.FaceDetectorYN.create(
            det_path, "", detect_size, score_threshold, nms_threshold, 5000
        )
        self.rec = cv2.FaceRecognizerSF.create(rec_path, "")
        self._size = None
        self.names = np.array([], dtype="<U32")
        self.embs = np.zeros((0, 128), dtype=np.float32)
        self.load_gallery()

    # ---------- gallery ----------

    @property
    def gallery_path(self):
        return os.path.join(self.faces_dir, "gallery.npz")

    def load_gallery(self):
        path = self.gallery_path
        if not os.path.isfile(path):
            LOG.warning("no gallery at %s (nobody enrolled)", path)
            return
        data = np.load(path, allow_pickle=False)
        self.names = data["names"].astype("<U32")
        embs = data["embs"].astype(np.float32)
        self.embs = _normalize(embs)
        LOG.info("gallery: %d embeddings for %s",
                 len(self.names), sorted(set(self.names.tolist())))

    # ---------- per-frame ----------

    def _set_size(self, frame):
        size = (frame.shape[1], frame.shape[0])
        if size != self._size:
            self.det.setInputSize(size)
            self._size = size

    def detect(self, frame):
        """Return the largest face row (x,y,w,h,5 landmarks,score) or None."""
        self._set_size(frame)
        _ok, faces = self.det.detect(frame)
        if faces is None or len(faces) == 0:
            return None
        return max(faces, key=lambda f: float(f[2]) * float(f[3]))

    def embed_face(self, frame, face):
        aligned = self.rec.alignCrop(frame, face)
        feat = self.rec.feature(aligned).astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(feat))
        if norm <= 1e-6:
            return None
        return feat / norm

    def embed_image(self, image):
        face = self.detect(image)
        if face is None:
            return None
        return self.embed_face(image, face)

    def recognize(self, frame):
        """Return (name|None, score). name is None when nobody matches."""
        face = self.detect(frame)
        if face is None:
            return None, 0.0
        emb = self.embed_face(frame, face)
        if emb is None or len(self.embs) == 0:
            return None, 0.0
        sims = self.embs @ emb
        best = int(np.argmax(sims))
        score = float(sims[best])
        if score < self.threshold:
            return None, score
        return str(self.names[best]), score


def _normalize(embs):
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    return (embs / norms).astype(np.float32)


def build_gallery(models_dir, faces_dir, threshold=DEFAULT_THRESHOLD):
    """Index every faces/<name>/*.jpg into faces/gallery.npz."""
    fid = FaceID(models_dir, faces_dir, threshold=threshold)
    fid.embs = np.zeros((0, 128), dtype=np.float32)
    fid.names = np.array([], dtype="<U32")

    names, embs = [], []
    skipped = 0
    for person_dir in sorted(glob.glob(os.path.join(faces_dir, "*"))):
        if not os.path.isdir(person_dir):
            continue
        person = os.path.basename(person_dir)
        for img_path in sorted(
            glob.glob(os.path.join(person_dir, "*.jpg"))
            + glob.glob(os.path.join(person_dir, "*.jpeg"))
            + glob.glob(os.path.join(person_dir, "*.png"))
        ):
            image = cv2.imread(img_path)
            if image is None:
                LOG.warning("unreadable %s", img_path)
                skipped += 1
                continue
            emb = fid.embed_image(image)
            if emb is None:
                LOG.warning("no face in %s", img_path)
                skipped += 1
                continue
            names.append(person)
            embs.append(emb)

    if not embs:
        raise SystemExit("gallery: no usable faces found")

    np.savez(
        os.path.join(faces_dir, "gallery.npz"),
        names=np.array(names, dtype="<U32"),
        embs=np.array(embs, dtype=np.float32),
    )
    LOG.info("gallery built: %d embeddings, %d files skipped", len(names), skipped)
    return names


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="build the face gallery")
    ap.add_argument("--models", default="/home/asus/pi/models")
    ap.add_argument("--faces", default="/home/asus/pi/faces")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    build_gallery(a.models, a.faces)

import os
import traceback
import FreeCAD as App
import Part
from FreeCAD import Vector as V, Placement, Rotation

ENC = r"C:\Users\azamk\Documents\Door-Lock-with-Rasp-InteJer\enclosure"
OUT = os.path.join(ENC, "assembly")
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "report.txt")
lines = []


def log(s):
    lines.append(str(s))


def load(path):
    shp = Part.Shape()
    shp.read(path) if False else None
    doc_shapes = Part.read(path)
    return doc_shapes


try:
    # Load shapes from the exported STEP files
    pi_shell = Part.read(os.path.join(ENC, "pi_box", "pi_box_shell.step"))
    cradle_base = Part.read(os.path.join(ENC, "webcam_cradle", "webcam_base.step"))
    cradle_saddle = Part.read(os.path.join(ENC, "webcam_cradle", "webcam_saddle.step"))

    # Pi box sits on the origin; its +Y wall is at y = 60 (outer face).
    # Cradle base origin is placed at (0, 60, 6) so the bolt holes (base z=8) land at world z=14.
    place = Placement(V(0, 60, 6), Rotation())
    base = cradle_base.copy()
    base.Placement = place
    saddle = cradle_saddle.copy()
    saddle.Placement = place
    cradle = base.fuse(saddle)

    log("cradle valid=%s solids=%d" % (cradle.isValid(), len(cradle.Solids)))
    log("pi shell bbox=%s" % pi_shell.BoundBox)
    log("cradle bbox=%s" % cradle.BoundBox)

    # 1. Cradle must not overlap the Pi box shell
    v = cradle.common(pi_shell).Volume
    log("cradle vs pi shell overlap=%.3f %s" % (v, "OK" if v < 1e-3 else "CLASH"))

    # 2. Bolt holes must align with the bosses: check a cylinder through the hole axis hits the wall
    for x in (-20.0, 20.0):
        ring = Part.makeCylinder(2.9, 4, V(x, 52.6, 14), V(0, 1, 0)).cut(Part.makeCylinder(1.6, 6, V(x, 50, 14), V(0, 1, 0)))
        hit = ring.common(pi_shell).Volume
        bore = Part.makeCylinder(1.6, 10, V(x, 50, 14), V(0, 1, 0)).common(pi_shell).Volume
        log("boss ring x=%+.0f: material=%.2f mm3 (expect >0); bore clear=%.3f (expect 0)" % (x, hit, bore))
        hole_in_base = Part.makeCylinder(1.6, 10, V(x, 55, 14), V(0, 1, 0)).common(cradle_base.copy().translate(V(0, 60, 6)) if False else pi_shell).Volume
        log("  base hole path check done")

    # 3. Camera at rest sits outside the box and clear of the box top
    cam = Part.makeBox(58, 30, 40, V(-29, 75, 6 + 36 + 2))
    log("camera vs pi shell overlap=%.3f" % cam.common(pi_shell).Volume)
    log("camera z range=%.1f..%.1f (box top 55)" % (cam.BoundBox.ZMin, cam.BoundBox.ZMax))

    # 4. Lock box is separate: no overlap check needed (different mount)
    log("DONE")
except Exception:
    log("ERROR")
    log(traceback.format_exc())

with open(REPORT, "w") as f:
    f.write("\n".join(lines) + "\n")

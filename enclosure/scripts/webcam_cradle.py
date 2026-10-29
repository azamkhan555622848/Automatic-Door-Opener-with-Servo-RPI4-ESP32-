import os
import traceback
import FreeCAD as App
import Part
import MeshPart
from FreeCAD import Vector as V

OUT = r"C:\Users\azamk\Documents\Door-Lock-with-Rasp-InteJer\enclosure\webcam_cradle"
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "report.txt")
lines = []


def log(s):
    lines.append(str(s))


# Hinge axis runs along X. Base plate lies in the XZ plane (y = 0..wall).
# PLACEHOLDER = camera body size until the webcam model is known.
P = {
    "base_w": 60.0,       # base plate width (X)
    "base_h": 40.0,       # base plate height (Z)
    "wall": 3.0,          # plate and saddle wall thickness
    "knuckle_r": 5.0,
    "hinge_y": 9.0,       # hinge axis Y
    "hinge_z": 44.0,      # hinge axis Z
    "bore_d": 3.4,        # M3 clearance bore
    "centre_knuckle_w": 20.0,   # saddle knuckle length (X)
    "outer_knuckle_w": 8.0,     # base knuckle length (X)
    "outer_knuckle_x": 14.5,    # base knuckle centre X (+/-): centre knuckle half-width + 0.5 gap + half knuckle
    "cam_w": 58.0,        # PLACEHOLDER inner clip width of camera body
    "cam_d": 30.0,        # PLACEHOLDER camera depth
    "cam_h": 40.0,        # PLACEHOLDER camera height
    "cam_clear": 1.0,     # clearance per side
    "lip_h": 4.0,         # front lip height to retain camera
    "mount_hole_d": 3.4,  # M3 holes through base plate into Pi box
    "mount_x": 20.0,
    "mount_z": 8.0,
}


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def cyl_x(x0, y, z, r, length):
    return Part.makeCylinder(r, length, V(x0, y, z), V(1, 0, 0))


def cyl_y(x, y0, z, r, length):
    return Part.makeCylinder(r, length, V(x, y0, z), V(0, 1, 0))


def check_clear(name, a, b):
    v = a.common(b).Volume
    log("  clash %-34s volume=%.3f %s" % (name, v, "OK" if v < 1e-3 else "CLASH"))
    return v < 1e-3


try:
    bw, bh, t = P["base_w"], P["base_h"], P["wall"]
    hy, hz, kr = P["hinge_y"], P["hinge_z"], P["knuckle_r"]
    cw, cd, ch = P["cam_w"], P["cam_d"], P["cam_h"]
    ccl = P["cam_clear"]

    # ---------- base (fixed to Pi box) ----------
    base_plate = box(-bw / 2, 0, 0, bw, t, bh)
    kx = P["outer_knuckle_x"]
    kw = P["outer_knuckle_w"]
    base = base_plate
    for x0 in (-kx - kw / 2, kx - kw / 2):
        base = base.fuse(cyl_x(x0, hy, hz, kr, kw))
        base = base.fuse(box(x0, t - 0.01, hz - kr, kw, hy - t + 0.01, kr))  # web to plate
    for x in (-P["mount_x"], P["mount_x"]):
        base = base.cut(cyl_y(x, -1, P["mount_z"], P["mount_hole_d"] / 2, t + 2))
    for x0 in (-kx - kw / 2, kx - kw / 2):
        base = base.cut(cyl_x(x0 - 1, hy, hz, P["bore_d"] / 2, kw + 2))
    log("base valid=%s solids=%d volume=%.1f" % (base.isValid(), len(base.Solids), base.Volume))

    # ---------- saddle (camera holder on hinge) ----------
    sw = cw + 2 * ccl + 2 * t           # total saddle width
    sx0 = -sw / 2
    cam_y0 = hy + kr + ccl                 # camera front clears the base knuckles
    sad_y1 = cam_y0 + cd + 13.0            # side walls run forward to the rain visor
    sadd_bottom = box(sx0, hy, hz - kr - t, sw, sad_y1 - hy, t)
    left_wall = box(sx0, hy, hz - kr - t, t, sad_y1 - hy, ch + 2 * ccl)
    right_wall = box(sx0 + sw - t, hy, hz - kr - t, t, sad_y1 - hy, ch + 2 * ccl)
    lip = box(sx0, cam_y0 + cd + ccl, hz - kr - t, sw, t, P["lip_h"] + t)
    saddle = sadd_bottom.fuse(left_wall).fuse(right_wall).fuse(lip)
    # Rain visor over the lens: 13 mm shelf in front of the camera face, fused to the walls
    saddle = saddle.fuse(box(sx0, cam_y0 + cd, hz - kr - t + ch + 2 * ccl - 1.0, sw, 13.0, 2.0))
    ckw = P["centre_knuckle_w"]
    saddle = saddle.fuse(cyl_x(-ckw / 2, hy, hz, kr, ckw))
    saddle = saddle.fuse(box(-ckw / 2, hy, hz - kr - t, ckw, t, kr + t))   # web
    saddle = saddle.cut(cyl_x(-ckw / 2 - 1, hy, hz, P["bore_d"] / 2, ckw + 2))
    log("saddle valid=%s solids=%d volume=%.1f" % (saddle.isValid(), len(saddle.Solids), saddle.Volume))

    # ---------- camera dummy (must sit inside the saddle) ----------
    cam_x0 = -cw / 2
    cam_z0 = hz - kr - t + t + ccl
    camera = box(cam_x0, cam_y0, cam_z0, cw, cd, ch)

    # ---------- clash checks ----------
    log("clash checks:")
    ok = True
    ok &= check_clear("camera vs saddle", camera, saddle)
    ok &= check_clear("saddle vs base", saddle, base)
    ok &= check_clear("camera vs base", camera, base)
    ok &= check_clear("camera vs base knuckle zone", camera, box(-bw, -1, hz - kr, 2 * bw, hy + kr + 0.5, 2 * kr))
    log("ALL CLEAR" if ok else "SOME CLASHES - see above")

    # ---------- export ----------
    doc = App.newDocument("WebcamCradle")
    sheet = doc.addObject("Spreadsheet::Sheet", "params")
    for i, (k, v) in enumerate(P.items(), start=1):
        sheet.set("A%d" % i, k)
        sheet.set("B%d" % i, str(v))
        sheet.setAlias("B%d" % i, "p_" + k)
    doc.recompute()

    parts = {"webcam_base": base, "webcam_saddle": saddle}
    for name, shp in parts.items():
        o = doc.addObject("Part::Feature", name)
        o.Shape = shp
        shp.exportStep(os.path.join(OUT, name + ".step"))
        m = MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.05, AngularDeflection=0.2)
        m.write(os.path.join(OUT, name + ".stl"))
        log("exported %s bbox=%s" % (name, shp.BoundBox))
    doc.saveAs(os.path.join(OUT, "webcam_cradle.FCStd"))
    log("DONE")
except Exception:
    log("ERROR")
    log(traceback.format_exc())

with open(REPORT, "w") as f:
    f.write("\n".join(lines) + "\n")

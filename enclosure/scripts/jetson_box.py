import os
import traceback
import FreeCAD as App
import Part
import MeshPart
from FreeCAD import Vector as V

OUT = r"C:\Users\azamk\Documents\Door-Lock-with-Rasp-InteJer\enclosure\jetson_box"
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "report.txt")
lines = []


def log(s):
    lines.append(str(s))


# VERIFY_ = dimension NOT retrieved from a datasheet. Replace before printing.
P = {
    "W": 190.0,
    "D": 100.0,
    "board_cx": -20.0,         # board centre X (holes are centred on it)
    "H_BASE": 40.0,            # tall base: holds heatsink + board
    "H_COVER": 30.0,
    "wall": 2.4,
    "floor": 3.0,
    "cover_top": 3.0,
    "fillet_v": 6.0,
    "fillet_top": 3.0,
    "gasket_w": 2.0,
    "gasket_d": 2.0,
    "gasket_inset": 4.0,
    "board_L": 100.0,          # VERIFY_ Jetson carrier length (X)
    "board_W": 80.0,           # VERIFY_ Jetson carrier width (Y)
    "board_t": 1.6,
    "standoff_h": 5.0,
    "hole_d": 3.2,             # VERIFY_ carrier mount hole diameter
    "hole_pitch_x": 86.0,      # VERIFY_ mount hole pattern
    "hole_pitch_y": 50.0,      # VERIFY_ mount hole pattern
    "heatsink_L": 40.0,        # VERIFY_ heatsink footprint
    "heatsink_W": 40.0,        # VERIFY_ heatsink footprint
    "heatsink_H": 25.0,        # VERIFY_ heatsink height above carrier
    "heatsink_x": -20.0,       # VERIFY_ SoC position (board centre)
    "heatsink_y": 0.0,
    "fan_d": 40.0,
    "fan_hole": 32.0,
    "fan_t": 10.0,
    "boss_x": 55.0,
    "boss_y": 42.0,
    "boss_r": 3.5,
    "boss_hole": 3.2,
    "gland_d": 12.5,
    "gland_x": -62.0,          # -X wall (VERIFY_ position)
    "gland_z": 14.0,
    "usb_w": 13.0,             # VERIFY_ USB-A port aperture
    "usb_h": 7.0,
    "usb_x0": 62.0,            # +X wall ports (VERIFY_ placement)
    "usb_y": -20.0,
    "usb_z": 14.0,
    "dc_w": 9.0,               # VERIFY_ DC barrel aperture
    "dc_h": 11.0,
    "dc_x": -25.0,             # -Y wall (VERIFY_)
    "dc_z": 14.0,
    "rs_L": 60.0,              # USB-RS485 adapter placeholder (along Y)
    "rs_W": 20.0,              # along X
    "rs_H": 12.0,
    "rs_x": -82.0,             # strip beside the board, -X side
    "rs_y": 0.0,
    "buck_L": 65.0,            # 12->5 V buck, 5 A, placeholder (along Y)
    "buck_W": 47.0,            # along X
    "buck_H": 25.0,
    "buck_x": 62.0,            # strip beside the board, +X side
    "buck_y": 0.0,
    "webcam_boss_x": 20.0,     # matches webcam_cradle.py mounting bosses
    "webcam_boss_z": 14.0,
    "drain_d": 2.0,
    "intake_w": 3.0,
    "intake_h": 8.0,
}


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def cyl(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(0, 0, 1))


def cyl_y(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(0, 1, 0))


def cyl_x(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(1, 0, 0))


def check_clear(name, a, b):
    v = a.common(b).Volume
    log("  clash %-34s volume=%.3f %s" % (name, v, "OK" if v < 1e-3 else "CLASH"))
    return v < 1e-3


def round_outer(solid, v_r, top_r, top_z=None):
    """Fillet vertical outer edges, then top edges, on an outer block BEFORE any cuts."""
    try:
        vert = [e for e in solid.Edges
                if e.BoundBox.ZLength > 1 and e.BoundBox.XLength < 1e-3 and e.BoundBox.YLength < 1e-3]
        solid = solid.makeFillet(v_r, vert)
        if top_z is not None and top_r > 0:
            top = [e for e in solid.Edges
                   if e.BoundBox.ZLength < 1e-3 and abs(e.BoundBox.ZMin - top_z) < 1e-3]
            solid = solid.makeFillet(top_r, top)
        log("  fillet ok (vertical %.1f, top %.1f)" % (v_r, top_r))
    except Exception as ex:
        log("  FILLET FAILED, using plain box: %r" % ex)
    return solid


try:
    W, D = P["W"], P["D"]
    t, fl = P["wall"], P["floor"]
    hb, hc = P["H_BASE"], P["H_COVER"]
    H = hb + hc
    xw, yw = W / 2, D / 2

    # ---------- base tray (z 0..hb), filleted before cuts ----------
    base_outer = round_outer(box(-xw, -yw, 0, W, D, hb), P["fillet_v"], 0.0)
    base = base_outer
    base = base.cut(box(-xw + t, -yw + t, fl, W - 2 * t, D - 2 * t, hb))           # cavity
    gi = P["gasket_inset"]
    ring_out = box(-xw + gi, -yw + gi, hb - P["gasket_d"], W - 2 * gi, D - 2 * gi, P["gasket_d"] + 1)
    ring_in = box(-xw + gi + P["gasket_w"], -yw + gi + P["gasket_w"], hb - P["gasket_d"] - 1,
                  W - 2 * gi - 2 * P["gasket_w"], D - 2 * gi - 2 * P["gasket_w"], P["gasket_d"] + 3)
    base = base.cut(ring_out.cut(ring_in))                                           # gasket groove

    # board standoffs and screw bosses
    bx, by = P["hole_pitch_x"] / 2, P["hole_pitch_y"] / 2
    bcx = P["board_cx"]
    board_z = fl + P["standoff_h"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            base = base.fuse(cyl(bcx + sx * bx, sy * by, fl, P["boss_r"], P["standoff_h"]))
            base = base.cut(cyl(bcx + sx * bx, sy * by, fl + 1, P["hole_d"] / 2, P["standoff_h"]))
    for sx in (-1, 1):
        for sy in (-1, 1):
            base = base.cut(cyl(sx * P["boss_x"], sy * P["boss_y"], -1, P["boss_hole"] / 2, fl + 2))  # floor screw holes

    # ports (cut individually; each is a clearance aperture)
    base = base.cut(box(P["usb_x0"], P["usb_y"], P["usb_z"], t + 2, P["usb_w"], P["usb_h"]))
    base = base.cut(box(P["usb_x0"], P["usb_y"] + 16, P["usb_z"], t + 2, P["usb_w"], P["usb_h"]))
    base = base.cut(cyl_y(P["dc_x"], -yw - 1, P["dc_z"], P["dc_w"] / 2, t + 2))
    base = base.cut(cyl_x(P["gland_x"] - 1, 0, P["gland_z"], P["gland_d"] / 2, t + 2))
    # gland position moved to -X wall: use cyl along X through the wall
    base = base.cut(cyl_y(0, 0, 0, 0.01, 0.01)) if False else base

    # intake slots on -X wall, low, with rain hood
    for vy in (-30, -24, -18, 18, 24, 30):
        base = base.cut(box(-xw - 1, vy, 4, t + 2, 3, P["intake_h"]))
    base = base.fuse(box(-xw - 6, -33, 13, 6, 36, 1.6))   # hood

    # webcam cradle bosses on +Y wall
    for x in (-P["webcam_boss_x"], P["webcam_boss_x"]):
        base = base.fuse(cyl_y(x, yw - t - 5, P["webcam_boss_z"], 3.0, 5))
        base = base.cut(cyl_y(x, yw - t - 6, P["webcam_boss_z"], 1.6, 6))
        base = base.cut(cyl_y(x, yw - t - 1, P["webcam_boss_z"], 1.7, t + 2))

    # drains
    for dx, dy in ((-50.0, -44.0), (50.0, -44.0)):
        base = base.cut(cyl(dx, dy, -1, P["drain_d"], fl + 2))

    log("base valid=%s solids=%d volume=%.1f" % (base.isValid(), len(base.Solids), base.Volume))

    # ---------- cover (z hb..H), hangs from ceiling with screw bosses ----------
    cover = round_outer(box(-xw, -yw, hb, W, D, hc), P["fillet_v"], P["fillet_top"], top_z=H)
    cover = cover.cut(box(-xw + t, -yw + t, hb - 1, W - 2 * t, D - 2 * t, hc - P["cover_top"] + 1))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cover = cover.fuse(cyl(sx * P["boss_x"], sy * P["boss_y"], hb, P["boss_r"], hc - P["cover_top"]))
            cover = cover.cut(cyl(sx * P["boss_x"], sy * P["boss_y"], hb, P["boss_hole"] / 2, hc - P["cover_top"]))
    # fan opening over heatsink (top face)
    cover = cover.cut(cyl(P["heatsink_x"], P["heatsink_y"], H - P["cover_top"] - 1, P["fan_d"] / 2 - 1, P["cover_top"] + 2))
    for dx in (-1, 1):
        for dy in (-1, 1):
            cover = cover.cut(cyl(P["heatsink_x"] + dx * P["fan_hole"] / 2, P["heatsink_y"] + dy * P["fan_hole"] / 2,
                                  H - P["cover_top"] - 1, 1.6, P["cover_top"] + 2))
    log("cover valid=%s solids=%d volume=%.1f" % (cover.isValid(), len(cover.Solids), cover.Volume))

    # ---------- dummies (assembled positions) ----------
    board = box(bcx - P["board_L"] / 2, -P["board_W"] / 2, board_z, P["board_L"], P["board_W"], P["board_t"])
    hs_z = board_z + P["board_t"]
    heatsink = box(P["heatsink_x"] - P["heatsink_L"] / 2, P["heatsink_y"] - P["heatsink_W"] / 2, hs_z,
                   P["heatsink_L"], P["heatsink_W"], P["heatsink_H"])
    fan = cyl(P["heatsink_x"], P["heatsink_y"], H, P["fan_d"] / 2, P["fan_t"])   # on top of cover
    rs = box(P["rs_x"] - P["rs_W"] / 2, P["rs_y"] - P["rs_L"] / 2, fl, P["rs_W"], P["rs_L"], P["rs_H"])
    buck = box(P["buck_x"] - P["buck_W"] / 2, P["buck_y"] - P["buck_L"] / 2, fl, P["buck_W"], P["buck_L"], P["buck_H"])

    log("clash checks:")
    ok = True
    ok &= check_clear("board vs base", board, base)
    ok &= check_clear("heatsink vs cover", heatsink, cover)
    ok &= check_clear("heatsink vs base walls", heatsink, base)
    ok &= check_clear("heatsink vs board holes", heatsink, base.common(board))
    ok &= check_clear("RS485 vs base", rs, base)
    ok &= check_clear("RS485 vs board", rs, board)
    ok &= check_clear("buck vs base", buck, base)
    ok &= check_clear("buck vs board", buck, board)
    ok &= check_clear("buck vs heatsink", buck, heatsink)
    ok &= check_clear("RS485 vs buck", rs, buck)
    # port apertures: dummy connectors must sit entirely in the removed wall space
    for name, c in (("USB-A #1", box(P["usb_x0"] - 1, P["usb_y"] + 1, P["usb_z"] + 1, t + 4, P["usb_w"] - 2, P["usb_h"] - 2)),):
        ok &= check_clear(name + " vs base wall", c, base)
    log("ALL CLEAR" if ok else "SOME CLASHES - see above")
    log("NOTE: fan body sits on top of cover (exterior); thermal path not simulated.")

    # ---------- export ----------
    doc = App.newDocument("JetsonBox")
    sheet = doc.addObject("Spreadsheet::Sheet", "params")
    for i, (k, v) in enumerate(P.items(), start=1):
        sheet.set("A%d" % i, k)
        sheet.set("B%d" % i, str(v))
        sheet.setAlias("B%d" % i, "p_" + k)
    doc.recompute()

    parts = {"jetson_base": base, "jetson_cover": cover}
    for name, shp in parts.items():
        o = doc.addObject("Part::Feature", name)
        o.Shape = shp
        shp.exportStep(os.path.join(OUT, name + ".step"))
        m = MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.05, AngularDeflection=0.2)
        m.write(os.path.join(OUT, name + ".stl"))
        log("exported %s bbox=%s" % (name, shp.BoundBox))
    doc.saveAs(os.path.join(OUT, "jetson_box.FCStd"))
    log("DONE")
except Exception:
    log("ERROR")
    log(traceback.format_exc())

with open(REPORT, "w") as f:
    f.write("\n".join(lines) + "\n")

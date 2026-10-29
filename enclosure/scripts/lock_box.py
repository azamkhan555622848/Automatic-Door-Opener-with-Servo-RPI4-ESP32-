import os
import traceback
import FreeCAD as App
import Part
import MeshPart
from FreeCAD import Vector as V

OUT = r"C:\Users\azamk\Documents\Door-Lock-with-Rasp-InteJer\enclosure\lock_box"
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "report.txt")
lines = []


def log(s):
    lines.append(str(s))


# Parameters. Z=0 is the rose face; the backplate sits on the rose.
# Everything marked PLACEHOLDER must be checked against real parts.
P = {
    "W": 150.0,          # outer X
    "D": 90.0,           # outer Y
    "H": 60.0,           # outer Z (shell height, lid sits on top)
    "floor": 3.0,        # backplate thickness
    "wall": 2.4,         # wall thickness (6 perimeters at 0.4 nozzle)
    "lid_t": 2.4,
    "boss_r": 3.5,       # corner screw boss
    "boss_hole": 3.2,    # M3 heat-set insert hole
    "boss_x": 70.0,
    "boss_y": 40.0,
    "boss_top": 56.0,
    "blade_w": 25.0,     # PLACEHOLDER turn piece width
    "blade_t": 8.0,      # PLACEHOLDER turn piece thickness
    "fit": 0.4,          # clearance per side on coupler slot
    "servo_L": 40.7,     # MG996R body length (X)
    "servo_W": 19.7,     # body width (Y)
    "servo_H": 37.0,     # body height (Z) - PLACEHOLDER, verify
    "shaft_off": 10.0,   # shaft offset from body -X end
    "shaft_z": 16.0,     # servo shaft face height
    "tab_z": 28.0,       # tab plane above shaft face
    "tab_span": 54.5,
    "tab_pitch": 48.0,
    "tab_t": 2.5,
    "cheek_w": 6.0,
    "cheek_d": 14.0,
    "coupler_r": 9.5,
    "gland_d": 12.5,     # PG7 hole
    "gland_x": -45.0,
    "gland_z": 12.0,
    "led_d": 3.0,
    "led_x": 50.0,
    "led_y": 35.0,
}


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def cyl(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(0, 0, 1))


def cyl_y(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(0, 1, 0))


def check_clear(name, a, b):
    v = a.common(b).Volume
    log("  clash %-28s volume=%.3f %s" % (name, v, "OK" if v < 1e-3 else "CLASH"))
    return v < 1e-3


try:
    W, D, H = P["W"], P["D"], P["H"]
    t, fl = P["wall"], P["floor"]
    bx, by = P["boss_x"], P["boss_y"]

    # ---------- servo geometry (dummy, for clearance checks) ----------
    shaft_x = 0.0
    body_x0 = shaft_x - P["shaft_off"]
    body_y0 = -P["servo_W"] / 2
    body_cx = body_x0 + P["servo_L"] / 2
    servo_body = box(body_x0, body_y0, P["shaft_z"], P["servo_L"], P["servo_W"], P["servo_H"])
    tab_z = P["shaft_z"] + P["tab_z"]
    tab_l = body_cx - P["tab_span"] / 2
    tab_r = body_cx + P["tab_span"] / 2
    tab_A = box(tab_l, body_y0, tab_z, body_x0 - tab_l, P["servo_W"], P["tab_t"])
    tab_B = box(body_x0 + P["servo_L"], body_y0, tab_z, tab_r - (body_x0 + P["servo_L"]), P["servo_W"], P["tab_t"])
    hole_A = body_cx - P["tab_pitch"] / 2
    hole_B = body_cx + P["tab_pitch"] / 2

    # ---------- lock box shell ----------
    outer = box(-W / 2, -D / 2, 0, W, D, H)
    cavity = box(-W / 2 + t, -D / 2 + t, fl, W - 2 * t, D - 2 * t, H)
    shell = outer.cut(cavity)

    for sx in (-1, 1):
        for sy in (-1, 1):
            shell = shell.fuse(cyl(sx * bx, sy * by, fl, P["boss_r"], P["boss_top"] - fl))

    # cheeks that carry the servo tabs
    cheek_A = box(hole_A - P["cheek_w"] / 2, -P["cheek_d"] / 2, fl, P["cheek_w"], P["cheek_d"], tab_z - fl)
    cheek_B = box(hole_B - P["cheek_w"] / 2, -P["cheek_d"] / 2, fl, P["cheek_w"], P["cheek_d"], tab_z - fl)
    shell = shell.fuse(cheek_A).fuse(cheek_B)

    # cuts
    for sx in (-1, 1):
        for sy in (-1, 1):
            shell = shell.cut(cyl(sx * bx, sy * by, 6.0, P["boss_hole"] / 2, P["boss_top"] - 6.0 + 1))
    # cheek tab screw inserts
    for hx in (hole_A, hole_B):
        shell = shell.cut(cyl(hx, 0, tab_z - 8, 2.1, 9))
    # blade slot through backplate, sized to blade + 1 mm
    shell = shell.cut(box(-(P["blade_w"] + 1) / 2, -(P["blade_t"] + 1) / 2, -1, P["blade_w"] + 1, P["blade_t"] + 1, fl + 2))
    # PG7 cable gland hole in +Y wall
    shell = shell.cut(cyl_y(P["gland_x"], D / 2 - 5, P["gland_z"], P["gland_d"] / 2, 10))
    # Drain holes in the backplate (water leaves onto the door face)
    for dx, dy in ((-69.0, -38.0), (69.0, -38.0)):
        shell = shell.cut(cyl(dx, dy, -1, 2.0, fl + 2))

    log("shell valid=%s solids=%d volume=%.1f" % (shell.isValid(), len(shell.Solids), shell.Volume))

    # ---------- lid ----------
    lid = box(-W / 2, -D / 2, H, W, D, P["lid_t"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            lid = lid.cut(cyl(sx * bx, sy * by, H - 1, 1.6, P["lid_t"] + 2))
    lid = lid.cut(cyl(P["led_x"], P["led_y"], H - 1, P["led_d"] / 2, P["lid_t"] + 2))

    log("lid valid=%s solids=%d" % (lid.isValid(), len(lid.Solids)))

    # ---------- coupler ----------
    slot_w = P["blade_w"] + 2 * P["fit"]
    slot_t = P["blade_t"] + 2 * P["fit"]
    coupler = cyl(0, 0, 4.0, P["coupler_r"], P["shaft_z"] - 4.0)
    coupler = coupler.cut(box(-slot_w / 2, -slot_t / 2, 3.0, slot_w, slot_t, 14.0 - 3.0))
    for sy in (-1, 1):
        coupler = coupler.cut(cyl(0, sy * 6.5, 3.0, 1.1, 15))
    log("coupler valid=%s solids=%d" % (coupler.isValid(), len(coupler.Solids)))

    # ---------- fit checks ----------
    comp = {
        "buck_5A (65x47x25)": box(-66, -40, fl, 47, 65, 25),
        "ESP32_DevKit (55x28x20)": box(40, -27, fl, 28, 55, 20),
        "MAX485 (44x14x10)": box(-66, 27, fl, 44, 14, 10),
    }
    log("fit checks:")
    ok = True
    ok &= check_clear("servo body vs shell", servo_body, shell)
    ok &= check_clear("tab A vs shell", tab_A, shell)
    ok &= check_clear("tab B vs shell", tab_B, shell)
    ok &= check_clear("servo body vs cheek A", servo_body, cheek_A)
    ok &= check_clear("servo body vs cheek B", servo_body, cheek_B)
    ok &= check_clear("coupler vs cheek A", coupler, cheek_A)
    ok &= check_clear("coupler vs cheek B", coupler, cheek_B)
    for name, c in comp.items():
        ok &= check_clear(name + " vs shell", c, shell)
        ok &= check_clear(name + " vs servo", c, servo_body)
        ok &= check_clear(name + " vs coupler", c, coupler)
    names = list(comp.keys())
    ok &= check_clear(names[0] + " vs MAX485", comp[names[0]], comp["MAX485 (44x14x10)"])
    ok &= check_clear(names[0] + " vs ESP32", comp[names[0]], comp["ESP32_DevKit (55x28x20)"])
    log("ALL CLEAR" if ok else "SOME CLASHES - see above")

    # ---------- export ----------
    doc = App.newDocument("LockBox")
    sheet = doc.addObject("Spreadsheet::Sheet", "params")
    for i, (k, v) in enumerate(P.items(), start=1):
        sheet.set("A%d" % i, k)
        sheet.set("B%d" % i, str(v))
        sheet.setAlias("B%d" % i, "p_" + k)
    doc.recompute()

    parts = {"lock_box_shell": shell, "lock_box_lid": lid, "lock_box_coupler": coupler}
    for name, shp in parts.items():
        o = doc.addObject("Part::Feature", name)
        o.Shape = shp
        shp.exportStep(os.path.join(OUT, name + ".step"))
        m = MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.05, AngularDeflection=0.2)
        m.write(os.path.join(OUT, name + ".stl"))
        log("exported %s bbox=%s" % (name, shp.BoundBox))
    doc.saveAs(os.path.join(OUT, "lock_box.FCStd"))
    log("DONE")
except Exception:
    log("ERROR")
    log(traceback.format_exc())

with open(REPORT, "w") as f:
    f.write("\n".join(lines) + "\n")

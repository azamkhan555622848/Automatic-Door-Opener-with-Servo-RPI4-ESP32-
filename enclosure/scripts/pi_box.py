import os
import traceback
import FreeCAD as App
import Part
import MeshPart
from FreeCAD import Vector as V

OUT = r"C:\Users\azamk\Documents\Door-Lock-with-Rasp-InteJer\enclosure\pi_box"
os.makedirs(OUT, exist_ok=True)
REPORT = os.path.join(OUT, "report.txt")
lines = []


def log(s):
    lines.append(str(s))


# Origin = box centre on the floor. Z=0 is the floor underside.
# PLACEHOLDER = verify with calipers / vendor mechanical drawing.
P = {
    "W": 150.0,          # outer X
    "D": 120.0,          # outer Y
    "H": 55.0,           # outer Z (lid sits on top)
    "floor": 3.0,
    "wall": 2.4,
    "lid_t": 2.4,
    "pi_L": 85.0,        # Pi 4 board X
    "pi_W": 56.0,        # Pi 4 board Y
    "pi_t": 1.6,
    "pi_hole_x": 58.0,   # mounting pattern
    "pi_hole_y": 49.0,
    "pi_edge": 3.5,      # first hole inset from board edge
    "pi_standoff_h": 5.0,
    "pi_boss_r": 3.0,
    "pi_insert_d": 3.2,  # M2.5 heat-set insert
    "pi_x_edge": 70.6,   # USB/ports edge of the Pi, sits 2 mm inside +X wall
    "kl_L": 75.0,        # PLACEHOLDER KL720 stick (along Y)
    "kl_W": 25.0,
    "kl_H": 12.0,
    "rs_L": 60.0,        # PLACEHOLDER USB-RS485 adapter (along Y)
    "rs_W": 20.0,
    "rs_H": 12.0,
    "buck_L": 40.0,      # PLACEHOLDER 12->5 V 3 A buck (along X)
    "buck_W": 25.0,
    "buck_H": 15.0,
    "clear_pocket": 0.5,
    "fan_d": 30.0,       # 30 mm fan
    "fan_hole": 24.0,    # fan screw pattern
    "fan_x": -48.0,
    "fan_y": 30.0,
    "jack_d": 11.0,      # 12 V barrel jack
    "jack_x": -55.0,
    "jack_z": 22.0,
    "gland_d": 12.5,     # PG7 cable gland
    "gland_x": -45.0,
    "gland_z": 14.0,
    "boss_x": 66.0,
    "boss_y": 50.0,
    "boss_r": 3.5,
    "boss_top": 52.0,
    "boss_hole": 3.2,
    "vent_w": 3.0,
}


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def cyl(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(0, 0, 1))


def cyl_y(x, y, z, r, h):
    return Part.makeCylinder(r, h, V(x, y, z), V(0, 1, 0))


def check_clear(name, a, b):
    v = a.common(b).Volume
    log("  clash %-34s volume=%.3f %s" % (name, v, "OK" if v < 1e-3 else "CLASH"))
    return v < 1e-3


try:
    W, D, H = P["W"], P["D"], P["H"]
    t, fl = P["wall"], P["floor"]
    xw, yw = W / 2, D / 2
    ix, iy = xw - t, yw - t  # inner half-extents

    # ---------- Pi geometry ----------
    pi_x0 = P["pi_x_edge"] - P["pi_L"]
    pi_y0 = -P["pi_W"] / 2
    pi_z = fl + P["pi_standoff_h"]
    pi_board = box(pi_x0, pi_y0, pi_z, P["pi_L"], P["pi_W"], P["pi_t"])
    hx = [pi_x0 + P["pi_edge"], pi_x0 + P["pi_edge"] + P["pi_hole_x"]]
    hy = [pi_y0 + P["pi_edge"], pi_y0 + P["pi_edge"] + P["pi_hole_y"]]

    # ---------- shell ----------
    outer = box(-xw, -yw, 0, W, D, H)
    cavity = box(-ix, -iy, fl, W - 2 * t, D - 2 * t, H)
    shell = outer.cut(cavity)

    # Pi standoffs
    for x in hx:
        for y in hy:
            shell = shell.fuse(cyl(x, y, fl, P["pi_boss_r"], P["pi_standoff_h"]))
    # Corner screw bosses for lid
    for sx in (-1, 1):
        for sy in (-1, 1):
            shell = shell.fuse(cyl(sx * P["boss_x"], sy * P["boss_y"], fl, P["boss_r"], P["boss_top"] - fl))
    # Heat-set insert holes in standoffs and corner bosses
    for x in hx:
        for y in hy:
            shell = shell.cut(cyl(x, y, fl + 1, P["pi_insert_d"] / 2, P["pi_standoff_h"] + 0.1))
    for sx in (-1, 1):
        for sy in (-1, 1):
            shell = shell.cut(cyl(sx * P["boss_x"], sy * P["boss_y"], 6.0, P["boss_hole"] / 2, P["boss_top"] - 6.0 + 1))

    # Port openings on +X wall (positions are PLACEHOLDER - verify on board)
    port_z0, port_z1 = pi_z, pi_z + 16
    shell = shell.cut(box(xw - t - 1, -22, port_z0, t + 2, 11, port_z1 - port_z0))   # USB-C / power
    shell = shell.cut(box(xw - t - 1, -6, port_z0 + 2, t + 2, 9, port_z1 - port_z0 - 2))  # micro HDMI
    shell = shell.cut(box(xw - t - 1, 6, port_z0 + 1, t + 2, 16, 14))                # Ethernet
    shell = shell.cut(box(xw - t - 1, 14, port_z0 + 1, t + 2, 22, 14))              # USB-A stack

    # 12 V barrel jack on -Y wall
    shell = shell.cut(cyl_y(P["jack_x"], -yw - 1, P["jack_z"], P["jack_d"] / 2, t + 2))
    # PG7 cable gland on +Y wall
    shell = shell.cut(cyl_y(P["gland_x"], yw - t - 1, P["gland_z"], P["gland_d"] / 2, t + 2))
    # Webcam cradle mount on the +Y wall: two M3 bosses inside, bolt holes through the wall.
    # Cradle base plate holes sit at world z=14 (cradle origin z=6, plate hole z=8).
    for x in (-20.0, 20.0):
        shell = shell.fuse(cyl_y(x, yw - t - 5, 14, 3.0, 5))
        shell = shell.cut(cyl_y(x, yw - t - 6, 14, 1.6, 6))
        shell = shell.cut(cyl_y(x, yw - t - 1, 14, 1.7, t + 2))
    # Drain holes in the floor so water that gets in can leave
    for dx, dy in ((-68.0, -52.0), (-68.0, 52.0)):
        shell = shell.cut(cyl(dx, dy, -1, 2.0, fl + 2))
    # Outdoor: no open vents on the cradle (-Y) side. Slots go in the -X wall,
    # each group protected by a rain hood fused on after the cuts.
    for vy in (-52, -46, -40, 40, 46, 52):
        shell = shell.cut(box(-xw - 1, vy, 4, t + 2, 3, 8))
    shell = shell.fuse(box(-xw - 6, -54, 13, 6, 18, 1.6))
    shell = shell.fuse(box(-xw - 6, 37, 13, 6, 19, 1.6))

    log("shell valid=%s solids=%d volume=%.1f" % (shell.isValid(), len(shell.Solids), shell.Volume))

    # ---------- lid ----------
    lid = box(-xw, -yw, H, W, D, P["lid_t"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            lid = lid.cut(cyl(sx * P["boss_x"], sy * P["boss_y"], H - 1, 1.6, P["lid_t"] + 2))
    # Lid is solid for outdoor use: no fan opening, no vent slots.
    # Seal with an adhesive closed-cell gasket strip on the lid underside.
    log("lid valid=%s solids=%d" % (lid.isValid(), len(lid.Solids)))

    # ---------- dummies for clash checks ----------
    kl_x0 = -xw + t + 2
    kl = box(kl_x0, -P["kl_L"] / 2, fl, P["kl_W"], P["kl_L"], P["kl_H"])
    rs_x0 = kl_x0 + P["kl_W"] + 2
    rs = box(rs_x0, -P["rs_L"] / 2, fl, P["rs_W"], P["rs_L"], P["rs_H"])
    buck = box(-30, -55, fl, P["buck_L"], P["buck_W"], P["buck_H"])
    jack_body = cyl_y(P["jack_x"], -yw + t, P["jack_z"], 6.0, 12)           # barrel body inside the wall

    # ---------- fit checks ----------
    log("clash checks:")
    ok = True
    ok &= check_clear("Pi board vs shell", pi_board, shell)
    ok &= check_clear("KL720 vs shell", kl, shell)
    ok &= check_clear("RS485 vs shell", rs, shell)
    ok &= check_clear("buck vs shell", buck, shell)
    ok &= check_clear("KL720 vs Pi board", kl, pi_board)
    ok &= check_clear("RS485 vs Pi board", rs, pi_board)
    ok &= check_clear("buck vs Pi board", buck, pi_board)
    ok &= check_clear("KL720 vs RS485", kl, rs)
    ok &= check_clear("buck vs KL720", buck, kl)
    ok &= check_clear("buck vs RS485", buck, rs)
    ok &= check_clear("jack body vs buck", jack_body, buck)
    log("ALL CLEAR" if ok else "SOME CLASHES - see above")

    # ---------- export ----------
    doc = App.newDocument("PiBox")
    sheet = doc.addObject("Spreadsheet::Sheet", "params")
    for i, (k, v) in enumerate(P.items(), start=1):
        sheet.set("A%d" % i, k)
        sheet.set("B%d" % i, str(v))
        sheet.setAlias("B%d" % i, "p_" + k)
    doc.recompute()

    parts = {"pi_box_shell": shell, "pi_box_lid": lid}
    for name, shp in parts.items():
        o = doc.addObject("Part::Feature", name)
        o.Shape = shp
        shp.exportStep(os.path.join(OUT, name + ".step"))
        m = MeshPart.meshFromShape(Shape=shp, LinearDeflection=0.05, AngularDeflection=0.2)
        m.write(os.path.join(OUT, name + ".stl"))
        log("exported %s bbox=%s" % (name, shp.BoundBox))
    doc.saveAs(os.path.join(OUT, "pi_box.FCStd"))
    log("DONE")
except Exception:
    log("ERROR")
    log(traceback.format_exc())

with open(REPORT, "w") as f:
    f.write("\n".join(lines) + "\n")

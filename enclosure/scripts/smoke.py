import FreeCAD as App, Part
out = r"C:\Users\azamk\Documents\Door-Lock-with-Rasp-InteJer\enclosure\scripts\smoke_result.txt"
try:
    s = Part.makeBox(10, 10, 10)
    with open(out, "w") as f:
        f.write("OK volume=%s valid=%s version=%s\n" % (s.Volume, s.isValid(), ".".join(App.Version()[:3])))
except Exception as e:
    with open(out, "w") as f:
        f.write("ERR %r\n" % e)

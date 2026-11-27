"""Replace Capacitor's default iPhone app icon with the Story Factory icon (run after `cap add ios`).
iOS wants a square, opaque picture and rounds the corners itself, so the full-bleed maskable icon is used."""
import sys
from pathlib import Path
from PIL import Image

folder = Path(sys.argv[1])                       # .../ios/App/App/Assets.xcassets/AppIcon.appiconset
src = Image.open(sys.argv[2]).convert("RGB")     # frontend/icons/maskable-512.png
pngs = sorted(folder.glob("*.png"))
if not pngs:
    sys.exit("no icon slots found in " + str(folder))
for f in pngs:
    size = Image.open(f).size
    src.resize(size, Image.LANCZOS).save(f)
    print("icon written:", f.name, size)

"""Replace Capacitor's default launcher icons with the Story Factory icon (run after `cap add android`)."""
import shutil, sys
from pathlib import Path
from PIL import Image

res = Path(sys.argv[1])                        # .../android/app/src/main/res
src = Image.open(sys.argv[2]).convert("RGBA")  # frontend/icons/icon-512.png
for folder, px in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
    d = res / f"mipmap-{folder}"
    d.mkdir(parents=True, exist_ok=True)
    img = src.resize((px, px), Image.LANCZOS)
    img.save(d / "ic_launcher.png")
    img.save(d / "ic_launcher_round.png")
    for extra in d.glob("ic_launcher_foreground.png"):
        extra.unlink()
shutil.rmtree(res / "mipmap-anydpi-v26", ignore_errors=True)   # use the plain PNG icons everywhere
print("icons replaced")

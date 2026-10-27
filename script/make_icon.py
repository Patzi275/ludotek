"""Generate the icons from assets/logo.png. Dev only: needs Pillow (pip install pillow).

Run from the repo root after changing the logo:  python script/make_icon.py

The logo is pixel art on a square grid of blocks, so every output is scaled by an
integer factor with nearest-neighbour: edges stay crisp, nothing is resampled.
Outputs:
  assets/ludotek.ico        exe icon (16 to 256 px), logo on a white rounded tile
  assets/logo-dark.png      white version of the logo, for dark backgrounds (README)
  ludotek/web/favicon.png   64 px tile, browser tab icon (web/ is bundled in the exe)
"""
import io
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "logo.png"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)  # all divisible by 8: logo = 6/8 of the tile
TILE = (255, 255, 255, 255)
HAIRLINE = (0xDD, 0xE0, 0xE6, 255)  # --dp-color-rule, keeps the white tile visible on white


def grid_blocks(img):
    """Number of blocks per side, or exit with a message if the logo is not a clean grid."""
    w, h = img.size
    px = img.load()
    edges = {x for x in range(1, w) for y in range(h) if px[x, y] != px[x - 1, y]}
    edges |= {y for y in range(1, h) for x in range(w) if px[x, y] != px[x, y - 1]}
    block = w
    for e in edges:
        while e % block:
            block -= 1
    if w != h or w % block:
        sys.exit(f"{LOGO} must be a square pixel-art grid (got {w}x{h}, block {block}).")
    return w // block


def scaled_logo(img, blocks, block_px):
    """The logo reduced to one pixel per block, then enlarged by an integer factor."""
    small = img.resize((blocks, blocks), Image.NEAREST)
    return small.resize((blocks * block_px, blocks * block_px), Image.NEAREST)


def tile(img, blocks, size):
    """Logo centred on a white rounded square of `size` px, margin = size/8."""
    if size % 8 or (size * 3 // 4) % blocks:
        sys.exit(f"Size {size} cannot hold a {blocks}-block logo without resampling.")
    big = size * 4  # draw the rounded corners at 4x, then downsample for smooth edges
    base = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    # Corner radius = margin: the rounding stays inside the margin and never touches the logo.
    ImageDraw.Draw(base).rounded_rectangle((0, 0, big - 1, big - 1), radius=big // 8,
                                           fill=TILE, outline=HAIRLINE, width=4)
    out = base.resize((size, size), Image.LANCZOS)
    logo = scaled_logo(img, blocks, size * 3 // 4 // blocks)
    out.alpha_composite(logo, (size // 8, size // 8))
    return out


def png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def write_ico(path, frames):
    """ICO with PNG frames (Windows Vista+). Written by hand so no frame gets resampled."""
    pngs = [png_bytes(f) for f in frames]
    header = struct.pack("<HHH", 0, 1, len(pngs))  # reserved, type 1 = icon, count
    offset = 6 + 16 * len(pngs)
    entries = b""
    for frame, data in zip(frames, pngs):
        w = frame.width if frame.width < 256 else 0  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(header + entries + b"".join(pngs))


def main():
    img = Image.open(LOGO).convert("RGBA")
    blocks = grid_blocks(img)

    write_ico(ROOT / "assets" / "ludotek.ico", [tile(img, blocks, s) for s in ICO_SIZES])

    dark = Image.new("RGBA", img.size)
    dark.putdata([(255 - r, 255 - g, 255 - b, a) for r, g, b, a in img.getdata()])
    dark.save(ROOT / "assets" / "logo-dark.png", optimize=True)

    tile(img, blocks, 64).save(ROOT / "ludotek" / "web" / "favicon.png", optimize=True)
    print(f"Logo: {blocks}x{blocks} blocks. Wrote ludotek.ico ({', '.join(map(str, ICO_SIZES))}), "
          "logo-dark.png, favicon.png.")


if __name__ == "__main__":
    main()

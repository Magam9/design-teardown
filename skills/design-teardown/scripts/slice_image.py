#!/usr/bin/env python3
"""Slice a UI screenshot into per-component crops and measure their styling.

Subcommands:
  probe     <image>                 dimensions, aspect, device class, DPR guess
  crop      <regions.json>          per-region crops with padding + upscaling
  colors    <regions.json>          dominant palette + probes per region
  contrast  <fg> <bg>               WCAG contrast ratio

regions.json format:
  {
    "image": "shot.png",
    "dpr": 2,
    "regions": [
      {"id": "nav-cta", "name": "primary-button", "box": [1256, 20, 1400, 52],
       "kind": "component", "upscale": 4}
    ]
  }

box is [x0, y0, x1, y1]. Values <= 1.0 across the whole box are treated as
normalized fractions of the image. "upscale" is optional; a sensible factor is
chosen from region size when omitted.
"""

import argparse
import json
import os
import re
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required.  pip install pillow --break-system-packages")

Image.MAX_IMAGE_PIXELS = None

# Long edge -> (device class, likely DPR). Checked in order.
DEVICE_CLASSES = [
    (500, "small mobile", 1),
    (1000, "mobile", 2),
    (1400, "mobile @3x or small tablet", 3),
    (1700, "laptop @1x or tablet portrait", 1),
    (2200, "desktop", 1),
    (3200, "desktop @2x", 2),
]

# Long edges that are overwhelmingly likely to be a real viewport rather than an
# exported artboard. Used only to decide how loudly to caveat the DPR guess.
COMMON_DEVICE_EDGES = {
    640, 667, 736, 812, 844, 896, 926, 1024, 1080, 1112, 1136, 1194, 1280,
    1366, 1440, 1512, 1536, 1600, 1728, 1792, 1920, 2048, 2160, 2560, 2880,
    3024, 3072, 3456, 3840,
}


# ---------------------------------------------------------------- helpers


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", str(text).lower()).strip()
    return re.sub(r"[-\s]+", "-", text) or "region"


def to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def load_spec(path):
    with open(path) as fh:
        spec = json.load(fh)
    if "regions" not in spec:
        sys.exit(f"{path}: missing 'regions' array")
    img_path = spec.get("image")
    if not img_path:
        sys.exit(f"{path}: missing 'image'")
    if not os.path.isabs(img_path):
        candidate = os.path.join(os.path.dirname(os.path.abspath(path)), img_path)
        if os.path.exists(candidate):
            img_path = candidate
    if not os.path.exists(img_path):
        sys.exit(f"image not found: {img_path}")
    return spec, img_path


def resolve_box(box, width, height):
    """Return an integer pixel box, clamped to the image, from pixel or normalized input."""
    if len(box) != 4:
        raise ValueError(f"box needs 4 values, got {len(box)}: {box}")
    x0, y0, x1, y1 = box
    if all(isinstance(v, (int, float)) and 0.0 <= v <= 1.0 for v in box):
        x0, x1 = x0 * width, x1 * width
        y0, y1 = y0 * height, y1 * height
    x0, x1 = sorted((int(round(x0)), int(round(x1))))
    y0, y1 = sorted((int(round(y0)), int(round(y1))))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(width, x1), min(height, y1)
    if x1 - x0 < 1 or y1 - y0 < 1:
        raise ValueError(f"box collapsed to nothing after clamping: {box}")
    return x0, y0, x1, y1


# Beyond this, a crop wastes vision-context budget without adding legibility.
MAX_OUTPUT_EDGE = 1600


def auto_upscale(w, h):
    """Small regions need magnifying before radius/border/shadow detail is legible."""
    short = min(w, h)
    if short < 24:
        factor = 6
    elif short < 48:
        factor = 4
    elif short < 120:
        factor = 3
    elif short < 300:
        factor = 2
    else:
        factor = 1
    # A wide thin strip (a navbar) is "small" by short edge but already huge by
    # long edge — scaling it 3x just burns tokens. Clamp on the long edge.
    long_edge = max(w, h)
    while factor > 1 and long_edge * factor > MAX_OUTPUT_EDGE:
        factor -= 1
    return factor


# ---------------------------------------------------------------- probe


def cmd_probe(args):
    with Image.open(args.image) as im:
        w, h = im.size
        mode, fmt = im.mode, im.format
    long_edge = max(w, h)
    device, dpr = "very large / stitched capture", 2
    for limit, name, guess in DEVICE_CLASSES:
        if long_edge <= limit:
            device, dpr = name, guess
            break

    print(f"file          {args.image}")
    print(f"size          {w} x {h} px  ({mode}, {fmt})")
    print(f"aspect        {w / h:.3f}")
    print(f"device class  {device}")
    print(f"dpr guess     {dpr}x   -> divide measured px by {dpr} for CSS units")
    if h > w * 2.5:
        print("note          tall capture; likely a full-page scroll — slice by section first")
    if w > h * 3:
        print("note          very wide; possibly multiple screens side by side")

    # The device class above is inferred from dimensions alone, which is only
    # meaningful for an actual viewport capture. Exported artboards and
    # presentation mockups land on round numbers no device ever produces, and
    # for those the DPR guess carries no information at all.
    artboard = (
        long_edge not in COMMON_DEVICE_EDGES
        and w % 100 == 0 and h % 100 == 0
    )
    if artboard:
        print("note          round dimensions and no matching device width — this looks like an")
        print("              exported artboard or presentation mockup, not a viewport capture.")
        print("              The DPR guess above is not evidence. Confirm it from a measured cap")
        print("              height (body text below ~10px means the export is @2x) before")
        print("              dividing anything.")
    print()
    print("Logical (CSS) size if the DPR guess holds: "
          f"{round(w / dpr)} x {round(h / dpr)}")


# ---------------------------------------------------------------- crop


def cmd_crop(args):
    spec, img_path = load_spec(args.regions)
    os.makedirs(args.outdir, exist_ok=True)

    with Image.open(img_path) as im:
        im = im.convert("RGBA") if im.mode in ("P", "LA") else im
        W, H = im.size
        entries = []

        for region in spec["regions"]:
            rid = region.get("id") or slugify(region.get("name", "region"))
            name = region.get("name", rid)
            try:
                x0, y0, x1, y1 = resolve_box(region["box"], W, H)
            except (ValueError, KeyError) as exc:
                print(f"  skip {rid}: {exc}", file=sys.stderr)
                continue

            pad = region.get("context", args.context)
            px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
            px1, py1 = min(W, x1 + pad), min(H, y1 + pad)

            crop = im.crop((px0, py0, px1, py1))
            cw, ch = crop.size
            factor = region.get("upscale") or auto_upscale(x1 - x0, y1 - y0)
            factor = max(1, min(int(factor), args.max_upscale))
            if factor > 1:
                # NEAREST keeps edges crisp so radius and 1px borders stay countable.
                crop = crop.resize((cw * factor, ch * factor), Image.NEAREST)

            fname = f"{slugify(rid)}__{slugify(name)}.png"
            out = os.path.join(args.outdir, fname)
            crop.save(out)

            entries.append({
                "id": rid,
                "name": name,
                "kind": region.get("kind", "component"),
                "file": fname,
                "source_box": [x0, y0, x1, y1],
                "source_size": [x1 - x0, y1 - y0],
                "context_padding": pad,
                "upscale": factor,
                "output_size": list(crop.size),
            })
            print(f"  {fname}  ({x1-x0}x{y1-y0} @ {factor}x -> {crop.size[0]}x{crop.size[1]})")

    manifest = {
        "image": os.path.basename(img_path),
        "image_size": [W, H],
        "dpr": spec.get("dpr"),
        "crops": entries,
    }
    mpath = os.path.join(args.outdir, "manifest.json")
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\n{len(entries)} crops + manifest -> {args.outdir}")


# ---------------------------------------------------------------- colors


# Two corner samples this close are the same fill with dithering noise on top.
CORNER_TOLERANCE = 6


def region_palette(im, box, top):
    crop = im.crop(box).convert("RGB")
    w, h = crop.size
    total = w * h
    # Quantize first: raw getcolors() on a photo-ish region returns thousands of
    # near-duplicate values from anti-aliasing, which buries the real fills.
    quant = crop.quantize(colors=min(64, max(2, total)), method=Image.MEDIANCUT)
    pal = quant.getpalette()
    counts = sorted(quant.getcolors() or [], key=lambda c: -c[0])

    merged = {}
    for count, idx in counts:
        rgb = tuple(pal[idx * 3: idx * 3 + 3])
        key = tuple(v // 8 for v in rgb)  # merge values within ~8/255
        if key in merged:
            merged[key][0] += count
        else:
            merged[key] = [count, rgb]

    out = []
    for count, rgb in sorted(merged.values(), key=lambda v: -v[0])[:top]:
        out.append({"hex": to_hex(rgb), "rgb": list(rgb), "coverage_pct": round(100 * count / total, 1)})

    inset = min(3, max(1, min(w, h) // 8))
    raw = {
        "top_left": crop.getpixel((inset, inset)),
        "top_right": crop.getpixel((w - 1 - inset, inset)),
        "bottom_left": crop.getpixel((inset, h - 1 - inset)),
        "bottom_right": crop.getpixel((w - 1 - inset, h - 1 - inset)),
        "center": crop.getpixel((w // 2, h // 2)),
    }
    probes = {k: to_hex(v) for k, v in raw.items()}

    # Corners are single pixels, so PNG dithering and a soft edge routinely make
    # two samples of the same flat fill differ by a value or two. Comparing the
    # hex strings exactly reported a "gradient" on most flat surfaces, which is
    # worse than saying nothing. Group with a tolerance instead.
    tl, tr, bl, br = (raw[k] for k in ("top_left", "top_right", "bottom_left", "bottom_right"))
    same = lambda a, b: max(abs(x - y) for x, y in zip(a, b)) <= CORNER_TOLERANCE

    # If no corner probe is anywhere near the region's dominant colour, all four
    # landed outside the component — a large corner radius put them on the page
    # behind. Any gradient read off them describes the page, not the fill, and a
    # shadow under one edge is enough to make that page look like a gradient.
    dominant = tuple(out[0]["rgb"]) if out else None
    if dominant is not None and not any(same(c, dominant) for c in (tl, tr, bl, br)):
        hint = ("no corner probe matches the dominant fill -> all four are off the component,"
                " caught by its corner radius. Re-sample with a tighter box; use `geometry`"
                " for the shape itself.")
    elif same(tl, tr) and same(tl, bl) and same(tl, br):
        hint = "corners match -> flat fill (or the component is inset from its box)"
    elif same(tl, tr) and same(bl, br):
        hint = "top pair differs from bottom pair -> likely a vertical gradient"
    elif same(tl, bl) and same(tr, br):
        hint = "left pair differs from right pair -> likely a horizontal gradient"
    elif same(tl, br) and same(tr, bl):
        hint = "diagonal pairs match -> likely a diagonal gradient"
    else:
        hint = "all corners differ -> rounded corners showing page behind, or a complex fill"

    return out, probes, hint


def cmd_colors(args):
    spec, img_path = load_spec(args.regions)
    with Image.open(img_path) as im:
        im = im.convert("RGB")
        W, H = im.size
        for region in spec["regions"]:
            rid = region.get("id") or slugify(region.get("name", "region"))
            try:
                box = resolve_box(region["box"], W, H)
            except (ValueError, KeyError) as exc:
                print(f"{rid}: skip ({exc})\n")
                continue
            palette, probes, hint = region_palette(im, box, args.top)

            print(f"=== {rid}  ({region.get('name', '')})  {box}")
            for c in palette:
                bar = "#" * max(1, int(c["coverage_pct"] / 4))
                print(f"    {c['hex']}  {c['coverage_pct']:5.1f}%  {bar}")
            print("    probes: " + "  ".join(f"{k}={v}" for k, v in probes.items()))
            print(f"    {hint}")
            print()


# ---------------------------------------------------------------- contrast


def luminance(rgb):
    def channel(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def parse_hex(value):
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        sys.exit(f"bad hex color: {value}")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def cmd_contrast(args):
    fg, bg = parse_hex(args.fg), parse_hex(args.bg)
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    ratio = (l1 + 0.05) / (l2 + 0.05)
    print(f"{to_hex(fg)} on {to_hex(bg)}   ratio {ratio:.2f}:1")
    checks = [
        ("AA  normal text (4.5)", ratio >= 4.5),
        ("AA  large text  (3.0)", ratio >= 3.0),
        ("AAA normal text (7.0)", ratio >= 7.0),
        ("AA  UI / borders(3.0)", ratio >= 3.0),
    ]
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")


# ---------------------------------------------------------------- cli


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probe", help="image dimensions, device class, DPR guess")
    sp.add_argument("image")
    sp.set_defaults(func=cmd_probe)

    sc = sub.add_parser("crop", help="write per-region crops")
    sc.add_argument("regions")
    sc.add_argument("--outdir", default="crops")
    sc.add_argument("--context", type=int, default=0,
                    help="pixels of surrounding context to include (default 0)")
    sc.add_argument("--max-upscale", type=int, default=8)
    sc.set_defaults(func=cmd_crop)

    sl = sub.add_parser("colors", help="dominant palette and probes per region")
    sl.add_argument("regions")
    sl.add_argument("--top", type=int, default=6)
    sl.set_defaults(func=cmd_colors)

    st = sub.add_parser("contrast", help="WCAG contrast ratio between two colors")
    st.add_argument("fg")
    st.add_argument("bg")
    st.set_defaults(func=cmd_contrast)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

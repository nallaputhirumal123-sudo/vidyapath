"""Craxle launch banners for LinkedIn and Instagram.

Same palette and mark as the site, so a post and the landing page read as one
brand. Drawn at 2x and downsampled — text at these sizes shows every jagged
edge otherwise.
"""
import math, os
from PIL import Image, ImageDraw, ImageFont

OUT = r"C:\Users\nalla\vidyapath\banners"
os.makedirs(OUT, exist_ok=True)
SS = 2

BG        = (10, 12, 16)          # --bg
PANEL     = (18, 22, 32)
SAFFRON   = (255, 179, 71)
SAFFRON_D = (221, 111, 24)
INK       = (238, 242, 248)       # --text
MUTED     = (147, 158, 176)
GREEN     = (75, 191, 130)

FONTS = r"C:\Windows\Fonts"


def font(size, bold=True):
    for n in (("seguibl.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)):
        p = os.path.join(FONTS, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def mark(d, cx, cy, R, colour):
    """The Craxle C, same geometry as the logo."""
    thick = R * 0.40
    d.arc([cx - R, cy - R, cx + R, cy + R], start=52, end=308,
          fill=colour, width=int(round(thick)))
    Rc = R - thick / 2
    a, b = math.radians(52), math.radians(308)
    x0, y0 = cx + Rc * math.cos(a), cy - Rc * math.sin(a)
    x1, y1 = cx + Rc * 1.30, cy - Rc * 1.24
    d.line([x0, y0, x1, y1], fill=colour, width=int(round(thick)))
    for px, py in ((x0, y0), (x1, y1), (cx + Rc * math.cos(b), cy - Rc * math.sin(b))):
        d.ellipse([px - thick / 2, py - thick / 2, px + thick / 2, py + thick / 2],
                  fill=colour)


def glow(img):
    """The same warm wash the site puts behind the page."""
    w, h = img.size
    lay = Image.new("RGB", (w, h), BG)
    px = lay.load()
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            dx, dy = (x - w * 0.12) / (w * 0.8), (y + h * 0.1) / (h * 0.9)
            t = max(0.0, 1.0 - (dx * dx + dy * dy))
            c = (int(BG[0] + 26 * t), int(BG[1] + 18 * t), int(BG[2] + 6 * t))
            for yy in range(y, min(y + 3, h)):
                for xx in range(x, min(x + 3, w)):
                    px[xx, yy] = c
    return lay


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def gradient_text(img, xy, text, f, c1=SAFFRON, c2=SAFFRON_D):
    """Saffron gradient on the headline, matching the site's h1."""
    d = ImageDraw.Draw(img)
    l, t, r, b = d.textbbox(xy, text, font=f)
    if r <= l:
        return
    grad = Image.new("RGB", (r - l, b - t))
    gp = grad.load()
    for x in range(r - l):
        k = x / max(r - l - 1, 1)
        gp_col = tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))
        for y in range(b - t):
            gp[x, y] = gp_col
    mask = Image.new("L", (r - l, b - t), 0)
    ImageDraw.Draw(mask).text((xy[0] - l, xy[1] - t), text, font=f, fill=255)
    img.paste(grad, (l, t), mask)


def banner(w, h, headline, sub, bullets, tag, name):
    """Lay out one banner.

    Type is scaled off the SHORT edge, not the width. Scaling off width made
    the 1200x627 headline enormous, pushed the body off the canvas and ran the
    footer straight through the subhead. Everything is also fit-checked before
    it is drawn, so a long line shrinks rather than overflows.
    """
    W, H = w * SS, h * SS
    S = min(W, H)                       # the type scale
    img = glow(Image.new("RGB", (W, H), BG))
    d = ImageDraw.Draw(img)
    pad = int(S * 0.09)
    inner = W - pad * 2

    # brand, top left
    mr = int(S * 0.030)
    mark(d, pad + mr, pad + mr, mr, SAFFRON)
    fw = font(int(S * 0.046))
    d.text((pad + mr * 2.6, pad + mr - int(S * 0.030)), "Craxle", font=fw, fill=INK)

    # footer first: it owns the bottom, so the body can never run into it
    ft = font(int(S * 0.032))
    foot_y = H - pad - int(S * 0.032)
    d.text((pad, foot_y), tag, font=ft, fill=SAFFRON)

    top = pad + mr * 2 + int(S * 0.06)
    avail = foot_y - top - int(S * 0.05)

    # Pick the largest size at which EVERYTHING fits, bullets included. An
    # earlier version stopped at the first size where the headline and subhead
    # fitted, which passed immediately at the largest size and silently dropped
    # the bullets — leaving a third of the canvas empty.
    def measure(scale):
        fh = font(int(S * scale))
        fs = font(int(S * scale * 0.42), bold=False)
        fb = font(int(S * scale * 0.38))
        hl, sl = wrap(d, headline, fh, inner), wrap(d, sub, fs, inner)
        lh, ls, lb = (int(S * scale * 1.16), int(S * scale * 0.56),
                      int(S * scale * 0.62))
        body = len(hl) * lh + int(S * 0.025) + len(sl) * ls
        # Bullets wrap too. Counting them as one line each was why the longest
        # one ran off the right edge — it fitted the height budget and then
        # overflowed the width.
        ind = int(S * 0.008) * 3.6
        bl = [wrap(d, b, fb, inner - ind) for b in bullets]
        nlines = sum(len(x) for x in bl)
        full = body + int(S * 0.03) + nlines * lb if bullets else body
        return fh, fs, fb, hl, sl, lh, ls, lb, body, full, bl

    SCALES = (0.098, 0.088, 0.078, 0.068, 0.060, 0.052)
    chosen = None
    for scale in SCALES:                       # everything fits?
        m = measure(scale)
        if m[9] <= avail:
            chosen, show = m, bool(bullets)
            break
    if chosen is None:                         # fall back: drop the bullets
        for scale in SCALES:
            m = measure(scale)
            if m[8] <= avail:
                chosen, show = m, False
                break
        else:
            chosen, show = measure(SCALES[-1]), False
    fh, fs, fb, hl, sl, lh, ls, lb = chosen[:8]
    blines = chosen[10]

    y = top
    for ln in hl:
        gradient_text(img, (pad, y), ln, fh)
        y += lh
    y += int(S * 0.025)
    for ln in sl:
        d.text((pad, y), ln, font=fs, fill=MUTED)
        y += ls
    if show:
        y += int(S * 0.03)
        r = int(S * 0.008)
        for lines in blines:
            d.ellipse([pad, y + r * 1.4, pad + r * 2, y + r * 3.4], fill=GREEN)
            for i, ln in enumerate(lines):
                d.text((pad + r * 3.6, y), ln, font=fb, fill=INK)
                y += lb

    img = img.resize((w, h), Image.LANCZOS)
    img.save(os.path.join(OUT, name), quality=95)
    return name


HEAD = "Stop applying into the void."
SUB = ("Craxle reads your resume, scores it against every live job, and tells "
       "you exactly which skills you are missing.")
BULLETS = ["Real postings, straight from company career pages",
           "A match score you can actually see the reasons for",
           "Employers can find you — anonymously, until you say yes"]
TAG = "craxle.com  ·  Get cracked by Craxle"

made = [
    banner(1200, 627, HEAD, SUB, BULLETS, TAG, "linkedin-1200x627.png"),
    banner(1080, 1080, HEAD, SUB, BULLETS, TAG, "instagram-1080x1080.png"),
    banner(1080, 1350, HEAD, SUB, BULLETS, TAG, "instagram-portrait-1080x1350.png"),
    banner(1080, 1920, "Get cracked by Craxle.",
           "Real jobs, matched to your resume. Not a keyword search.",
           ["Scored against every live posting",
            "See the skills you are missing",
            "Employers come to you"],
           TAG, "instagram-story-1080x1920.png"),
]
print("wrote: " + ", ".join(made))

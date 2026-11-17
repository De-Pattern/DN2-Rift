"""RIFT start-up animation, take 2 (owner, 2026-11-17): PS2-style 3D at the Digitone's 128 x 64, one
bit. The camera sweeps around three endoskeleton robots drumming (two hand drums, a steel pan)
around a campfire, then tilts up to the stars; the fire's smoke rises and spells RIFT.

A small software renderer: flat-shaded triangles with a z-buffer, lit by the flickering fire,
ordered (Bayer) dither to one bit, and a one-pixel outline where objects meet, for the Elektron look."""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 128, 64
R = random.Random(11)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16.0
DITHER = np.tile(BAYER, (H // 4, W // 4))


# -- geometry ---------------------------------------------------------------------------------
def box(cx, cy, cz, sx, sy, sz):
    """a box's 12 triangles (centre, half sizes)"""
    v = [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for a, b, c, d in q:
        out += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return out


def cyl(cx, cy, cz, r, h, n=10):
    out = []
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0 = (cx + r * math.cos(a0), cz + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), cz + r * math.sin(a1))
        b0, b1 = (p0[0], cy, p0[1]), (p1[0], cy, p1[1])
        t0, t1 = (p0[0], cy + h, p0[1]), (p1[0], cy + h, p1[1])
        out += [(b0, b1, t1), (b0, t1, t0), ((cx, cy + h, cz), t0, t1)]
    return out


def rot_y(tris, a, ox, oz):
    c, s = math.cos(a), math.sin(a)
    out = []
    for t in tris:
        out.append(tuple((ox + x * c - z * s, y, oz + x * s + z * c) for x, y, z in t))
    return out


def limb(p0, p1, w):
    """a thin box from p0 to p1 (a bone)"""
    p0, p1 = np.array(p0), np.array(p1)
    d = p1 - p0
    L = np.linalg.norm(d) + 1e-9
    f = d / L
    up = np.array([0, 0, 1.0]) if abs(f[2]) < 0.9 else np.array([1.0, 0, 0])
    s = np.cross(f, up); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    corners = []
    for a in (0, 1):
        for b in (-1, 1):
            for c in (-1, 1):
                corners.append(p0 + d * a + s * b * w + u * c * w)
    v = corners
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    out = []
    for a_, b_, c_, d_ in q:
        out += [(tuple(v[a_]), tuple(v[b_]), tuple(v[c_])), (tuple(v[a_]), tuple(v[c_]), tuple(v[d_]))]
    return out


def robot(t, phase, kind):
    """an endoskeleton seated on a log, in local space facing -z (toward the fire), at the origin:
    bones and joints, an open ribcage, a skull with sockets, cheekbones and a jaw, fingers.
    Returns (triangles, eye points)."""
    tris = []
    lean = 0.08 * math.sin(phase * 2)
    # pelvis (two hip plates), spine of vertebrae with gaps
    for s in (-1, 1):
        tris += box(0.13 * s, 0.76, 0, 0.09, 0.06, 0.1)
    for k in range(6):
        tris += box(0, 0.86 + k * 0.075, 0.03 + lean * 0.05 * k, 0.04, 0.025, 0.04)
    # ribcage: open hoops of ribs (left and right bars and a front strip), a sternum
    for k in range(4):
        y = 1.18 + k * 0.08
        wdt = 0.2 - 0.02 * abs(k - 1.5)
        for s in (-1, 1):
            tris += limb((0.03 * s, y, 0.06 + lean * 0.3), (wdt * s, y - 0.02, -0.02 + lean * 0.3), 0.014)
            tris += limb((wdt * s, y - 0.02, -0.02 + lean * 0.3), (0.06 * s, y - 0.04, -0.14 + lean * 0.3), 0.014)
    tris += box(0, 1.27, -0.15 + lean * 0.3, 0.02, 0.13, 0.015)
    # clavicles and shoulder balls
    for s in (-1, 1):
        tris += limb((0.02 * s, 1.5, -0.04), (0.3 * s, 1.52, 0), 0.02)
        tris += box(0.33 * s, 1.5, 0, 0.045, 0.045, 0.045)
    # neck, skull: cranium, brow, cheekbones, jaw apart from it; the eyes in the sockets
    tris += limb((0, 1.52, 0), (0, 1.62, -0.02 + lean), 0.025)
    tris += box(0, 1.79, 0.0 + lean, 0.11, 0.09, 0.12)
    tris += box(0, 1.72, -0.11 + lean, 0.11, 0.015, 0.02)
    for s in (-1, 1):
        tris += box(0.085 * s, 1.67, -0.08 + lean, 0.03, 0.025, 0.05)
    tris += box(0, 1.6 - 0.02 * abs(math.sin(phase * 3)), -0.07 + lean, 0.075, 0.022, 0.07)
    eyes = [(-0.05, 1.7, -0.14 + lean), (0.05, 1.7, -0.14 + lean)]
    # legs, seated: thigh, knee joint, shin, ankle, foot
    for s in (-1, 1):
        kn = (0.15 * s, 0.7, -0.45)
        tris += limb((0.13 * s, 0.74, 0), kn, 0.03)
        tris += box(kn[0], kn[1], kn[2], 0.045, 0.045, 0.045)
        tris += limb(kn, (0.17 * s, 0.07, -0.5), 0.026)
        tris += box(0.17 * s, 0.04, -0.6, 0.05, 0.025, 0.1)
    # arms: upper arm, elbow joint, forearm (two bones), wrist, three fingers; strike the drum
    for s in (-1, 1):
        hit = 0.5 + 0.5 * math.sin(phase * 2 * math.pi + (0 if s < 0 else math.pi))
        sh = (0.33 * s, 1.48, 0)
        hand = (0.16 * s, 0.98 + 0.32 * hit, -0.7 + 0.08 * hit)
        el = ((sh[0] + hand[0]) / 2 + 0.13 * s, (sh[1] + hand[1]) / 2 - 0.05, -0.32)
        tris += limb(sh, el, 0.026)
        tris += box(el[0], el[1], el[2], 0.035, 0.035, 0.035)
        for o in (-0.02, 0.02):
            tris += limb((el[0] + o, el[1], el[2]), (hand[0] + o, hand[1] + 0.02, hand[2] + 0.06), 0.012)
        tris += box(hand[0], hand[1] + 0.02, hand[2] + 0.04, 0.035, 0.02, 0.03)
        for f in (-1, 0, 1):
            tris += limb((hand[0] + 0.022 * f, hand[1] + 0.01, hand[2]),
                         (hand[0] + 0.03 * f, hand[1] - 0.03, hand[2] - 0.08), 0.008)
    # the drum: two hand drums (djembe) or a steel pan on a stand
    if kind == "pan":
        tris += cyl(0, 0.92, -0.75, 0.32, 0.08, 12)
        tris += limb((0, 0.1, -0.75), (0, 0.92, -0.75), 0.03)
    else:
        tris += cyl(0, 0.45, -0.75, 0.16, 0.5, 9)
        tris += cyl(0, 0.05, -0.75, 0.09, 0.4, 7)
    # the log seat
    tris += limb((-0.45, 0.35, 0.05), (0.45, 0.35, 0.05), 0.16)
    return tris, eyes


# -- the camera and the raster ------------------------------------------------------------------
def look(eye, target):
    eye, target = np.array(eye, float), np.array(target, float)
    f = target - eye; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1.0, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return eye, r, u, f


def project(cam, p, fov=1.1):
    eye, r, u, f = cam
    d = np.asarray(p, float) - eye
    z = d @ f
    if z < 0.05:
        return None
    k = (H / 2) / math.tan(fov / 2)
    return (W / 2 + (d @ r) / z * k, H / 2 - (d @ u) / z * k, z)


def raster(tris, cam, light, flick, shade_k=1.0, ids=None):
    """intensity (0..1), depth, object id; flat-shaded by the fire's point light"""
    I = np.zeros((H, W)); Z = np.full((H, W), np.inf); O = np.zeros((H, W), int)
    for n, (t, oid) in enumerate(tris):
        pts = [project(cam, v) for v in t]
        if any(p is None for p in pts):
            continue
        a, b, c = (np.array(t[0]), np.array(t[1]), np.array(t[2]))
        nrm = np.cross(b - a, c - a)
        ln = np.linalg.norm(nrm)
        if ln < 1e-12:
            continue
        nrm /= ln
        cen = (a + b + c) / 3
        to_eye = cam[0] - cen
        if nrm @ to_eye < 0:                      # back face
            nrm = -nrm
        to_l = light - cen
        dist = np.linalg.norm(to_l)
        lam = max(0.0, nrm @ (to_l / dist))
        val = shade_k * (0.05 + 1.6 * lam * flick / (0.3 + 0.12 * dist * dist))
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        x0, x1 = max(0, int(min(xs))), min(W - 1, int(max(xs)) + 1)
        y0, y1 = max(0, int(min(ys))), min(H - 1, int(max(ys)) + 1)
        if x0 > x1 or y0 > y1:
            continue
        (ax, ay, az), (bx, by, bz), (cx_, cy_, cz) = pts
        den = (by - cy_) * (ax - cx_) + (cx_ - bx) * (ay - cy_)
        if abs(den) < 1e-9:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((by - cy_) * (gx - cx_) + (cx_ - bx) * (gy - cy_)) / den
        w1 = ((cy_ - ay) * (gx - cx_) + (ax - cx_) * (gy - cy_)) / den
        w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any():
            continue
        z = w0 * az + w1 * bz + w2 * cz
        sub = Z[y0:y1 + 1, x0:x1 + 1]
        win = m & (z < sub)
        sub[win] = z[win]
        I[y0:y1 + 1, x0:x1 + 1][win] = val
        O[y0:y1 + 1, x0:x1 + 1][win] = oid
    return I, Z, O


def dither(I):
    return (I > DITHER).astype(np.uint8)


def outline(img, O, Z):
    """a lit pixel where two objects meet (silhouettes), the Elektron line"""
    e = np.zeros_like(img)
    e[:, 1:] |= (O[:, 1:] != O[:, :-1])
    e[1:, :] |= (O[1:, :] != O[:-1, :])
    e &= (np.minimum(Z, np.roll(Z, 1, 1)) < 50)
    return img | e.astype(np.uint8)


# -- the scene -------------------------------------------------------------------------------
SEATS = [(math.radians(a), k) for a, k in ((90, "drum"), (210, "pan"), (330, "drum"))]
RAD = 1.9
STARS = [(R.uniform(0, 2 * math.pi), R.uniform(0.15, 1.45), R.random()) for _ in range(140)]


def logo_targets():
    """RIFT as points in the sky (screen space when the camera looks up), from a blocky font"""
    im = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(im)
    y0, h = 14, 16
    d.rectangle((16, y0, 33, y0 + 4), fill=1); d.rectangle((16, y0, 21, y0 + h), fill=1)
    d.rectangle((28, y0, 33, y0 + 8), fill=1); d.rectangle((16, y0 + 7, 32, y0 + 10), fill=1)
    d.polygon([(23, y0 + 10), (29, y0 + 10), (35, y0 + h), (29, y0 + h)], fill=1)
    d.rectangle((41, y0, 60, y0 + 4), fill=1); d.rectangle((48, y0, 53, y0 + h), fill=1); d.rectangle((41, y0 + h - 4, 60, y0 + h), fill=1)
    d.rectangle((67, y0, 87, y0 + 4), fill=1); d.rectangle((67, y0, 72, y0 + h), fill=1); d.rectangle((67, y0 + 7, 84, y0 + 10), fill=1)
    d.rectangle((92, y0, 115, y0 + 4), fill=1); d.rectangle((101, y0, 106, y0 + h), fill=1)
    for (x, y, sx, sy) in ((7, 8, 1, 1), (120, 8, -1, 1), (7, 37, 1, -1), (120, 37, -1, -1)):
        d.line((x, y, x + 4 * sx, y), fill=1); d.line((x, y, x, y + 4 * sy), fill=1)
    pts = [(18, 42), (26, 42), (26, 40), (36, 40), (36, 43), (46, 43), (46, 45), (54, 45), (54, 42), (64, 42),
           (64, 40), (72, 40), (72, 43), (82, 43), (82, 45), (90, 45), (90, 42), (102, 42)]
    d.line(pts, fill=1)
    a = np.array(im)
    return [(x, y) for y in range(H) for x in range(W) if a[y, x]], a


LOGO_PTS, LOGO = logo_targets()

# smoke particles: born at the fire, rising, swirling
smoke = []


def frame(t, n_total):
    """t in 0..1 over the animation"""
    flick = 0.85 + 0.15 * math.sin(t * 90) * math.sin(t * 37 + 1) + 0.05 * R.random()
    # camera: orbit 0..0.62, then tilt to the sky
    orbit = math.radians(200 + 150 * min(t / 0.62, 1.0) ** 0.9)
    cam_r, cam_h = 3.8 - 0.5 * min(t / 0.62, 1), 1.5
    eye = (cam_r * math.cos(orbit), cam_h, cam_r * math.sin(orbit))
    tilt = 0.0 if t < 0.55 else min(1.0, (t - 0.55) / 0.25)
    tilt = tilt * tilt * (3 - 2 * tilt)
    target = (0, 0.95 + 9.0 * tilt, 0)
    cam = look(eye, target)
    light = np.array([0, 0.6, 0])
    tris = []
    eyes = []
    for k, (a, kind) in enumerate(SEATS):
        rt, ey = robot(t, t * 9.0 + k * 0.33, kind)
        ang = -a + math.pi / 2
        tris += [(tr, k + 1) for tr in rot_y(rt, ang, RAD * math.cos(a), RAD * math.sin(a))]
        eyes += [rot_y([(e,)], ang, RAD * math.cos(a), RAD * math.sin(a))[0][0] for e in ey]
    # the fire's stones
    for k in range(8):
        a = 2 * math.pi * k / 8
        tris += [(tr, 10) for tr in box(0.6 * math.cos(a), 0.06, 0.6 * math.sin(a), 0.12, 0.07, 0.1)]
    I, Z, O = raster(tris, cam, light, flick)
    # the ground: lit by the fire, falling off (a disc of dither under everything)
    eye_, r_, u_, f_ = cam
    k = (H / 2) / math.tan(1.1 / 2)
    gy, gx = np.mgrid[0:H, 0:W] + 0.5
    dirs = f_[None, None, :] + ((gx - W / 2) / k)[..., None] * r_ + (-(gy - H / 2) / k)[..., None] * u_
    tg = -eye_[1] / np.where(dirs[..., 1] < -1e-6, dirs[..., 1], -1e-6)
    hit = (dirs[..., 1] < -1e-6) & (tg < Z / np.maximum(1e-6, (dirs @ f_)))
    px = eye_[0] + dirs[..., 0] * tg; pz = eye_[2] + dirs[..., 2] * tg
    dist = np.sqrt(px * px + pz * pz)
    gl = np.where(hit, 0.42 * flick / (0.5 + 0.35 * dist * dist) - 0.06, 0)
    I = np.where(np.isinf(Z) & hit, gl, I)
    img = dither(np.clip(I, 0, 1))
    img = outline(img, np.where(np.isinf(Z), 0, O), np.where(np.isinf(Z), 99, Z))
    # stars (the sky shows as the camera tilts)
    for (az, el, tw) in STARS:
        p = project(cam, eye_ + 60 * np.array([math.cos(el) * math.cos(az), math.sin(el), math.cos(el) * math.sin(az)]))
        if p and 0 <= p[0] < W and 0 <= p[1] < H and math.isinf(Z[int(p[1]), int(p[0])]) and not hit[int(p[1]), int(p[0])]:
            if (tw + t * 3) % 1 > 0.15:
                img[int(p[1]), int(p[0])] = 1
    # the fire: flames as flickering bright tongues, projected
    for kk in range(26):
        s = R.random()
        a = R.uniform(0, 2 * math.pi)
        rr = 0.35 * R.random()
        hgt = 0.1 + 0.8 * R.random() ** 1.5 * flick
        p = project(cam, (rr * math.cos(a), hgt, rr * math.sin(a)))
        if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H and p[2] < Z[int(p[1]), int(p[0])] + 0.5:
            x, y = int(p[0]), int(p[1])
            img[max(0, y - 1):y + 1, x] = 1
    # the eyes: two lit pixels each, where seen
    for e in eyes:
        p = project(cam, e)
        if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H and p[2] <= Z[int(p[1]), int(p[0])] + 0.3:
            img[int(p[1]), int(p[0])] = 1
    # smoke: rises from the fire; at the end it gathers into the logo (screen space)
    for _ in range(6):
        smoke.append([R.uniform(-0.2, 0.2), 0.9, R.uniform(-0.2, 0.2), R.uniform(0, 6.28), None])
    gather = 0.0 if t < 0.72 else min(1.0, (t - 0.72) / 0.18)
    gather = gather * gather * (3 - 2 * gather)
    for i, s in enumerate(smoke):
        s[1] += 0.11
        s[0] += 0.03 * math.sin(s[1] * 1.7 + s[3]); s[2] += 0.03 * math.cos(s[1] * 1.3 + s[3])
        p = project(cam, (s[0] * (1 + s[1] * 0.12), s[1], s[2] * (1 + s[1] * 0.12)))
        if p is None:
            continue
        x, y = p[0], p[1]
        if gather > 0:
            if s[4] is None:
                s[4] = LOGO_PTS[(i * 7919) % len(LOGO_PTS)]
            x = x + (s[4][0] - x) * gather
            y = y + (s[4][1] - y) * gather
        if 0 <= int(x) < W and 0 <= int(y) < H and (gather > 0.6 or R.random() < 0.55):
            img[int(y), int(x)] = 1
    if gather > 0.85:                                         # the logo resolves, the smoke still drifting
        img = img | LOGO.astype(np.uint8) if gather >= 1.0 else img | (LOGO & (np.random.RandomState(int(t * 999)).rand(H, W) < (gather - 0.85) / 0.15)).astype(np.uint8)
    return img


def main():
    N = 80
    frames = []
    for i in range(N):
        frames.append(frame(i / (N - 1), N))
    frames[-1][55:, 93:] = 0                                # the version label's corner, clear (bootanim)
    durs = [70] * (N - 1) + [900]
    big = [Image.fromarray(f * 255).resize((W * 4, H * 4), Image.NEAREST) for f in frames]
    big[0].save("out/anim/rift_intro_3d.gif", save_all=True, append_images=big[1:], duration=durs, loop=0)
    for i in (10, 30, 45, 60, 70, 79):
        big[i].save(f"out/anim/g{i:02d}.png")
    print(N, "frames", sum(durs) / 1000, "s")


if __name__ == "__main__":
    main()

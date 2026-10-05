import cv2, numpy as np

def preprocess(path, stroke_frac=0.07, margin_frac=0.08, return_debug=False):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    # shrink big phone photos first (keeps things fast and stroke math stable)
    s = 1400 / max(img.shape)
    if s < 1: img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    # flat-field: remove shadows / uneven light by dividing by estimated paper brightness
    bg = cv2.morphologyEx(img, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    bg = cv2.GaussianBlur(bg, (0, 0), 25)
    flat = np.clip(img.astype(np.float32) / (bg.astype(np.float32) + 1e-3) * 255, 0, 255).astype(np.uint8)
    # ink is dark. ghost marks from pages underneath are faint, so use a strict threshold
    ink = (flat < 0.62 * 255).astype(np.uint8)
    # ignore the outer border (paper edge shadows) 
    b = int(0.05 * min(ink.shape)); ink[:b] = 0; ink[-b:] = 0; ink[:, :b] = 0; ink[:, -b:] = 0
    # keep the main letter: biggest ink blob + any blob close to it (dots, matra pieces). Printed logos far away are dropped.
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    main = 1 + int(np.argmax(areas))
    mx, my, mw, mh = stats[main, :4]
    reach = 0.25 * max(mw, mh)
    keep = np.zeros_like(ink)
    for i in range(1, n):
        x, y, w_, h_, a = stats[i]
        if a < 25: continue
        near = (x < mx + mw + reach) and (x + w_ > mx - reach) and (y < my + mh + reach) and (y + h_ > my - reach)
        if i == main or near: keep[lab == i] = 1
    ys, xs = np.where(keep > 0)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = keep[y0:y1 + 1, x0:x1 + 1] * 255
    h, w = crop.shape; side = max(h, w)
    # thicken thin pen strokes so they look like the dataset's thick strokes
    k = max(3, int(side * stroke_frac)) | 1
    thick = cv2.dilate(crop, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    m = int(side * margin_frac)
    sq = np.zeros((side + 2 * m, side + 2 * m), np.uint8)
    oy, ox = m + (side - h) // 2, m + (side - w) // 2
    sq[oy:oy + h, ox:ox + w] = thick
    final = cv2.resize(sq, (64, 64), interpolation=cv2.INTER_AREA)   # white char on black, 0..255
    if return_debug: return final, dict(flat=flat, ink=keep * 255, thick=sq)
    return final

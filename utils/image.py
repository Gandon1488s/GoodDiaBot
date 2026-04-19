import io
from PIL import Image


def process_avatar(raw: bytes) -> bytes:
    """Resize to 389x535, white background, JPEG."""
    src = Image.open(io.BytesIO(raw))
    if src.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", src.size, (255, 255, 255))
        if src.mode == "P":
            src = src.convert("RGBA")
        bg.paste(src, mask=src.split()[-1] if src.mode in ("RGBA", "LA") else None)
        img = bg
    else:
        img = src.convert("RGB")
    tw, th = 389, 535
    r = img.width / img.height
    if r > tw / th:
        new_h = th
        new_w = int(r * new_h)
    else:
        new_w = tw
        new_h = int(new_w / r)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    img = img.crop((left, top, left + tw, top + th))
    bg = Image.new("RGB", (tw, th), (255, 255, 255))
    bg.paste(img, (0, 0))
    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def process_signature(raw: bytes) -> bytes:
    """Resize to 341x170, remove white background → transparent PNG."""
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    tw, th = 341, 170
    r = img.width / img.height
    if r > tw / th:
        new_h = th
        new_w = int(r * new_h)
    else:
        new_w = tw
        new_h = int(new_w / r)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    img = img.crop((left, top, left + tw, top + th))
    data = []
    for px in img.getdata():
        r2, g, b, a = px
        data.append((255, 255, 255, 0) if r2 > 200 and g > 200 and b > 200 else px)
    img.putdata(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

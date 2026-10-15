#!/usr/bin/env python3
"""Generate fingerprinted WebP assets and update declared image references.

Requires Pillow>=10. Run from any directory: python3 scripts/optimize_images.py
Original images are preserved. Generated paths change when encoded bytes change.
"""
from hashlib import sha256
from html import escape
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re

from PIL import Image, ImageCms, ImageOps, features

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
OUTPUT = ASSETS / 'optimized'
WIDTHS = (480, 960, 1440)
SIZES = {
    'hero': '100vw',
    'about': '(min-width: 1168px) 588px, (min-width: 760px) calc((100vw - 48px) * 0.525), calc(100vw - 30px)',
    'unit': '(min-width: 1168px) 588px, (min-width: 760px) calc((100vw - 48px) * 0.525), calc(100vw - 30px)',
    'gallery': '(min-width: 1168px) 269px, (min-width: 1040px) calc((100vw - 48px) * 0.24), (min-width: 760px) calc((100vw - 48px) * 0.31), calc((100vw - 30px) * 0.88)',
    'hero-logo': '(min-width: 760px) 120px, 104px',
    'logo': '43px',
    'footer-logo': '48px',
}


def encode(image, width, fmt='WEBP'):
    height = round(image.height * width / image.width)
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    if fmt == 'WEBP':
        resized.save(buffer, format=fmt, quality=84, method=6)
    else:
        resized.save(buffer, format=fmt, optimize=True)
    return buffer.getvalue(), height


def make_variant(stem, image, width, fmt='WEBP'):
    content, height = encode(image, width, fmt)
    suffix = 'webp' if fmt == 'WEBP' else 'png'
    path = OUTPUT / f'{stem}-{width}-{sha256(content).hexdigest()[:12]}.{suffix}'
    path.write_bytes(content)
    return {'path': path.relative_to(ROOT).as_posix(), 'width': width,
            'height': height, 'bytes': len(content)}


def generate():
    if not features.check('webp'):
        raise RuntimeError('Pillow must support WebP encoding')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'format': 'webp', 'quality': 84, 'images': {}}
    for source in sorted(ASSETS.iterdir()):
        if source.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
            continue
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            profile = opened.info.get('icc_profile')
            if profile:
                # Convert embedded profiles to sRGB before dropping metadata.
                image = ImageCms.profileToProfile(image,
                    ImageCms.ImageCmsProfile(BytesIO(profile)),
                    ImageCms.createProfile('sRGB'), outputMode='RGB')
            else:
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
            if source.name == 'logo.png':
                # Up to 3x density for the 120px hero logo; keep small header files.
                widths = (96, 192, 384)
            else:
                widths = sorted({min(w, image.width) for w in WIDTHS})
            variants = [make_variant(source.stem, image, w) for w in widths]
            entry = {'source_bytes': source.stat().st_size,
                     'original_width': image.width, 'original_height': image.height,
                     'variants': variants, 'full': variants[-1]['path']}
            if source.name == 'logo.png':
                entry['favicon'] = make_variant('favicon', image, 64, 'PNG')
            manifest['images'][source.name] = entry
            print(f'{source.name}: {source.stat().st_size} -> {variants[-1]["bytes"]} bytes', flush=True)
    (ASSETS / 'image-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


class Attributes(HTMLParser):
    def __init__(self, tag):
        super().__init__(convert_charrefs=True)
        self.attrs = {}
        self.feed(tag)

    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)


def render(tag, attrs):
    values = ' '.join(key if value is None else f'{key}="{escape(str(value), quote=True)}"'
                      for key, value in attrs.items())
    return f'<{tag} {values}>'


def update_markup(manifest):
    entries = manifest['images']
    index = ROOT / 'index.html'
    text = index.read_text(encoding='utf-8')

    def image_tag(match):
        attrs = Attributes(match.group()).attrs
        original, role = attrs.get('data-image'), attrs.get('data-role')
        if not original:
            return match.group()
        entry = entries[original]
        variants = entry['variants']
        default = variants[-1] if role == 'hero' else next(
            (v for v in variants if v['width'] >= 960), variants[-1])
        if original == 'logo.png':
            default = next(v for v in variants if v['width'] >= 192) if role == 'hero-logo' else variants[0]
        attrs.update(src=default['path'],
                     srcset=', '.join(f'{v["path"]} {v["width"]}w' for v in variants),
                     sizes=SIZES[role], width=str(default['width']),
                     height=str(default['height']), decoding='async')
        return render('img', attrs)

    def shot_tag(match):
        attrs = Attributes(match.group()).attrs
        original = attrs.get('data-image')
        if original:
            attrs['data-full'] = entries[original]['full']
        return render('button', attrs)

    text = re.sub(r'<img\b[^>]*>', image_tag, text)
    text = re.sub(r'<button\b[^>]*data-full[^>]*>', shot_tag, text)
    favicon = entries['logo.png']['favicon']['path']
    text = re.sub(r'<link rel="icon"[^>]*>',
                  f'<link rel="icon" type="image/png" href="{favicon}" sizes="64x64">', text)
    index.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    update_markup(generate())

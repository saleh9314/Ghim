#!/usr/bin/env python3
"""Prepare editable transparent SVG wordmarks from the approved original logo.

Uses Pillow, NumPy and the Potrace CLI only during preparation, not at runtime.
No fonts, embedded bitmaps, background rectangle or replacement lettering.
Potrace: https://potrace.sourceforge.net/ (mirror: github.com/skyrpex/potrace)
"""
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
SOURCE = ROOT / 'assets/logo.png'
ET.register_namespace('', NS)
PALETTES = {
    'dark': {'wordmark': '#19313a', 'cloud': '#9aac97'},
    'light': {'wordmark': '#ffffff', 'cloud': '#cad6c6'},
}


def masks():
    with Image.open(SOURCE) as original:
        if original.size != (1000, 1000):
            raise ValueError('This source-specific trace expects the approved 1000px logo')
        pixels = np.array(original.convert('RGB'), dtype=np.int16)
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    y, x = np.indices(red.shape)
    # Isolate the authorized wordmark only: the circular seal and small caption
    # remain in the original file, not the website-specific wordmark.
    region = (x >= 180) & (x < 820) & (y >= 280) & (y < 604)
    wordmark = region & (red < 150) & (green < 175) & (blue - red > 16)
    cloud = ((x >= 550) & (x < 760) & (y >= 340) & (y < 470)
             & (red > 90) & (red < 225) & (green - red > 2)
             & (blue < red + 12))
    combined = wordmark | cloud
    yy, xx = np.where(combined)
    box = (int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1)
    x0, y0, x1, y1 = box
    # Real transparent clearspace around the actual mark, not a square badge.
    padding = 24
    result = {}
    for name, mask in [('wordmark', wordmark), ('cloud', cloud)]:
        cut = np.pad(mask[y0:y1, x0:x1], padding)
        result[name] = Image.fromarray(np.where(cut, 0, 255).astype('uint8')).convert('1')
    return result, box, result['wordmark'].size


def trace(mask, directory, name):
    source = directory / (name + '.pbm')
    output = directory / (name + '.svg')
    mask.save(source)
    speckle_limit = '20' if name == 'cloud' else '2'
    subprocess.run(['potrace', str(source), '--svg', '--flat', '--turdsize', speckle_limit,
                    '--alphamax', '1', '--opttolerance', '0.15',
                    '--output', str(output)], check=True)
    tree = ET.parse(output)
    group = tree.find('.//{' + NS + '}g')
    if group is None or not group.findall('{' + NS + '}path'):
        raise ValueError('No vector paths were traced')
    return group


def build(groups, width, height, palette):
    root = ET.Element('{' + NS + '}svg', {
        'viewBox': f'0 0 {width} {height}', 'width': str(width), 'height': str(height),
        'role': 'img', 'aria-labelledby': 'ghim-title ghim-desc',
        'preserveAspectRatio': 'xMidYMid meet',
    })
    ET.SubElement(root, '{' + NS + '}title', {'id': 'ghim-title'}).text = 'غيم'
    ET.SubElement(root, '{' + NS + '}desc', {'id': 'ghim-desc'}).text = (
        'رسم غيم العربي ولمسة السحابة، بمسارات متجهية وخلفية شفافة.')
    for name, group in groups.items():
        cloned = deepcopy(group)
        cloned.attrib['id'] = name
        cloned.attrib['fill'] = palette[name]
        cloned.attrib['stroke'] = 'none'
        root.append(cloned)
    data = ET.tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + data + '\n'


def update_page(manifest):
    path = ROOT / 'index.html'
    html = path.read_text()
    import re
    from html.parser import HTMLParser

    class Attrs(HTMLParser):
        def handle_starttag(self, tag, attrs):
            self.attrs = dict(attrs)

    def replacement(match):
        parsed = Attrs(); parsed.feed(match.group())
        attrs = parsed.attrs
        variant = attrs.get('data-vector-logo')
        if not variant:
            return match.group()
        entry = manifest['variants'][variant]
        attrs.update(src=entry['path'], width=str(manifest['width']),
                     height=str(manifest['height']))
        return '<img ' + ' '.join(f'{key}="{escape(value, quote=True)}"'
                                 for key, value in attrs.items()) + '>'
    html = re.sub(r'<img\b[^>]*>', replacement, html)
    path.write_text(html)


def main():
    (ROOT / 'assets/brand').mkdir(parents=True, exist_ok=True)
    (ROOT / 'assets/optimized').mkdir(parents=True, exist_ok=True)
    layers, box, size = masks()
    with tempfile.TemporaryDirectory() as temporary:
        groups = {name: trace(mask, Path(temporary), name) for name, mask in layers.items()}
    width, height = size
    manifest = {
        'source': 'assets/logo.png', 'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
        'source_wordmark_bounds': box, 'clearspace': 24,
        'width': width, 'height': height, 'method': 'Potrace 1.16 vector trace',
        'variants': {},
    }
    for variant, palette in PALETTES.items():
        content = build(groups, width, height, palette).encode('utf-8')
        master = ROOT / f'assets/brand/ghim-{variant}.svg'
        fingerprint = sha256(content).hexdigest()[:12]
        served = ROOT / f'assets/optimized/ghim-{variant}-{fingerprint}.svg'
        master.write_bytes(content); served.write_bytes(content)
        manifest['variants'][variant] = {
            'master': master.relative_to(ROOT).as_posix(),
            'path': served.relative_to(ROOT).as_posix(), 'bytes': len(content),
            'colors': palette,
        }
        print(variant, master, 'bytes', len(content), flush=True)
    (ROOT / 'assets/brand/logo-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    update_page(manifest)


if __name__ == '__main__':
    main()

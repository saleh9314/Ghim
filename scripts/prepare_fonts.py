#!/usr/bin/env python3
"""Vendor the same Google Fonts WOFF2 files, licenses and unicode ranges.

Run manually when updating font versions; no network build step is needed.
Uses only Python's standard library. Existing styles and font weights remain.
"""
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QUERY = 'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Marhey:wght@500&display=swap'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
FAMILIES = ('Cairo', 'Marhey')
OUTPUT = ROOT / 'assets/fonts'
LICENSES = ROOT / 'docs/font-licenses'


def download(url):
    with urlopen(Request(url, headers={'User-Agent': UA}), timeout=30) as response:
        return response.read()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    LICENSES.mkdir(parents=True, exist_ok=True)
    css = download(QUERY).decode('utf-8')
    records, by_url, faces = [], {}, []
    for subset, body in re.findall(r'/\*\s*([^*]+?)\s*\*/\s*(@font-face\s*\{[^}]+\})', css):
        family = re.search(r"font-family:\s*'([^']+)'", body).group(1)
        url = re.search(r'src:\s*url\(([^)]+)\)', body).group(1)
        weight = re.search(r'font-weight:\s*([^;]+)', body).group(1)
        if family not in FAMILIES or not url.startswith('https://fonts.gstatic.com/') or not url.endswith('.woff2'):
            raise RuntimeError('Unexpected font family or URL')
        if url not in by_url:
            data = download(url)
            if data[:4] != b'wOF2':
                raise RuntimeError('Expected a WOFF2 file')
            filename = f'{family.lower()}-{subset.strip()}-{sha256(data).hexdigest()[:12]}.woff2'
            path = OUTPUT / filename
            path.write_bytes(data)
            record = {'family': family, 'subset': subset.strip(),
                      'path': path.relative_to(ROOT).as_posix(),
                      'bytes': len(data), 'source': url, 'weights': []}
            by_url[url] = record
            records.append(record)
            print(f'{family} {subset.strip()}: {len(data)} bytes', flush=True)
        record = by_url[url]
        record['weights'].append(weight)
        body = body.replace(url, record['path'])
        # Exact unicode ranges and faces are preserved from the font service.
        faces.append(re.sub(r'\s+', ' ', body).strip())
    if len(records) != 6 or len(faces) != 15:
        raise RuntimeError('Unexpected CSS; review before updating font declarations')
    for family in FAMILIES:
        license_url = f'https://raw.githubusercontent.com/google/fonts/main/ofl/{family.lower()}/OFL.txt'
        license_text = download(license_url)
        if b'SIL OPEN FONT LICENSE' not in license_text:
            raise RuntimeError('Expected the SIL Open Font License')
        (LICENSES / f'{family}-OFL.txt').write_bytes(license_text)
    manifest = {'source_css': QUERY, 'fonts': records}
    (ROOT / 'assets/fonts-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    preloads = '\n'.join(
        f'<link rel="preload" as="font" type="font/woff2" href="{r["path"]}" crossorigin data-font="{r["family"]}">'
        for r in records if r['subset'] == 'arabic')
    block = '/* LOCAL-FONTS:START */\n' + '\n'.join(faces) + '\n/* LOCAL-FONTS:END */'
    index = ROOT / 'index.html'
    html = index.read_text()
    html = re.sub(r'^<link[^>]+https://fonts\.(?:googleapis|gstatic)\.com[^>]*>\n?', '', html, flags=re.M)
    html = re.sub(r'^<link[^>]+data-font="(?:Cairo|Marhey)"[^>]*>\n?', '', html, flags=re.M)
    if '/* LOCAL-FONTS:START */' in html:
        html = re.sub(r'/\* LOCAL-FONTS:START \*/[\s\S]*?/\* LOCAL-FONTS:END \*/', block, html)
    else:
        html = html.replace('<style>\n', '<style>\n' + block + '\n', 1)
    html = html.replace('<style>\n', preloads + '\n<style>\n', 1)
    index.write_text(html)


if __name__ == '__main__':
    main()

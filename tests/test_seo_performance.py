"""SEO and optimized asset checks using only the Python standard library."""
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://ghim.pages.dev'
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
MANIFEST = json.loads((ROOT / 'assets/image-manifest.json').read_text())


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.items = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.items.append((tag, dict(attrs)))


TAGS = Tags(HTML)


class SEOTests(unittest.TestCase):
    def test_canonical_and_social_urls_agree(self):
        canonical = [a['href'] for t, a in TAGS.items if t == 'link' and a.get('rel') == 'canonical']
        self.assertEqual(canonical, [ORIGIN + '/'])
        metas = {a.get('property') or a.get('name'): a.get('content') for t, a in TAGS.items if t == 'meta'}
        self.assertEqual(metas['og:url'], canonical[0])
        self.assertIn('شقق غيم', metas['description'])
        self.assertEqual(metas['og:type'], 'website')
        self.assertEqual(metas['og:locale'], 'ar_SA')
        self.assertEqual(metas['twitter:card'], 'summary_large_image')
        self.assertIn('بريدة', metas['og:title'])
        self.assertIn('حي الفايزية', HTML.split('</title>')[0])
        for key in ('og:image', 'twitter:image'):
            url = urlparse(metas[key])
            self.assertEqual(url.scheme + '://' + url.netloc, ORIGIN)
            self.assertTrue((ROOT / url.path.lstrip('/')).is_file())

    def test_structured_data_is_valid_and_factual(self):
        data = json.loads(re.search(r'<script type="application/ld\+json">([\s\S]*?)</script>', HTML).group(1))
        self.assertEqual(data['@context'], 'https://schema.org')
        self.assertEqual(data['@type'], 'WebSite')
        self.assertEqual(data['url'], ORIGIN + '/')
        self.assertEqual(data['inLanguage'], 'ar-SA')
        self.assertNotIn('aggregateRating', data)
        self.assertNotIn('offers', data)

    def test_robots_is_a_real_allowing_document(self):
        text = (ROOT / 'robots.txt').read_text()
        self.assertIn('User-agent: *', text)
        self.assertIn('Allow: /', text)
        self.assertIn('Sitemap: ' + ORIGIN + '/sitemap.xml', text)
        self.assertNotIn('<html', text)
        self.assertNotIn('Disallow: /', text)

    def test_sitemap_contains_only_canonical_page(self):
        tree = ET.parse(ROOT / 'sitemap.xml')
        urls = [loc.text for loc in tree.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(urls, [ORIGIN + '/'])
        self.assertTrue(all('#' not in url for url in urls))

    def test_error_page_exists_and_is_not_indexable(self):
        page = (ROOT / '404.html').read_text()
        tags = Tags(page).items
        robots = [a.get('content') for t, a in tags if t == 'meta' and a.get('name') == 'robots']
        self.assertTrue(robots and 'noindex' in robots[0])
        self.assertIn('الصفحة غير موجودة', page)
        self.assertIn(ORIGIN + '/', page)

    def test_no_blank_client_rendered_shell(self):
        self.assertIn('<html lang="ar" dir="rtl">', HTML)
        self.assertEqual(len(re.findall(r'<h1\b', HTML)), 1)
        self.assertIn('حتى 3 ضيوف', HTML)
        self.assertIn('الفايزية', HTML)
        self.assertNotIn('name="keywords"', HTML)


class AssetTests(unittest.TestCase):
    def test_every_generated_asset_is_fingerprinted_and_preserves_ratio(self):
        for name, entry in MANIFEST['images'].items():
            source = ROOT / 'assets' / name
            self.assertEqual(source.stat().st_size, entry['source_bytes'])
            ratio = entry['original_height'] / entry['original_width']
            widths = []
            for variant in entry['variants'] + ([entry['favicon']] if 'favicon' in entry else []):
                file = ROOT / variant['path']
                content = file.read_bytes()
                self.assertEqual(len(content), variant['bytes'])
                self.assertIn(sha256(content).hexdigest()[:12], file.name)
                self.assertLessEqual(variant['width'], entry['original_width'])
                self.assertLessEqual(abs(variant['height'] - variant['width'] * ratio), 0.5)
                if file.suffix == '.webp':
                    self.assertEqual(content[:4], b'RIFF')
                    self.assertEqual(content[8:12], b'WEBP')
                    widths.append(variant['width'])
            self.assertEqual(widths, sorted(set(widths)))
            self.assertEqual(entry['full'], entry['variants'][-1]['path'])

    def test_display_images_have_srcset_sizes_and_dimensions(self):
        for tag, attrs in TAGS.items:
            if tag != 'img' or not attrs.get('src'):
                continue
            self.assertTrue(attrs['src'].startswith('assets/optimized/'))
            self.assertGreater(int(attrs['width']), 0)
            self.assertGreater(int(attrs['height']), 0)
            self.assertEqual(attrs.get('decoding'), 'async')
            if attrs.get('data-vector-logo'):
                self.assertTrue(attrs['src'].endswith('.svg'))
                self.assertTrue((ROOT / attrs['src']).is_file())
                self.assertNotIn('srcset', attrs)
                self.assertNotIn('data-image', attrs)
                continue  # Detailed vector structure checks live in test_logo_polish.
            self.assertTrue(attrs.get('sizes'))
            variants = {v['path']: v for v in MANIFEST['images'][attrs['data-image']]['variants']}
            for candidate in attrs['srcset'].split(','):
                file, descriptor = candidate.strip().split()
                self.assertIn(file, variants)
                self.assertEqual(descriptor, str(variants[file]['width']) + 'w')
            self.assertEqual(int(attrs['width']), variants[attrs['src']]['width'])
            self.assertEqual(int(attrs['height']), variants[attrs['src']]['height'])

    def test_hero_is_not_lazy_loaded(self):
        hero = [a for t, a in TAGS.items if t == 'img' and a.get('data-role') == 'hero']
        self.assertEqual(len(hero), 1)
        self.assertEqual(hero[0].get('fetchpriority'), 'high')
        self.assertNotEqual(hero[0].get('loading'), 'lazy')

    def test_gallery_full_images_only_assigned_on_click(self):
        shots = [a for t, a in TAGS.items if t == 'button' and a.get('class') == 'shot']
        self.assertEqual(len(shots), 12)
        for shot in shots:
            self.assertEqual(shot['data-full'], MANIFEST['images'][shot['data-image']]['full'])
        dynamic_image = [a for t, a in TAGS.items if t == 'img' and a.get('id') == 'big'][0]
        self.assertNotIn('src', dynamic_image)
        self.assertNotIn('srcset', dynamic_image)
        self.assertIn('big.src=x.dataset.full', HTML)

    def test_optimized_unique_images_are_smaller(self):
        original = sum(e['source_bytes'] for e in MANIFEST['images'].values())
        optimized = sum(e['variants'][-1]['bytes'] for e in MANIFEST['images'].values())
        self.assertLess(optimized, original * 0.2)
        for name in ('unit2-lounge.jpg', 'unit2-hospitality.jpg', 'unit2-lounge-2.jpg'):
            entry = MANIFEST['images'][name]
            self.assertLess(entry['variants'][-1]['bytes'], entry['source_bytes'] * 0.15)

    def test_cache_policy_only_targets_fingerprinted_files(self):
        headers = (ROOT / '_headers').read_text()
        self.assertIn('/assets/optimized/*\n  Cache-Control: public, max-age=31536000, immutable', headers)
        cache_paths = re.findall(r'^([^#\n]+)\n  Cache-Control:', headers, re.M)
        self.assertEqual(cache_paths, ['/assets/optimized/*', '/assets/fonts/*'])
        self.assertNotIn('/assets/image-manifest.json\n  Cache-Control', headers)
        for file in (ROOT / 'assets/optimized').iterdir():
            self.assertRegex(file.name, r'-[0-9a-f]{12}\.(webp|png|svg)$')
        self.assertIn('/robots.txt\n  Content-Type: text/plain', headers)
        self.assertIn('/sitemap.xml\n  Content-Type: application/xml', headers)

    def test_local_fonts_preserve_weights_ranges_and_licenses(self):
        fonts = json.loads((ROOT / 'assets/fonts-manifest.json').read_text())['fonts']
        self.assertEqual(len(fonts), 6)
        self.assertNotIn('https://fonts.googleapis.com', HTML)
        self.assertNotIn('https://fonts.gstatic.com', HTML)
        preloads = [a for t, a in TAGS.items if t == 'link' and a.get('as') == 'font']
        self.assertEqual(len(preloads), 2)
        self.assertEqual({a['data-font'] for a in preloads}, {'Cairo', 'Marhey'})
        for font in fonts:
            data = (ROOT / font['path']).read_bytes()
            self.assertEqual(data[:4], b'wOF2')
            self.assertEqual(len(data), font['bytes'])
            self.assertIn(sha256(data).hexdigest()[:12], font['path'])
            self.assertEqual(font['weights'], ['400', '600', '700', '800'] if font['family'] == 'Cairo' else ['500'])
            self.assertIn(font['path'], HTML)
        self.assertEqual(HTML.count('font-display: swap'), 15)
        self.assertIn('unicode-range:', HTML)
        for family in ('Cairo', 'Marhey'):
            license_text = (ROOT / 'docs/font-licenses' / (family + '-OFL.txt')).read_text()
            self.assertIn('SIL OPEN FONT LICENSE', license_text)


if __name__ == '__main__':
    unittest.main()

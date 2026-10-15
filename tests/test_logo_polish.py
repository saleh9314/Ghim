"""Focused checks for the vector wordmark and preserved shadow polish."""
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
CSS = re.search(r'<style>([\s\S]*?)</style>', HTML).group(1)
MOBILE, DESKTOP = CSS.split('@media(min-width:760px){', 1)
MANIFEST = json.loads((ROOT / 'assets/brand/logo-manifest.json').read_text())
NS = '{http://www.w3.org/2000/svg}'


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.feed(HTML)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('data-vector-logo'):
            self.items.append(attrs)


LOGOS = Images().items


def declarations(selector, css=MOBILE):
    match = re.search(re.escape(selector) + r'\{([^}]+)\}', css)
    if not match:
        raise AssertionError('Missing CSS selector: ' + selector)
    return dict(part.split(':', 1) for part in match.group(1).split(';') if part)


class LogoPolishTests(unittest.TestCase):
    def test_logo_sizes_by_placement_preserve_aspect_ratio(self):
        for selector, width, height, css in [
            ('.hero-logo', '210px', 'auto', MOBILE),
            ('.hero-logo', '244px', 'auto', DESKTOP),
            ('.brand img', '64px', '33px', MOBILE),
            ('.foot-brand img', '88px', 'auto', MOBILE),
        ]:
            rule = declarations(selector, css)
            self.assertEqual(rule['width'], width)
            self.assertEqual(rule['height'], height)
        self.assertEqual(declarations('.hero-logo')['aspect-ratio'], '662/341')
        self.assertEqual(declarations('.foot-brand img')['aspect-ratio'], '662/341')

    def test_transparent_wordmark_has_no_square_badge(self):
        for selector in ('.hero-logo', '.brand img', '.foot-brand img'):
            rule = declarations(selector)
            self.assertEqual(rule['object-fit'], 'contain')
            self.assertEqual(rule['background'], 'none')
            self.assertEqual(rule['border-radius'], '0')
        rule = declarations('.hero-logo')
        self.assertEqual(rule['padding'], '0')
        self.assertEqual(rule['box-shadow'], 'none')
        self.assertEqual(declarations('.hero-content')['padding'], '72px 0 34px')

    def test_site_uses_fingerprinted_vectors_with_reserved_dimensions(self):
        self.assertEqual(len(LOGOS), 4)
        for attrs in LOGOS:
            variant = MANIFEST['variants'][attrs['data-vector-logo']]
            self.assertEqual(attrs['src'], variant['path'])
            self.assertEqual(int(attrs['width']), MANIFEST['width'])
            self.assertEqual(int(attrs['height']), MANIFEST['height'])
            self.assertEqual(attrs.get('decoding'), 'async')
            self.assertNotIn('srcset', attrs)
            self.assertNotIn('data-image', attrs)
            self.assertNotIn('sizes', attrs)
        self.assertNotRegex(HTML, r'<img[^>]*data-image="logo.png"')

    def test_header_switches_light_and_dark_without_new_javascript(self):
        self.assertEqual(declarations('.brand .brand-dark')['display'], 'none')
        self.assertEqual(declarations('.header.scrolled .brand-light')['display'], 'none')
        self.assertEqual(declarations('.header.scrolled .brand-dark')['display'], 'block')
        self.assertIn('aria-label="غيم للشقق المفروشة"', HTML)
        self.assertIn('@media(max-width:419px){.brand span{display:none}}', CSS)
        for attrs in LOGOS:
            if attrs['class'].startswith('brand-'):
                self.assertEqual(attrs.get('alt'), '')
                self.assertEqual(attrs.get('aria-hidden'), 'true')

    def test_vector_files_are_editable_safe_and_transparent(self):
        for variant in MANIFEST['variants'].values():
            content = (ROOT / variant['path']).read_bytes()
            self.assertEqual(content, (ROOT / variant['master']).read_bytes())
            self.assertEqual(len(content), variant['bytes'])
            self.assertIn(sha256(content).hexdigest()[:12], variant['path'])
            self.assertLess(len(content), 5000)
            root = ET.fromstring(content)
            self.assertEqual(root.tag, NS + 'svg')
            self.assertEqual(root.get('viewBox'), '0 0 662 341')
            names = {node.tag.removeprefix(NS) for node in root.iter()}
            self.assertEqual(names, {'svg', 'title', 'desc', 'g', 'path'})
            self.assertNotIn(b'data:image', content)
            groups = {node.get('id'): node for node in root.findall(NS + 'g')}
            self.assertEqual(set(groups), {'wordmark', 'cloud'})
            for name, color in variant['colors'].items():
                self.assertEqual(groups[name].get('fill'), color)
                paths = groups[name].findall(NS + 'path')
                self.assertTrue(paths)
                self.assertTrue(all('c' in path.get('d', '') for path in paths))
            self.assertEqual(root.find(NS + 'title').text, 'غيم')

    def test_original_circular_logo_and_favicon_remain(self):
        self.assertEqual(sha256((ROOT / MANIFEST['source']).read_bytes()).hexdigest(), MANIFEST['source_sha256'])
        self.assertIn('favicon-64-', HTML)
        self.assertEqual(MANIFEST['source_wordmark_bounds'], [191, 296, 805, 589])
        self.assertEqual(MANIFEST['clearspace'], 24)

    def test_secondary_shadows_are_softened(self):
        expected = {
            '.header.scrolled .nav': '0 8px 24px rgba(17,40,49,.06)',
            '.drawer': '0 12px 32px rgba(17,40,49,.08)',
            '.chooser': '0 12px 32px rgba(17,40,49,.08)',
            '.about-photo img': '0 12px 32px rgba(17,40,49,.08)',
            '.unit-card': '0 10px 28px rgba(17,40,49,.05)',
            '.shot': 'none',
            '.reserve-shell': '0 16px 40px rgba(16,38,47,.12)',
            '.loc-card,.map-card': '0 8px 20px rgba(17,40,49,.04)',
            '.dock': '0 -6px 20px rgba(17,40,49,.04)',
        }
        for selector, shadow in expected.items():
            self.assertEqual(declarations(selector)['box-shadow'], shadow)
        self.assertEqual(declarations('.hero-description')['text-shadow'], '0 2px 12px rgba(0,0,0,.4)')

    def test_round_cards_and_original_image_treatments_remain(self):
        self.assertEqual(declarations('.unit-card')['border-radius'], '34px')
        self.assertEqual(declarations('.shot')['border-radius'], '25px')
        self.assertEqual(declarations('.unit-hero img')['filter'], 'saturate(.82) contrast(.97)')
        self.assertEqual(declarations('.hero-media img')['filter'], 'saturate(.8) contrast(.97)')
        self.assertIn('rgba(9,22,28,.84)', declarations('.unit-hero:after')['background'])
        self.assertIn('rgba(7,18,24,.9)', declarations('.hero-media:after')['background'])


if __name__ == '__main__':
    unittest.main()

"""Focused checks for the bounded logo and shadow polish."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')
CSS = re.search(r'<style>([\s\S]*?)</style>', HTML).group(1)
MOBILE, DESKTOP = CSS.split('@media(min-width:760px){', 1)
MANIFEST = json.loads((ROOT / 'assets/image-manifest.json').read_text())


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.roles = {}
        self.feed(HTML)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('data-image') == 'logo.png':
            self.roles[attrs['data-role']] = attrs


LOGOS = Images().roles


def declarations(selector, css=MOBILE):
    match = re.search(re.escape(selector) + r'\{([^}]+)\}', css)
    if not match:
        raise AssertionError('Missing CSS selector: ' + selector)
    return dict(part.split(':', 1) for part in match.group(1).split(';') if part)


class LogoPolishTests(unittest.TestCase):
    def test_logo_sizes_by_placement(self):
        for selector, expected, css in [
            ('.hero-logo', '104px', MOBILE),
            ('.hero-logo', '120px', DESKTOP),
            ('.brand img', '43px', MOBILE),
            ('.foot-brand img', '48px', MOBILE),
        ]:
            rule = declarations(selector, css)
            self.assertEqual(rule['width'], expected)
            self.assertEqual(rule['height'], expected)

    def test_hero_container_has_less_padding_and_softer_shadow(self):
        rule = declarations('.hero-logo')
        self.assertEqual(rule['object-fit'], 'contain')
        self.assertEqual(rule['background'], '#fff')
        self.assertEqual(rule['padding'], '2px')
        self.assertEqual(rule['border-radius'], '18px')
        self.assertEqual(rule['box-shadow'], '0 8px 24px rgba(0,0,0,.14)')
        self.assertEqual(declarations('.hero-content')['padding'], '72px 0 34px')

    def test_srcset_matches_larger_logo_without_heavy_original(self):
        self.assertEqual(set(LOGOS), {'logo', 'hero-logo', 'footer-logo'})
        self.assertEqual(LOGOS['hero-logo']['sizes'], '(min-width: 760px) 120px, 104px')
        self.assertEqual(LOGOS['logo']['sizes'], '43px')
        self.assertEqual(LOGOS['footer-logo']['sizes'], '48px')
        variants = MANIFEST['images']['logo.png']['variants']
        self.assertEqual([v['width'] for v in variants], [96, 192, 384])
        self.assertGreaterEqual(variants[-1]['width'], 120 * 3)
        self.assertLess(variants[-1]['bytes'], 12000)
        self.assertLess(variants[0]['bytes'], 2000)
        for attrs in LOGOS.values():
            self.assertIn('384w', attrs['srcset'])
            self.assertTrue(attrs['src'].endswith('.webp'))
            self.assertNotEqual(attrs['src'], 'assets/logo.png')

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
        # Preserve readable text shadows rather than weakening image contrast.
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

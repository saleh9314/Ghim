"""Static regression checks; run with python3 -m unittest discover -s tests."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


PAGE = PageParser()
PAGE.feed(HTML)


class PageTests(unittest.TestCase):
    def test_short_showcase_hero(self):
        self.assertIn('<h1>غيم… راحتك في بريدة</h1>', HTML)
        self.assertIn('class="hero-description"', HTML)
        self.assertIn('شقتان مفروشتان بخصوصية ودخول ذاتي.', HTML)
        self.assertIn('href="#stays">اكتشف الشقق</a>', HTML)
        self.assertIn('>تواصل معنا</a>', HTML)

    def test_verified_unit_details(self):
        for unit in ('1', '2'):
            block = re.search(r'<article[^>]+id="unit' + unit + r'"[\s\S]*?</article>', HTML).group()
            for value in ('حتى 3 ضيوف', 'غرفة واحدة', 'سرير كينج واحد', 'حمام واحد'):
                self.assertIn(value, block)
            self.assertEqual(block.count('<dt>'), 4)
            self.assertIn('واي فاي', block)
            self.assertIn('دخول ذاتي', block)
            self.assertIn('موقف مجاني', block)

    def test_readable_type_scale(self):
        sizes = [int(size) for size in re.findall(r'font-size:(\d+)px', HTML)]
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 12)
        self.assertIn('--muted:#58666b', HTML)
        self.assertRegex(HTML, r'\.head p\{font-size:16px')
        self.assertRegex(HTML, r'\.meta dd\{[^}]*font-size:14px')

    def test_local_anchors_are_valid_and_unique(self):
        ids = [attrs['id'] for _, attrs in PAGE.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for tag, attrs in PAGE.elements:
            href = attrs.get('href', '')
            if href.startswith('#'):
                self.assertIn(href[1:], ids)
        for required in ('home', 'about', 'stays', 'unit1', 'unit2', 'gallery', 'gallery1', 'gallery2', 'booking', 'book1', 'book2', 'location'):
            self.assertIn(required, ids)

    def test_images_exist_and_have_alt_text(self):
        for tag, attrs in PAGE.elements:
            if tag == 'img':
                self.assertIn('alt', attrs)
                source = attrs.get('src')
                if source:
                    self.assertTrue((ROOT / source).is_file(), source)
            if 'data-full' in attrs:
                self.assertTrue((ROOT / attrs['data-full']).is_file())

    def test_booking_channels_preserved(self):
        links = [attrs.get('href') for tag, attrs in PAGE.elements if attrs.get('class') == 'channel']
        expected = [
            'https://gathern.co/link/view?id=195865&check_in=2026-09-28&check_out=2026-09-29',
            'https://www.airbnb.com/h/ghiim',
            'https://www.booking.com/Share-6bHACM',
            'https://gathern.co/link/view?id=244148&check_in=2026-09-28&check_out=2026-09-29',
            'https://www.airbnb.com/h/gheem2',
            'https://www.booking.com/Share-EbD7TB',
        ]
        self.assertEqual(Counter(links), Counter(expected))
        buttons = [attrs.get('data-book') for _, attrs in PAGE.elements if 'data-book' in attrs]
        self.assertEqual(buttons, ['1', '2'])


if __name__ == '__main__':
    unittest.main()

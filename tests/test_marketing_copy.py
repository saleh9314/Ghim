"""Regression checks for the owner's approved concise Arabic copy."""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')


def section(name):
    match = re.search(r'<section\b[^>]*id="' + name + r'"[\s\S]*?</section>', HTML)
    if not match:
        raise AssertionError('Missing section: ' + name)
    return match.group()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.active = None
        self.feed(HTML)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.active = {'attrs': dict(attrs), 'text': ''}

    def handle_data(self, text):
        if self.active is not None:
            self.active['text'] += text

    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.links.append(self.active)
            self.active = None


class MarketingCopyTests(unittest.TestCase):
    def test_each_section_has_the_approved_short_copy(self):
        required = {
            'home': ['غيم… راحتك في بريدة', 'شقتان مفروشتان بخصوصية ودخول ذاتي.', 'اكتشف الشقق'],
            'about': ['مساحتك الخاصة', 'شقق مستقلة بتصميمين مختلفين، مع واي فاي وموقف مجاني.'],
            'stays': ['شقتان، بطابعين', 'قارن المواصفات واختر شقتك.',
                      'طابع دافئ، مع ركن قهوة ومطبخ مجهز.', 'طابع عصري، مع مطبخ ببار ومساحة للعمل.'],
            'gallery': ['غيم عن قرب', 'صور فعلية لكل شقة.'],
            'booking': ['اختر شقتك ومنصة الحجز', 'شاهد الأسعار والتوافر على منصة الحجز.'],
            'location': ['غيم في الفايزية', 'افتح الخريطة للوصول إلى الشقق.', 'الموقع على الخريطة ↗', 'الاتجاهات إلى غيم'],
        }
        for name, texts in required.items():
            block = section(name)
            for text in texts:
                self.assertIn(text, block)

    def test_repeated_generic_claims_are_removed_from_display_copy(self):
        body = HTML.split('<body>', 1)[1].split('<script>', 1)[0]
        for old in ['حجز مرن', 'أناقة تستحق الإقامة', 'تجربة إقامة واضحة، مرتبة، ومريحة',
                    'موقع واضح وسهل الوصول', 'المعرض الأول', 'المعرض الثاني', 'احجز الآن']:
            self.assertNotIn(old, body)
        self.assertNotIn('<p class="about-body">', section('about'))
        self.assertEqual(section('home').count('class="mini"'), 3)
        self.assertEqual(section('about').count('class="fact"'), 4)
        self.assertIn('<strong>اختر طابع إقامتك</strong>', HTML)
        self.assertIn('<small>طابع دافئ</small>', HTML)
        self.assertIn('<small>طابع عصري</small>', HTML)

    def test_ctas_describe_destination_and_keep_apartment_context(self):
        links = Links().links
        for class_name in ('head-btn', 'dock-book'):
            items = [link for link in links if link['attrs'].get('class') == class_name]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['text'], 'خيارات الحجز')
            self.assertEqual(items[0]['attrs']['href'], '#booking')
        unit_links = [link for link in links if 'data-book' in link['attrs']]
        self.assertEqual(len(unit_links), 2)
        for unit, link in zip(('1', '2'), unit_links):
            self.assertEqual(link['attrs']['data-book'], unit)
            self.assertEqual(link['attrs']['aria-label'], 'خيارات الحجز لغيم 0' + unit)
            self.assertEqual(link['text'], 'خيارات الحجز')
            self.assertEqual(link['attrs']['href'], '#booking')
        channels = [link for link in links if link['attrs'].get('class') == 'channel']
        self.assertEqual(len(channels), 6)
        for link in channels:
            self.assertIn('زيارة المنصة ↗', link['text'])
            self.assertTrue(link['attrs']['href'].startswith('https://'))
        for unit in ('1', '2'):
            block = re.search(r'<div class="book-panel(?: active)?" id="book' + unit + r'">([\s\S]*?)(?=<div class="book-panel"|</div></div></section>)', HTML).group(1)
            self.assertEqual(block.count('<p>صفحة غيم 0' + unit + '</p>'), 3)

    def test_contact_number_and_footer_brand_remain_visible(self):
        self.assertEqual(HTML.count('<small class="direct-phone">056 201 8166</small>'), 2)
        self.assertIn('.direct-phone{display:block;direction:ltr;font-size:12px', HTML)
        direct_links = [link for link in Links().links if link['attrs'].get('class') == 'wa']
        self.assertEqual(len(direct_links), 2)
        for link in direct_links:
            self.assertEqual(link['text'], 'تواصل عبر واتساب ↗')
            self.assertTrue(link['attrs']['href'].startswith('https://wa.me/966562018166?'))
        footer = re.search(r'<footer>[\s\S]*?</footer>', HTML).group()
        self.assertIn('غيم للشقق المفروشة', footer)
        self.assertIn('مساحتك الهادئة في بريدة', footer)
        self.assertIn('© 2026 غيم · جميع الحقوق محفوظة', footer)

    def test_gallery_help_and_search_title_remain_accurate(self):
        self.assertEqual(section('gallery').count('اضغط على الصورة لتكبيرها.'), 2)
        self.assertEqual(section('gallery').count('class="shot"'), 12)
        self.assertIn('<title>غيم للشقق المفروشة في بريدة | حي الفايزية</title>', HTML)
        self.assertNotIn('<title>غيم… راحتك في بريدة</title>', HTML)


if __name__ == '__main__':
    unittest.main()

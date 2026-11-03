import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

# Each page, and a script it must load. The pages check the login in the browser (helper.js).
PAGES = {
    "/login": "Login",
    "/containers": "js/containers.js",
    "/images": "js/images.js",
    "/browse": "js/browse.js",
    "/terminal": "js/terminal.js",
    "/console/shell/abc123": "js/console.js",
    "/console/attach/abc123": "js/console.js",
}


class PageTests(TestCase):
    def test_every_page_renders(self):
        for url, marker in PAGES.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, marker)

    def test_root_goes_to_login(self):
        self.assertRedirects(self.client.get("/"), "/login", fetch_redirect_response=False)

    def test_local_scripts_and_styles_exist(self):
        static_dir = Path(settings.STATICFILES_DIRS[0])
        found = []
        for url in PAGES:
            html = self.client.get(url).content.decode()
            for ref in re.findall(rf'{settings.STATIC_URL}([^"]+)', html):
                found.append(ref)
                with self.subTest(url=url, ref=ref):
                    self.assertTrue((static_dir / ref).is_file(), ref)
        self.assertIn("js/terminal-session.js", found)

    def test_third_party_files_are_pinned_and_checked(self):
        tags = 0
        for url in PAGES:
            html = self.client.get(url).content.decode()
            for tag in re.findall(r'<(?:script|link)[^>]+(?:src|href)="https://[^>]+>', html):
                tags += 1
                with self.subTest(url=url, tag=tag[:60]):
                    self.assertIn('integrity="sha384-', tag)
                    self.assertRegex(tag, r'@\d+\.\d+\.\d+/|/\d+\.\d+\.\d+/')  # an exact version
        self.assertGreater(tags, 10)

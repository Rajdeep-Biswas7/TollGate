import unittest

from tests import _stubs  # noqa: F401  (must come first)

from app.errors import ToolError
from app.mathx import calculate
from app.parsers import html_to_text, parse_arxiv_atom, parse_ddg_html
from app.safety import ip_is_public, validate_url_shape
from app.schema import clean_schema, has_params


class CalculatorTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(calculate("1 + 2 * 3"), 7)
        self.assertEqual(calculate("(1250 * 1.18) / 12"), 122.91666666666667)
        self.assertEqual(calculate("2^10"), 1024)
        self.assertEqual(calculate("sqrt(144) + ln(e)"), 13)
        self.assertEqual(calculate("10 % 4"), 2)

    def test_rejects_code_and_abuse(self):
        for bad in ["__import__('os').system('ls')", "open('x')", "a + 1", "9**9**9", "1/0", "(-8)**0.5", "factorial(500)", "x" * 300, "", "'a'*5"]:
            with self.assertRaises(ToolError, msg=bad):
                calculate(bad)


class SafetyTests(unittest.TestCase):
    def test_ip_classification(self):
        for private in ["127.0.0.1", "10.1.2.3", "192.168.0.5", "169.254.169.254", "::1", "::ffff:127.0.0.1", "100.64.0.1", "0.0.0.0"]:
            self.assertFalse(ip_is_public(private), private)
        for public in ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"]:
            self.assertTrue(ip_is_public(public), public)

    def test_url_shape(self):
        self.assertEqual(validate_url_shape("https://example.com/a")[1:], ("example.com", 443))
        for bad in ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "https://user:pw@example.com", "http://"]:
            with self.assertRaises(ToolError, msg=bad):
                validate_url_shape(bad)


class ParserTests(unittest.TestCase):
    def test_html_to_text_skips_noise(self):
        html = """<html><head><title> My  Page </title><style>x{}</style></head><body>
        <nav>MENU</nav><h1>Hello</h1><p>First <b>bold</b> para.</p><script>evil()</script>
        <ul><li>one</li><li>two</li></ul><footer>FOOT</footer></body></html>"""
        title, text = html_to_text(html)
        self.assertEqual(title, "My Page")
        self.assertIn("Hello", text)
        self.assertIn("First bold para.", text)
        self.assertIn("one\ntwo", text)
        for noise in ("MENU", "evil", "FOOT", "x{}"):
            self.assertNotIn(noise, text)

    def test_ddg(self):
        html = """
        <div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=1">Example <b>A</b></a>
        <a class="result__snippet" href="x">Snippet about <b>A</b> thing</a></div>
        <div class="result"><a class="result__a" href="//duckduckgo.com/y.js?ad=1">Ad</a></div>
        <div class="result"><a class="result__a" href="https://b.org/">B</a><a class="result__snippet">B snippet</a></div>"""
        res = parse_ddg_html(html, 5)
        self.assertEqual([r["url"] for r in res], ["https://example.com/a", "https://b.org/"])
        self.assertEqual(res[0]["title"], "Example A")
        self.assertEqual(res[0]["snippet"], "Snippet about A thing")

    def test_arxiv(self):
        xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2401.00001v1</id>
        <published>2024-01-02T00:00:00Z</published><title>A  Great
        Paper</title><summary> We do   things. </summary><author><name>Ann</name></author><author><name>Bob</name></author></entry></feed>"""
        p = parse_arxiv_atom(xml)
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]["title"], "A Great Paper")
        self.assertEqual(p[0]["url"], "https://arxiv.org/abs/2401.00001v1")
        self.assertEqual(p[0]["authors"], ["Ann", "Bob"])
        self.assertEqual(p[0]["published"], "2024-01-02")


class SchemaTests(unittest.TestCase):
    def test_clean(self):
        raw = {
            "title": "X",
            "type": "object",
            "properties": {
                "title": {"title": "Title", "type": "string", "default": "a"},
                "q": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Q", "description": "d"},
            },
            "required": ["q"],
            "additionalProperties": False,
        }
        c = clean_schema(raw)
        self.assertEqual(c["properties"]["title"], {"type": "string"})  # property literally named "title" survives
        self.assertEqual(c["properties"]["q"], {"type": "string", "description": "d"})
        self.assertNotIn("additionalProperties", c)
        self.assertTrue(has_params(c))
        self.assertFalse(has_params({"type": "object", "properties": {}}))


if __name__ == "__main__":
    unittest.main()

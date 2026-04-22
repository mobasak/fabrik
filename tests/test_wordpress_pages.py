import unittest
from unittest.mock import MagicMock, patch
import json
from fabrik.wordpress.pages import PageCreator, CreatedPage


class TestWordPressPages(unittest.TestCase):
    def setUp(self):
        self.wp = MagicMock()
        self.api = MagicMock()
        self.creator = PageCreator("wp-test", wp_client=self.wp, api_client=self.api)

    def test_find_homepage(self):
        # Test homepage detection via option
        self.wp.option_get.return_value = "5"
        self.api.get_page.return_value = {
            "id": 5,
            "title": {"rendered": "Welcome"},
            "slug": "welcome",
            "link": "http://test/",
            "parent": 0,
        }

        page = self.creator.find_page("", None)
        self.assertEqual(page.id, 5)
        self.assertEqual(page.slug, "welcome")

    def test_create_page_idempotency(self):
        # Mock find_page to return existing
        with patch.object(PageCreator, "find_page") as mock_find:
            mock_find.return_value = CreatedPage(id=1, title="Test", slug="test", url="")
            page = self.creator.create_or_get_page("Test", slug="test")
            self.assertEqual(page.id, 1)
            self.api._request.assert_not_called()

    def test_create_page_cli_fallback(self):
        # Mock API to fail
        self.api._request.side_effect = Exception("API error")
        self.wp.run.side_effect = [
            "10",
            '{"ID": 10, "post_title": "New Page", "post_name": "new-page"}',
        ]

        page = self.creator.create_page("New Page", slug="new-page")
        self.assertEqual(page.id, 10)
        # Verify CLI command quoting
        create_call = self.wp.run.call_args_list[0][0][0]
        self.assertIn("'--post_title=New Page'", create_call)
        self.assertIn("'--post_name=new-page'", create_call)


if __name__ == "__main__":
    unittest.main()

import unittest

import pwncollege_cli
import responses


class TestPwnCollegeCLI(unittest.TestCase):
    def test_init(self):
        pcc = pwncollege_cli.PwnCollegeCLI()
        self.assertEqual(pcc.base_url, pwncollege_cli.PWNCOLLEGE_CLI_BASE_URL)
        self.assertFalse(pcc.logged_in)
        self.assertEqual(
            pcc.session.headers["User-Agent"],
            pwncollege_cli.PWNCOLLEGE_CLI_USER_AGENT,
        )

    def test_init_custom(self):
        base_url = "https://www.example.org"
        pcc = pwncollege_cli.PwnCollegeCLI(base_url=base_url)
        self.assertEqual(pcc.base_url, base_url)

    @responses.activate
    def test_nonce(self):
        pcc = pwncollege_cli.PwnCollegeCLI()
        responses.get(
            pcc.base_url,
            content_type="text/html",
            status=200,
            body="""
                <script type="text/javascript">
                  var init = {
                      'urlRoot': "",
                      'csrfNonce': "FAKE-CSRF-NONCE",
                      'userMode': "users",
                      'userId': 0,
                      'start': null,
                      'end': null,
                      'theme_settings': null,
                      'dojo': "",
                      'module': ""
                  }
                </script>
            """,
        )
        self.assertEqual(pcc.nonce(), "FAKE-CSRF-NONCE")


if __name__ == "__main__":
    unittest.main()

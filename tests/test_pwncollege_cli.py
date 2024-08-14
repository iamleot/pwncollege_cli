import unittest

import pwncollege_cli
import responses


class TestPwnCollegeCLI(unittest.TestCase):
    def setUp(self):
        base_url = pwncollege_cli.PWNCOLLEGE_CLI_BASE_URL

        responses.get(
            base_url,
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

        responses.get(
            f"{base_url}/login",
            content_type="text/html",
            status=200,
            headers={
                "Set-Cookie": 'session="FAKE-SESSION-COOKIE"; '
                + "HttpOnly; Path=/; SameSite=Lax"
            },
        )

        # XXX: `POST /login` actually redirects to `/challenges` that
        # XXX: redirects to `/dojos` that has such body and status.
        responses.post(
            f"{base_url}/login",
            content_type="text/html",
            status=200,
            body="""
                <script type="text/javascript">
                  var init = {
                      'urlRoot': "",
                      'csrfNonce': "FAKE-CSRF-NONCE",
                      'userMode': "users",
                      'userId': 1234567890,
                      'start': null,
                      'end': null,
                      'theme_settings': null,
                      'dojo': "",
                      'module': ""
                  }
                </script>
            """,
        )

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
        self.assertEqual(pcc.nonce(), "FAKE-CSRF-NONCE")

    @responses.activate
    def test_login(self):
        username = "fake-username"
        password = "fake-password"
        pcc = pwncollege_cli.PwnCollegeCLI()
        self.assertFalse(pcc.logged_in)
        pcc.login(username, password)
        self.assertTrue(pcc.logged_in)


if __name__ == "__main__":
    unittest.main()

import unittest

from flex_watch.detector import detect_state


class DetectStateTests(unittest.TestCase):
    def test_login_url_is_login(self):
        state = detect_state("https://flexstudent.nu.edu.pk/Login", "<h2>Sign In</h2>")
        self.assertEqual(state.status, "login")

    def test_closed_marker_is_closed(self):
        state = detect_state(
            "https://flexstudent.nu.edu.pk/Student/CourseRegistration",
            "<main>Course registration is closed</main>",
        )
        self.assertEqual(state.status, "closed")

    def test_burp_inactive_page_is_closed(self):
        html = """
        <html>
            <body>
                <a href="/Student/CourseRegistration?dump=x">Course Registration</a>
                <div class="alert alert-danger" role="alert">
                    <strong>Registration</strong> not active yet.
                </div>
            </body>
        </html>
        """
        state = detect_state(
            "https://flexstudent.nu.edu.pk/Student/CourseRegistration?dump=x",
            html,
        )
        self.assertEqual(state.status, "closed")
        self.assertIn("not active yet", state.reason)

    def test_registration_controls_are_open(self):
        state = detect_state(
            "https://flexstudent.nu.edu.pk/Student/CourseRegistration",
            """
            <form id="courseRegForm">
                <select class="section"></select>
                <input class="RegisterChkbox" type="checkbox">
                <button id="submit" type="submit">Register</button>
            </form>
            """,
        )
        self.assertEqual(state.status, "open")

    def test_server_error_page_is_error(self):
        state = detect_state(
            "https://flexstudent.nu.edu.pk/Student/CourseRegistration",
            "<html><title>Server Error in '/' Application.</title><body>Runtime Error</body></html>",
        )
        self.assertEqual(state.status, "error")

    def test_home_page_is_home(self):
        state = detect_state(
            "https://flexstudent.nu.edu.pk/Home",
            '<div id="m_ver_menu"><a href="/Student/CourseRegistration?dump=x">Course Registration</a></div>',
        )
        self.assertEqual(state.status, "home")

    def test_unclear_page_is_unknown(self):
        state = detect_state(
            "https://flexstudent.nu.edu.pk/Student/CourseRegistration",
            "<main>Welcome</main>",
        )
        self.assertEqual(state.status, "unknown")


if __name__ == "__main__":
    unittest.main()

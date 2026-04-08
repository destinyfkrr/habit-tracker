import tempfile
import unittest
from datetime import date

from habit_tracker import create_app
from habit_tracker import services


class HabitTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = f"{self.temp_dir.name}/test.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": self.database_path,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_split_pages_load_seeded_sections(self):
        dashboard_response = self.client.get("/")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn(b"Month overview", dashboard_response.data)
        self.assertIn(b"Month Overview", dashboard_response.data)
        self.assertIn(b"Log Day", dashboard_response.data)
        self.assertIn(b"Manage Setup", dashboard_response.data)
        self.assertIn(b"Deep Analysis", dashboard_response.data)
        self.assertIn(b"Cybersecurity", dashboard_response.data)

        log_response = self.client.get("/log")
        self.assertEqual(log_response.status_code, 200)
        self.assertIn(b"Log your day", log_response.data)
        self.assertIn(b"Daily logging", log_response.data)
        self.assertIn(b"Japanese Practice", log_response.data)

        manage_response = self.client.get("/manage")
        self.assertEqual(manage_response.status_code, 200)
        self.assertIn(b"Manage setup", manage_response.data)
        self.assertIn(b"Categories", manage_response.data)
        self.assertIn(b"Habits", manage_response.data)
        self.assertIn(b"Goals", manage_response.data)

        analysis_response = self.client.get("/analysis")
        self.assertEqual(analysis_response.status_code, 200)
        self.assertIn(b"Deep analysis", analysis_response.data)
        self.assertIn(b"Weekly consistency trend", analysis_response.data)
        self.assertIn(b"Habit health table", analysis_response.data)

        with self.app.app_context():
            self.assertGreaterEqual(len(services.list_categories()), 5)
            self.assertGreaterEqual(len(services.list_habits()), 6)
            self.assertGreaterEqual(len(services.list_goals()), 6)

    def test_manage_edit_state_prefills_forms(self):
        with self.app.app_context():
            japanese = next(item for item in services.list_categories() if item["name"] == "Japanese")
            habit = next(item for item in services.list_habits(include_inactive=True) if item["name"] == "Japanese Practice")
            goal = next(item for item in services.list_goals() if item["habit_id"] == habit["id"] and item["goal_type"] == "streak")

        response = self.client.get(
            f"/manage?edit_category={japanese['id']}&edit_habit={habit['id']}&edit_goal={goal['id']}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'value="Japanese"', response.data)
        self.assertIn(b'value="Japanese Practice"', response.data)
        self.assertIn(goal["title"].encode(), response.data)

    def test_edit_routes_and_daily_checkin_flow(self):
        today = date.today().isoformat()
        month_value = f"{date.today():%Y-%m}"

        with self.app.app_context():
            japanese = next(item for item in services.list_categories() if item["name"] == "Japanese")
            habit = next(item for item in services.list_habits(include_inactive=True) if item["name"] == "Japanese Practice")
            goal = next(item for item in services.list_goals() if item["habit_id"] == habit["id"] and item["goal_type"] == "streak")

        category_response = self.client.post(
            "/categories/save",
            data={
                "category_id": str(japanese["id"]),
                "name": "Japanese Study",
                "color": japanese["color"],
                "return_month": month_value,
                "return_date": today,
            },
        )
        self.assertEqual(category_response.status_code, 302)
        self.assertIn("/manage", category_response.headers["Location"])
        self.assertIn("#manage-categories", category_response.headers["Location"])

        habit_response = self.client.post(
            "/habits/save",
            data={
                "habit_id": str(habit["id"]),
                "name": "Japanese Deep Work",
                "category_id": str(japanese["id"]),
                "description": "Grammar, vocab, and sentence practice.",
                "color": habit["color"],
                "start_date": habit["start_date"],
                "active": "1",
                "return_month": month_value,
                "return_date": today,
            },
        )
        self.assertEqual(habit_response.status_code, 302)
        self.assertIn("/manage", habit_response.headers["Location"])
        self.assertIn("#manage-habits", habit_response.headers["Location"])

        goal_response = self.client.post(
            "/goals/save",
            data={
                "goal_id": str(goal["id"]),
                "habit_id": str(habit["id"]),
                "goal_type": "streak",
                "target_value": "7",
                "title": "7-day Japanese streak",
                "return_month": month_value,
                "return_date": today,
            },
        )
        self.assertEqual(goal_response.status_code, 302)
        self.assertIn("/manage", goal_response.headers["Location"])
        self.assertIn("#manage-goals", goal_response.headers["Location"])

        checkin_response = self.client.post(
            "/checkin",
            data={
                "log_date": today,
                "return_month": month_value,
                "habit_ids": str(habit["id"]),
                f"completed_{habit['id']}": "on",
                f"quantity_{habit['id']}": "2",
                f"note_{habit['id']}": "Reviewed kana and finished vocab drills.",
            },
        )
        self.assertEqual(checkin_response.status_code, 302)
        self.assertIn("/log", checkin_response.headers["Location"])
        self.assertIn("#daily-log-panel", checkin_response.headers["Location"])

        manage_response = self.client.get(f"/manage?month={month_value}&date={today}")
        self.assertEqual(manage_response.status_code, 200)
        self.assertIn(b"Manage setup", manage_response.data)
        self.assertIn(b"Japanese Study", manage_response.data)
        self.assertIn(b"Japanese Deep Work", manage_response.data)
        self.assertIn(b"7-day Japanese streak", manage_response.data)

        log_response = self.client.get(f"/log?month={month_value}&date={today}")
        self.assertEqual(log_response.status_code, 200)
        self.assertIn(b"Log your day", log_response.data)
        self.assertIn(b"Reviewed kana and finished vocab drills.", log_response.data)

        with self.app.app_context():
            updated_category = next(item for item in services.list_categories() if item["id"] == japanese["id"])
            updated_habit = next(item for item in services.list_habits(include_inactive=True) if item["id"] == habit["id"])
            updated_goal = next(item for item in services.list_goals() if item["id"] == goal["id"])
            dashboard = services.get_dashboard_data(selected_date=today, selected_month=month_value)
            updated_log = next(
                item["log"]
                for group in dashboard["log_groups"]
                for item in group["habits"]
                if item["id"] == habit["id"]
            )

        self.assertEqual(updated_category["name"], "Japanese Study")
        self.assertEqual(updated_habit["name"], "Japanese Deep Work")
        self.assertEqual(updated_goal["target_value"], 7)
        self.assertTrue(updated_log["completed"])
        self.assertEqual(updated_log["quantity"], 2)
        self.assertEqual(updated_log["note"], "Reviewed kana and finished vocab drills.")

    def test_redirect_helpers_point_to_split_pages(self):
        today = date.today().isoformat()
        month_value = f"{date.today():%Y-%m}"

        history_response = self.client.get(f"/history?month={month_value}&date={today}")
        self.assertEqual(history_response.status_code, 302)
        self.assertIn("/?month=", history_response.headers["Location"])

        with self.app.app_context():
            habit = next(item for item in services.list_habits(include_inactive=True) if item["name"] == "Japanese Practice")

        habit_response = self.client.get(f"/habit/{habit['id']}?month={month_value}&date={today}")
        self.assertEqual(habit_response.status_code, 302)
        self.assertIn("/analysis", habit_response.headers["Location"])

    def test_delete_routes_remove_records_completely(self):
        today = date.today().isoformat()
        month_value = f"{date.today():%Y-%m}"

        with self.app.app_context():
            category = next(item for item in services.list_categories() if item["name"] == "Anime")
            habit = next(item for item in services.list_habits(include_inactive=True) if item["name"] == "Watch Anime")
            goal = next(item for item in services.list_goals() if item["habit_id"] == habit["id"])

        goal_response = self.client.post(
            f"/goals/{goal['id']}/delete",
            data={
                "return_month": month_value,
                "return_date": today,
                "return_anchor": "manage-goals",
            },
        )
        self.assertEqual(goal_response.status_code, 302)
        self.assertIn("#manage-goals", goal_response.headers["Location"])

        with self.app.app_context():
            self.assertIsNone(services.get_goal(goal["id"]))

        habit_response = self.client.post(
            f"/habits/{habit['id']}/delete",
            data={
                "return_month": month_value,
                "return_date": today,
                "return_anchor": "manage-habits",
            },
        )
        self.assertEqual(habit_response.status_code, 302)
        self.assertIn("#manage-habits", habit_response.headers["Location"])

        with self.app.app_context():
            self.assertIsNone(services.get_habit(habit["id"]))
            self.assertEqual(
                0,
                len([item for item in services.list_goals() if item["habit_id"] == habit["id"]]),
            )

        category_response = self.client.post(
            f"/categories/{category['id']}/delete",
            data={
                "return_month": month_value,
                "return_date": today,
                "return_anchor": "manage-categories",
            },
        )
        self.assertEqual(category_response.status_code, 302)
        self.assertIn("#manage-categories", category_response.headers["Location"])

        with self.app.app_context():
            self.assertIsNone(services.get_category(category["id"]))


if __name__ == "__main__":
    unittest.main()

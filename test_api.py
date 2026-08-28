import unittest

from main import User, app, db


class UserApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["API_KEY"] = "test-key"
        cls.client = app.test_client()
        cls.headers = {"X-API-Key": "test-key"}

    def setUp(self):
        with app.app_context():
            db.session.query(User).delete()
            db.session.commit()

    def test_create_and_list_users(self):
        response = self.client.post(
            "/users", headers=self.headers,
            json={"name": "Ada Lovelace", "email": " ADA@example.com "}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["email"], "ada@example.com")

        response = self.client.get("/users")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total"], 1)
        self.assertEqual(response.json["items"][0]["name"], "Ada Lovelace")

    def test_duplicate_email_is_rejected_on_create_and_update(self):
        self.client.post("/users", headers=self.headers,
                         json={"name": "Ada", "email": "ada@example.com"})
        second = self.client.post(
            "/users", headers=self.headers,
            json={"name": "Grace", "email": "grace@example.com"}
        )
        second_id = second.json["id"]

        response = self.client.post(
            "/users", headers=self.headers,
            json={"name": "Other", "email": "ADA@example.com"}
        )
        self.assertEqual(response.status_code, 409)

        response = self.client.patch(
            f"/users/{second_id}", headers=self.headers,
            json={"email": "ada@example.com"}
        )
        self.assertEqual(response.status_code, 409)

    def test_invalid_patch_is_rejected_without_modifying_user(self):
        created = self.client.post(
            "/users", headers=self.headers,
            json={"name": "Ada", "email": "ada@example.com"}
        )
        user_id = created.json["id"]

        response = self.client.patch(
            f"/users/{user_id}", headers=self.headers, json={"name": None}
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.get(f"/users/{user_id}")
        self.assertEqual(response.json["name"], "Ada")

    def test_missing_user_returns_not_found(self):
        response = self.client.get("/users/999")
        self.assertEqual(response.status_code, 404)

    def test_search_and_stats(self):
        self.client.post("/users", headers=self.headers,
                         json={"name": "Ada", "email": "ada@example.com"})
        self.client.post("/users", headers=self.headers,
                         json={"name": "Grace", "email": "grace@example.com"})

        response = self.client.get("/users?q=grace")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total"], 1)
        self.assertEqual(response.json["items"][0]["name"], "Grace")

        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total_users"], 2)
        self.assertIsNotNone(response.json["latest_signup"])

    def test_write_without_api_key_is_rejected(self):
        response = self.client.post(
            "/users", json={"name": "Ada", "email": "ada@example.com"}
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()

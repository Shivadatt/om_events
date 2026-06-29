from datetime import date, timedelta

from django.test import TestCase


class PlatformTests(TestCase):
    def test_health_and_catalog(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "healthy")
        self.assertEqual(len(self.client.get("/api/categories").json()["data"]), 6)
        self.assertEqual(len(self.client.get("/api/items").json()["data"]), 12)

    def test_search_and_filter(self):
        result = self.client.get("/api/items?category=proposal&q=moonlit").json()["data"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["slug"], "moonlit-marry-me")

    def test_lead_validation_and_creation(self):
        self.assertEqual(self.client.post("/api/leads", {"name": "A"}, content_type="application/json").status_code, 422)
        response = self.client.post("/api/leads", {"name": "Aarav Shah", "phone": "9876543210", "requirements": "<b>Wedding</b>"}, content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_quote_and_pdf(self):
        item = self.client.get("/api/items?category=birthday").json()["data"][0]
        response = self.client.post("/api/quotes", {
            "name": "Kavya Patel", "phone": "9876543210", "event_date": (date.today() + timedelta(days=30)).isoformat(),
            "event_time": "19:30", "location": "Ahmedabad", "items": [{"id": item["id"], "quantity": 2}],
        }, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["quotation"]["subtotal"], item["effective_price"] * 2)
        pdf = self.client.get(response.json()["pdf_url"])
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")

    def test_admin_login_and_protection(self):
        self.assertEqual(self.client.get("/api/admin/stats").status_code, 401)
        login = self.client.post("/api/auth/login", {"email": "admin@omevents.in", "password": "ChangeMe123!"}, content_type="application/json")
        self.assertEqual(login.status_code, 200)
        stats = self.client.get("/api/admin/stats", HTTP_AUTHORIZATION=f"Bearer {login.json()['access_token']}")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()["categories"], 6)


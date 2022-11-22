from django.test import Client, TestCase


class Test(TestCase):
    def test_core_page_uses_correct_template(self):
        guest_client = Client()
        response = guest_client.get('/unexisting_page/')
        self.assertTemplateUsed(response, 'core/404.html')

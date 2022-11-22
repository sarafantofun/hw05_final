from http import HTTPStatus

from django.core.cache import cache
from django.test import Client, TestCase

from ..models import Group, Post, User


class PostURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='Tanya')
        cls.nonauthor = User.objects.create_user(username='NotTanya')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )
        cls.PUBLIC_URLS = {
            '/': ('posts/index.html', HTTPStatus.OK),
            f'/group/{cls.group.slug}/': (
                'posts/group_list.html', HTTPStatus.OK
            ),
            f'/profile/{cls.user}/': ('posts/profile.html', HTTPStatus.OK),
            f'/posts/{cls.post.pk}/': (
                'posts/post_detail.html', HTTPStatus.OK
            ),
        }
        cls.PRIVATE_URLS = {
            f'/posts/{cls.post.pk}/edit/': (
                'posts/create_post.html', HTTPStatus.OK
            ),
            '/create/': ('posts/create_post.html', HTTPStatus.OK),
        }

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(PostURLTests.user)
        self.authorized_nonauthor = Client()
        self.authorized_nonauthor.force_login(PostURLTests.nonauthor)

    def test_public_urls_uses_correct_template(self):
        """Проверка вызываемых шаблонов для каждого адреса"""
        for url, (template, _) in PostURLTests.PUBLIC_URLS.items():
            with self.subTest(url=url):
                response = self.guest_client.get(url)
                self.assertTemplateUsed(response, template)

    def test_private_urls_uses_correct_template(self):
        for url, (template, _) in PostURLTests.PRIVATE_URLS.items():
            with self.subTest(url=url):
                response = self.authorized_client.get(url)
                self.assertTemplateUsed(response, template)

    def test_public_urls_exists_at_desired_location(self):
        """Тест, что все публичные страницы открываются гостем"""
        for url, (_, status) in PostURLTests.PUBLIC_URLS.items():
            with self.subTest(url=url):
                response = self.guest_client.get(url)
                self.assertEqual(response.status_code, status)

    def test_private_urls_exists_at_desired_location(self):
        """Тест, что все приватные страницы открываются
        авторизованным пользователем"""
        for url, (_, status) in PostURLTests.PRIVATE_URLS.items():
            with self.subTest(url=url):
                response = self.authorized_client.get(url)
                self.assertEqual(response.status_code, status)

    def test_unexisting_page_url_exists_at_desired_location(self):
        """Страница /unexisting_page/ вернёт ошибку."""
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_post_create_url_redirect_anonymous_on_auth_login(self):
        """Страница /create/ перенаправит анонимного пользователя
        на страницу логина.
        """
        response = self.guest_client.get('/create/', follow=True)
        self.assertRedirects(
            response, '/auth/login/?next=/create/')

    def test_post_edit_url_redirect_anonymous_on_auth_login(self):
        """Страница /posts/test-post_id/edit/ перенаправит анонимного
        пользователя на страницу логина.
        """
        response = self.client.get(f'/posts/{self.post.pk}/edit/', follow=True)
        self.assertRedirects(
            response, (f'/auth/login/?next=/posts/{self.post.pk}/edit/'))

    def test_post_edit_url_redirect_nonauthor_on_post_detail(self):
        """Страница /posts/test-post_id/edit/ перенаправит не автора поста,
        но авторизованного пользователя на страницу поста.
        """
        response = self.authorized_nonauthor.get(
            f'/posts/{self.post.pk}/edit/', follow=True
        )
        self.assertRedirects(
            response, (f'/posts/{self.post.pk}/'))

import shutil
import tempfile
from http import HTTPStatus

from django import forms
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Follow, Group, Post, User

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPagesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='tanya')
        cls.author2 = User.objects.create_user(username='NotTanya')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.group2 = Group.objects.create(
            title='Неправильная группа',
            slug='test2-slug',
            description='Тестовое описание2',
        )
        cls.small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.small_gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            group=cls.group,
            text='Тестовый пост',
            image=cls.uploaded
        )

        cls.PUBLIC_URLS = {
            reverse('posts:index'): ('posts/index.html', HTTPStatus.OK),
            reverse('posts:group_posts', kwargs={'slug': cls.group.slug}): (
                'posts/group_list.html', HTTPStatus.OK
            ),
            reverse('posts:profile', kwargs={'username': cls.user}): (
                'posts/profile.html', HTTPStatus.OK
            ),
            reverse('posts:post_detail', kwargs={'post_id': cls.post.pk}): (
                'posts/post_detail.html', HTTPStatus.OK
            ),
        }
        cls.PRIVATE_URLS = {
            reverse('posts:post_edit', kwargs={'post_id': cls.post.pk}): (
                'posts/create_post.html', HTTPStatus.OK
            ),
            reverse('posts:post_create'): (
                'posts/create_post.html', HTTPStatus.OK
            ),
        }

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(PostPagesTests.user)
        self.authorized_author2 = Client()
        self.authorized_author2.force_login(PostPagesTests.author2)

    def test_public_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        for reverse_name, (template, _) in PostPagesTests.PUBLIC_URLS.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_private_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        for reverse_name, (template, _) in PostPagesTests.PRIVATE_URLS.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_public_pages_show_correct_context(self):
        """Тест контекста всех публичных страниц"""
        for reverse_name, (_, _) in PostPagesTests.PUBLIC_URLS.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                if 'page_obj' in response.context:
                    first_object = response.context['page_obj'][0]
                else:
                    first_object = response.context['post']
                self.assertEqual(
                    first_object.group.title, PostPagesTests.group.title
                )
                self.assertEqual(
                    first_object.group.description,
                    PostPagesTests.group.description
                )
                self.assertEqual(
                    first_object.group.slug, PostPagesTests.group.slug
                )
                self.assertEqual(first_object.text, PostPagesTests.post.text)
                self.assertEqual(
                    first_object.author.username,
                    PostPagesTests.post.author.username
                )
                self.assertEqual(first_object.image, 'posts/small.gif')

    def test_private_pages_show_correct_context(self):
        """Тест контекста всех приватных страниц"""
        for reverse_name, (_, _) in PostPagesTests.PRIVATE_URLS.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                form_fields = {
                    'text': forms.fields.CharField,
                    'group': forms.fields.ChoiceField,
                }
                for value, expected in form_fields.items():
                    with self.subTest(value=value):
                        form_field = (
                            response.context.get('form').fields.get(value)
                        )
                        self.assertIsInstance(form_field, expected)

    def test_post_not_in_another_group(self):
        """Проверка, что пост не попал в чужую группу."""
        response = (self.authorized_client.get(
            reverse(
                'posts:group_posts',
                kwargs={'slug': PostPagesTests.group2.slug}
            )
        ))
        object = response.context['page_obj']
        self.assertNotIn(PostPagesTests.post, object)

    def test_post_not_in_another_profile(self):
        """Проверка, что пост не попал в профиль другого автора."""
        response = (self.authorized_author2.get(
            reverse(
                'posts:profile',
                kwargs={'username': PostPagesTests.author2}
            )
        ))
        object = response.context['page_obj']
        self.assertNotIn(PostPagesTests.post, object)

    def test_cache_index(self):
        """Проверка хранения и очищения кэша для index."""
        response = self.authorized_client.get(reverse('posts:index'))
        Post.objects.create(
            text='Новейший текст',
            author=self.user,
        )
        response_old = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(response_old.content, response.content)
        cache.clear()
        response_new = self.authorized_client.get(reverse('posts:index'))
        self.assertNotEqual(response_old.content, response_new.content)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='tanya')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        Post.objects.bulk_create(
            [
                Post(
                    author=cls.user,
                    group=cls.group,
                    text='Тестовый пост' + str(i),
                )
                for i in range(settings.NUM_PAGE + settings.NUM_PAGE2)
            ]
        )
        cls.URLS = [
            reverse('posts:index'),
            reverse('posts:group_posts', kwargs={'slug': cls.group.slug}),
            reverse('posts:profile', kwargs={'username': cls.user}),
        ]

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(PaginatorViewsTest.user)

    def test_paginator(self):
        for reverse_name in PaginatorViewsTest.URLS:
            with self.subTest(reverse_name=reverse_name):
                responses_numpages = {
                    self.authorized_client.get(reverse_name):
                    settings.NUM_PAGE,
                    self.authorized_client.get((reverse_name) + '?page=2'):
                    settings.NUM_PAGE2,
                }
                for response, numpages in responses_numpages.items():
                    with self.subTest(response=response):
                        self.assertEqual(
                            len(response.context['page_obj']), numpages
                        )


class FollowViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user1 = User.objects.create_user(username='Tanya')
        cls.user2 = User.objects.create_user(username='notTanya')
        cls.user3 = User.objects.create_user(username='somebogy')
        cls.post1 = Post.objects.create(
            author=FollowViewsTest.user1,
            text='Тестовый пост Юзера1',
        )
        cls.reverse_follow_user1 = reverse('posts:profile_follow', kwargs={
            'username': FollowViewsTest.user1
        })
        cls.reverse_unfollow_user1 = reverse('posts:profile_unfollow', kwargs={
            'username': FollowViewsTest.user1
        })
        cls.reverse_follow_index = reverse('posts:follow_index')

    def setUp(self):
        cache.clear()
        self.authorized_client = Client()
        self.authorized_client.force_login(FollowViewsTest.user1)
        self.authorized_client2 = Client()
        self.authorized_client2.force_login(FollowViewsTest.user2)
        self.authorized_client3 = Client()
        self.authorized_client3.force_login(FollowViewsTest.user3)

    def test_profile_follow_and_unfollow(self):
        """Авторизованный пользователь может подписываться на
        других пользователей и удалять их из подписок.
        """
        self.authorized_client3.get(FollowViewsTest.reverse_follow_user1)
        first_object = Follow.objects.get(id=1)
        self.assertEqual(first_object.author, FollowViewsTest.user1)
        self.assertEqual(first_object.user, FollowViewsTest.user3)
        follow_count = Follow.objects.count()
        self.authorized_client3.get(FollowViewsTest.reverse_unfollow_user1)
        follow_count2 = Follow.objects.count()
        self.assertNotEqual(follow_count, follow_count2)

    def test_new_post_in_right_follow_location(self):
        """Новая запись пользователя появляется в ленте тех,
        кто на него подписан.
        """
        self.authorized_client3.get(FollowViewsTest.reverse_follow_user1)
        response = self.authorized_client3.get(
            FollowViewsTest.reverse_follow_index
        )
        first_object = response.context['page_obj'][0]
        self.assertEqual(first_object.text, FollowViewsTest.post1.text)

    def test_new_post_not_in_unfollow_location(self):
        """Новая запись пользователя не появляется в ленте тех,
        кто не подписан.
        """
        response = self.authorized_client2.get(
            FollowViewsTest.reverse_follow_index
        )
        self.assertNotIn(
            FollowViewsTest.post1.text, response.context['page_obj']
        )

    def test_author_cant_follow_himself(self):
        """Проверка, что нельзя подписаться на самого себя."""
        self.authorized_client.get(FollowViewsTest.reverse_follow_user1)
        follow_count = Follow.objects.count()
        self.assertEqual(follow_count, 0)

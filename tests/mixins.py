import json
import os
import random
import typing

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from posts.models import Comment, Post
from tests.factories import CommentFactory, PostFactory, UserFactory

User = get_user_model()

BatchStubUsers = typing.List

IMAGES_FOR_TEST_NAMES = [
    "image_1.jpeg",
    "image_2.jpg"
]


class ProxyFactories(object):
    User = UserFactory
    Post = PostFactory
    Comment = CommentFactory


class SendEndpointDetailRequestMixin:
    def send_endpoint_detail_request(self, client: APIClient, status__: int, **kwargs) -> Response:
        detail_url = reverse_lazy(self.endpoint_detail, kwargs=kwargs)   # noqa
        response = client.get(detail_url)
        assert response.status_code == status__
        return response


class CheckUserDataMixin(SendEndpointDetailRequestMixin):
    def check_user_data(self, client: APIClient, user: User, content: typing.Optional[typing.Dict] = None) -> None:
        if not content:
            response = self.send_endpoint_detail_request(client, status.HTTP_200_OK, pk=user.pk)
            content = json.loads(response.content)
        assert content["id"] == user.pk
        assert content["username"] == user.username


class RegisterUsersMixin(CheckUserDataMixin, ProxyFactories):
    REGISTER_USERS_ENDPOINT: typing.Final = "users:account-list"

    def parse_stub_user(self, user):
        return {
            "username": user.username,
            "email": user.email,
            "password": user.password,
        }

    def get_validated_content(self, client: APIClient, data: typing.Dict) -> typing.Dict:
        response = client.post(reverse_lazy(self.REGISTER_USERS_ENDPOINT), data=data)
        assert response.status_code == status.HTTP_201_CREATED
        return json.loads(response.content)

    def register_users(self, client: APIClient, users_count: int, stub: bool = False) -> BatchStubUsers:
        content_list = []
        users = self.User.stub_batch(users_count)
        for user in users:
            data = self.parse_stub_user(user)
            content_list.append(self.get_validated_content(client, data))
        users_created = User.objects.filter(username__in=[user.username for user in users])
        for user, content in zip(users_created, content_list):
            self.check_user_data(client, user, content=content)
        return users if stub else users_created


class RegisterPostMixin(ProxyFactories):
    REGISTER_POSTS_ENDPOINT: typing.Final = "posts:posts-list"

    def register_post(self, client: APIClient, author: User) -> Post:
        client.force_authenticate(author)
        data = {
            "signature": self.Post.stub().signature,
        }
        image_1 = os.path.join(settings.STATICFILES_DIRS[0], settings.TEST_IMAGES_DIR, IMAGES_FOR_TEST_NAMES[0])
        image_2 = os.path.join(settings.STATICFILES_DIRS[0], settings.TEST_IMAGES_DIR, IMAGES_FOR_TEST_NAMES[1])
        with open(image_1, "rb") as image_1:
            with open(image_2, "rb") as image_2:
                data["image1"] = image_1
                data["image2"] = image_2
                response = client.post(reverse_lazy(self.REGISTER_POSTS_ENDPOINT), data=data)
                assert response.status_code == status.HTTP_201_CREATED
        client.force_authenticate()
        return Post.objects.get(signature=data["signature"])   # noqa


class RegisterLikeMixin(RegisterPostMixin):
    def register_like(self, client: APIClient, author: User, post: typing.Optional[Post] = None) \
            -> typing.Tuple[User, int]:
        post_id = post.id if post else self.register_post(client, author).pk   # noqa
        data = {"post_id": post_id}  # noqa
        client.force_authenticate(author)
        response = client.post(reverse_lazy(self.endpoint_list), data=data)   # noqa
        assert response.status_code == status.HTTP_201_CREATED
        client.force_authenticate()
        return author, post_id


class RegisterCommentMixin(RegisterPostMixin):
    def register_comment(self, client: APIClient, author: User, post: typing.Optional[Post] = None) -> User:
        post_id = post.id if post else self.register_post(client, author).pk   # noqa
        client.force_authenticate(author)
        data = {
            "post_id": post_id,
            "comment": self.Comment.stub().comment
        }
        response = client.post(reverse_lazy(self.endpoint_list), data=data)   # noqa
        client.force_authenticate()
        assert response.status_code == status.HTTP_201_CREATED
        return Comment.objects.first()   # noqa


class RegisterObjectsMixin(RegisterUsersMixin, RegisterLikeMixin, RegisterCommentMixin):
    pass


class IterableFollowingRelationsMixin(object):
    def get_iterable(self, client: APIClient, stub: bool = False) -> typing.Iterable:
        relations = []

        for user in super().get_iterable(client, False):   # noqa
            client.force_authenticate(user)
            following = random.choice(User.objects.exclude(username=user.username))
            response = client.post(reverse_lazy(self.endpoint_list), data={"following": following.pk})   # noqa
            assert response.status_code == status.HTTP_201_CREATED
            assert user.following.count() == 1
            relations.append((user, following))

        return relations  # noqa


class AssertContentKeysMixin(object):
    def assert_keys(self, content: typing.Dict, needed_keys: typing.Tuple) -> None:
        keys = list(content.keys())
        for key in needed_keys:
            assert key in keys


class AssertResponseMixin(AssertContentKeysMixin):
    def assert_response(self, response: Response, status__: typing.Optional[int] = status.HTTP_200_OK,
                        needed_keys: typing.Optional[typing.Tuple] = None) -> typing.Dict:
        content = json.loads(response.content)
        assert response.status_code == status__
        if needed_keys:
            self.assert_keys(content, needed_keys)
        return content


class AssertPaginatedResponseMixin(AssertResponseMixin):
    def assert_paginated_response(self, response: Response) -> typing.Dict:
        content = self.assert_response(response, needed_keys=("count", "next", "previous", "results"))
        assert content["count"] == self.list_tests_count   # noqa
        assert len(content["results"]) == self.list_tests_count   # noqa
        return content
import json
import random
import secrets
import string
import typing

import pytest
import pytz
from django.contrib.auth import authenticate, get_user_model
from django.urls import reverse_lazy
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIClient

from tests import AssertPaginatedResponseMixin, AssertResponseMixin, GenericTest
from users.models import ExwonderUser

User = get_user_model()
pytestmark = [pytest.mark.django_db]

ResponseContent = typing.Dict


class TestUsersCreation(GenericTest):
    endpoint_list = "users:account-list"
    endpoint_detail = "users:account-detail"

    def test_users_creation(self, api_client):
        super().make_test(api_client)


class TestUsersMy(AssertResponseMixin, GenericTest):
    endpoint_detail = "users:account-me"

    def test_users_my(self, api_client):
        super().make_test(api_client)

    def case_test(self, client: APIClient, instance: User) -> typing.Tuple[Response, User]:
        client.force_authenticate(instance)
        return self.send_endpoint_detail_request(client, status.HTTP_200_OK), instance

    def assert_case_test(self, response: Response, *args) -> None:
        self.assert_response(response, needed_keys=("user", "availible_timezones"))


class TestUsersSearch(AssertPaginatedResponseMixin, GenericTest):
    endpoint_list = "users:account-list"

    def test_users_search(self, api_client):
        super().make_test(api_client)

    def __generate_random_search_users(self, users_count: int) -> typing.Tuple[typing.Any, ...]:
        return tuple(
            self.User.stub(username="searchu" + "".join(secrets.choice(string.digits) for _ in range(3)))
            for _ in range(users_count)
        )

    def case_test(self, client: APIClient, instance: User) -> Response:
        users = self.User.stub_batch(self.list_tests_count - 2)
        search_users = self.__generate_random_search_users(2)
        search_users[0].is_private = True
        users.extend(search_users)
        self.register_users(client, self.list_tests_count, users=users)
        client.force_authenticate(instance)
        return client.get(f"{reverse_lazy(self.endpoint_list)}?search=searchu")

    def assert_case_test(self, response: Response, *args) -> None:
        self.assert_paginated_response(response, 1)

    def after_assert(self, client: APIClient, *args) -> None:
        User.objects.filter(username__startswith="searchu").delete()


class TestUsersFull(AssertResponseMixin, GenericTest):
    endpoint_list = "users:full-user"

    def test_users_full(self, api_client):
        super().make_test(api_client)

    def case_test(self, client: APIClient, instance: User) -> Response:
        user_for_check = random.choice(User.objects.filter())
        self.register_post(client, user_for_check)
        client.force_authenticate(instance)
        return client.get(f"{reverse_lazy(self.endpoint_list)}?username={user_for_check.username}&fields=all")

    def assert_case_test(self, response: Response, *args) -> None:
        self.assert_response(
            response,
            needed_keys=(
                "id",
                "username",
                "name",
                "description",
                "avatar",
                "posts_count",
                "is_followed",
                "followers_count",
                "followings_count",
            ),
        )


class TestUsersUpdate(GenericTest):
    endpoint_list = "users:account-list"
    endpoint_detail = "users:account-me"
    endpoint_update = "users:account-update"

    def test_users_update(self, api_client):
        super().make_test(api_client)

    def case_test(self, client: APIClient, instance: User) -> typing.Tuple[Response, APIClient, User]:
        client.force_authenticate(instance)
        data = {
            "email": self.User.stub().email,
            "timezone": random.choice(pytz.common_timezones),
            "name": "yea, test",
            "description": "test desc",
            "is_2fa_enabled": True,
            "is_private": True,
            "comments_private_status": ExwonderUser.CommentsPrivateStatus.FOLLOWERS,
        }
        return (
            client.patch(reverse_lazy(self.endpoint_update), data=data),
            client,
            User.objects.get(username=instance.username),
        )

    def assert_case_test(self, response: Response, *args) -> None:
        assert response.status_code == status.HTTP_204_NO_CONTENT
        client, user = args[0], args[1]
        client.force_authenticate(user)
        response = client.get(reverse_lazy(self.endpoint_detail))
        content = json.loads(response.content)
        assert content["user"]["id"] == user.pk
        assert content["user"]["username"] == user.username
        assert content["user"]["name"] == user.name
        assert content["user"]["description"] == user.desc
        assert content["user"]["email"] == user.email
        assert content["user"]["timezone"] == user.timezone
        assert content["user"]["is_2fa_enabled"] == user.is_2fa_enabled
        assert content["user"]["is_private"] == user.is_private
        assert content["user"]["comments_private_status"] == user.comments_private_status
        return content


class TestUsersLogin(GenericTest):
    endpoint_list = "users:account-list"
    endpoint_detail = "users:account-detail"
    endpoint_login = "users:account-login"

    def test_users_login(self, api_client):
        super().make_test(api_client, stub=True)

    def case_test(self, client: APIClient, instance: User) -> Response:
        data = {"username": instance.username, "password": instance.password}
        return client.post(reverse_lazy(self.endpoint_login), data=data)

    def assert_case_test(self, response: Response, *args) -> None:
        content = json.loads(response.content)
        assert response.status_code == status.HTTP_200_OK
        keys = list(content.keys())
        assert "token" in keys and "user_id" in keys


class TestUsersPasswordChange(GenericTest):
    endpoint_list = "users:account-list"
    endpoint_detail = "users:account-detail"
    endpoint_password_change = "users:password-change"

    def test_users_password_change(self, api_client):
        super().make_test(api_client, stub=True)

    def case_test(self, client: APIClient, instance: User) -> typing.Tuple[Response, str, str]:
        client.force_authenticate(User.objects.get(username=instance.username))
        new_password = self.User.stub().password
        data = {"old_password": instance.password, "new_password1": new_password, "new_password2": new_password}
        return client.post(reverse_lazy(self.endpoint_password_change), data=data), instance.username, new_password

    def assert_case_test(self, response: Response, *args) -> None:
        assert response.status_code == status.HTTP_200_OK
        assert authenticate(username=args[0], password=args[1])

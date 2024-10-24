from typing import Optional

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.validators import MinLengthValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


def get_uploaded_avatar_path(instance: Optional['ExwonderUser'] = None, filename: Optional[str] = None) -> str:
    return f"{settings.CUSTOM_USER_AVATARS_DIR}/{filename}"


class ExwonderUserManager(BaseUserManager):
    def create_user(self, username: str, email: str, avatar: str, timezone: str, password: Optional[str] = None) \
            -> 'ExwonderUser':
        if not email:
            raise ValueError("Users must have an email address")

        user: 'ExwonderUser' = self.model(
            username=username,
            email=self.normalize_email(email),
            avatar=avatar,
            timezone=timezone
        )

        user.set_password(password)
        user.save(using=self._db)
        return user


class ExwonderUser(AbstractBaseUser):
    username = models.CharField(
        verbose_name=_("Имя пользователя"),
        max_length=16,
        unique=True,
        help_text=_("Не более 16 символов, не менее 5. Буквы, цифры, @/./+/-/_."),
        validators=[UnicodeUsernameValidator(), MinLengthValidator(5)],
        error_messages={
            "unique": _("Пользователь с таким именем уже существует."),
        }
    )
    email = models.EmailField(
        verbose_name=_('Почта'),
        unique=True,
        help_text=_("Электронная почта для аккаунта."),
        null=True
    )
    avatar = models.ImageField(
        verbose_name=_("Аватарка"),
        upload_to=get_uploaded_avatar_path,
        default=settings.DEFAULT_USER_AVATAR_PATH
    )
    timezone = models.CharField(
        verbose_name=_("Временная зона"),
        max_length=64,
        default=settings.DEFAULT_USER_TIMEZONE
    )
    date_joined = models.DateTimeField(verbose_name=_('Время регистрации'), auto_now_add=True)
    penultimate_login = models.DateTimeField(verbose_name=_("Предпоследний вход"), blank=True, null=True)
    is_2fa_enabled = models.BooleanField(verbose_name=_('Включена ли 2FA'), default=False)

    USERNAME_FIELD = "username"
    objects = ExwonderUserManager()

    class Meta:
        verbose_name = _("Пользователь")
        verbose_name_plural = _("Пользователи")

        ordering = "pk",

        db_table = "exwonder_users"

    def __str__(self):
        return f"{self.username}"


class Follow(models.Model):
    follower = models.ForeignKey(ExwonderUser, related_name="following", on_delete=models.CASCADE)
    following = models.ForeignKey(ExwonderUser, related_name="followers", on_delete=models.CASCADE)

    class Meta:
        ordering = "-pk",

    def __str__(self):
        return f"{self.follower.pk} following for {self.following.pk}"   # noqa

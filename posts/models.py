from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models

User = get_user_model()


def post_images_upload(instance: 'PostImage', filename: str) -> str:
    return f"{settings.POSTS_IMAGES_DIR}/{filename}"


class PostImage(models.Model):
    image = models.ImageField(upload_to=post_images_upload)
    post = models.ForeignKey("Post", related_name="images", on_delete=models.CASCADE)

    def __str__(self):
        return f"Image for {self.post.pk}."   # noqa


class Post(models.Model):
    author = models.ForeignKey(User, related_name="posts", on_delete=models.CASCADE)
    signature = models.CharField(max_length=512, default="")
    time_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = "-id",

    def __str__(self):
        return f"{self.pk} post."


class PostLike(models.Model):
    author = models.ForeignKey(User, related_name="likes", on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name="likes", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.author.pk} like for {self.post.pk} post."   # noqa


class Comment(models.Model):
    author = models.ForeignKey(User, related_name="comments", on_delete=models.CASCADE)
    comment = models.TextField(max_length=2048, validators=(MinLengthValidator(10),))
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    time_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = "-time_added",

    def __str__(self):
        return f"{self.author.pk} comment for {self.post.pk}."   # noqa


class CommentLike(models.Model):
    author = models.ForeignKey(User, related_name="comment_likes", on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, related_name="likes", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.author.pk} like for {self.post.pk} comment."   # noqa


class Saved(models.Model):
    owner = models.ForeignKey(User, related_name="saved_posts", on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name="saved_by", on_delete=models.CASCADE)
    time_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = "-time_added", "-id"

    def __str__(self):
        return f"Saved post {self.post.pk} by {self.owner.pk}"   # noqa

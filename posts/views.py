from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from posts.models import Comment, CommentLike, Post, PostLike, Saved
from posts.permissions import IsOwnerOrCreateOnly, IsOwnerOrReadOnly
from posts.serializers import (
    CommentIDSerializer,
    CommentLikeSerializer,
    CommentSerializer,
    PostIDSerializer,
    PostLikeSerializer,
    PostRequestSerializer,
    PostResponseSerializer,
    SavedSerializer,
)
from posts.services import (
    BaseLikeViewSet,
    CreateModelMixin,
    annotate_likes_count_and_is_liked_comments_queryset,
    filter_posts_queryset_by_author,
    filter_posts_queryset_by_top,
    get_full_annotated_posts_queryset,
)
from users.models import ExwonderUser
from users.serializers import DetailedCodeSerializer

User = get_user_model()


@extend_schema_view(
    create=extend_schema(
        request=PostRequestSerializer,
        responses={
            status.HTTP_201_CREATED: PostRequestSerializer,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
        },
        description="Endpoint to create post.",
    ),
    list=extend_schema(
        request=None,
        parameters=[
            OpenApiParameter(
                name="user", description="Author of posts (username). Default is request sender.", type=str
            ),
            OpenApiParameter(
                name="top",
                description="Filter posts by top. "
                "Valid values is 'likes', 'recent', 'updates' and 'recommended'. "
                "Cant be used with 'user'.",
                type=str,
            ),
        ],
        responses={status.HTTP_200_OK: PostResponseSerializer, status.HTTP_403_FORBIDDEN: DetailedCodeSerializer},
        description="Endpoint to get posts of user or you or some posts tops.",
    ),
    retrieve=extend_schema(
        request=None,
        responses={
            status.HTTP_200_OK: PostResponseSerializer,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to get post info.",
    ),
    destroy=extend_schema(
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to delete your post.",
    ),
)
class PostViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PostResponseSerializer
    permission_classes = permissions.IsAuthenticated, IsOwnerOrReadOnly
    lookup_url_kwarg = "id"

    def get_queryset(self):
        queryset = Post.objects.filter()  # noqa

        if self.action != "retrieve":
            queryset, has_filtered = filter_posts_queryset_by_top(self.request, queryset)
            if not has_filtered:
                queryset = filter_posts_queryset_by_author(
                    self.request, queryset, self.request.query_params.get("user", None)
                )
        else:
            queryset = get_full_annotated_posts_queryset(self.request, queryset)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PostRequestSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        key = settings.POSTS_RECENT_TOP_CACHE_NAME
        cache.delete(key)


@extend_schema_view(
    create=extend_schema(
        request=PostIDSerializer,
        responses={
            status.HTTP_201_CREATED: PostLikeSerializer,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to like some post.",
    ),
    destroy=extend_schema(
        request=None,
        responses={status.HTTP_204_NO_CONTENT: None, status.HTTP_404_NOT_FOUND: DetailedCodeSerializer},
        description="Endpoint to delete like from post.",
    ),
)
class PostLikeViewSet(BaseLikeViewSet):
    serializer_class = PostLikeSerializer
    queryset = PostLike.objects.filter()  # noqa
    lookup_url_kwarg = "post_id"
    entity_model = Post


@extend_schema_view(
    create=extend_schema(
        request=PostIDSerializer,
        responses={
            status.HTTP_201_CREATED: CommentSerializer,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to create comment to post.",
    ),
    list=extend_schema(
        request=None,
        parameters=[OpenApiParameter(name="post_id", description="Post id to get comments.", type=int)],
        responses={
            status.HTTP_200_OK: CommentSerializer,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to get comments of post.",
    ),
    destroy=extend_schema(
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to delete your comment.",
    ),
)
class CommentViewSet(CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = CommentSerializer
    permission_classes = permissions.IsAuthenticated, IsOwnerOrReadOnly
    lookup_url_kwarg = "id"

    def get_queryset(self):
        if self.action == "list":
            serializer = PostIDSerializer(data=self.request.query_params)
            serializer.is_valid(raise_exception=True)
            queryset = get_object_or_404(Post, pk=serializer.validated_data["post_id"]).comments.select_related(
                "author"
            )  # noqa
            return annotate_likes_count_and_is_liked_comments_queryset(self.request, queryset)
        elif self.action == "destroy":
            return Comment.objects.filter()  # noqa

    def perform_create(self, request: Request, serializer: serializers.ModelSerializer) -> None:
        post_id = self.get_and_validate_post_id(request)
        author = Post.objects.select_related("author").get(pk=post_id).author

        match author.comments_private_status:
            case ExwonderUser.CommentsPrivateStatus.FOLLOWERS:
                if not author.followers.select_related("follower").filter(follower=request.user).exists():
                    raise serializers.ValidationError(
                        "You can leave your comment here only if you are follower of author of this post."
                    )
            case ExwonderUser.CommentsPrivateStatus.NONE:
                raise serializers.ValidationError("You cant leave comments to posts of this author.")

        super().perform_create(request, serializer)


@extend_schema_view(
    create=extend_schema(
        request=CommentIDSerializer,
        responses={
            status.HTTP_201_CREATED: CommentLikeSerializer,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to like some comment.",
    ),
    destroy=extend_schema(
        request=None,
        responses={status.HTTP_204_NO_CONTENT: None, status.HTTP_404_NOT_FOUND: DetailedCodeSerializer},
        description="Endpoint to delete like from comment.",
    ),
)
class CommentLikeViewSet(BaseLikeViewSet):
    serializer_class = CommentLikeSerializer
    queryset = CommentLike.objects.filter()  # noqa
    lookup_url_kwarg = "comment_id"
    entity_model = Comment


@extend_schema_view(
    list=extend_schema(
        request=None, responses={status.HTTP_200_OK: SavedSerializer}, description="Endpoint to view your saved posts."
    ),
    create=extend_schema(
        request=PostIDSerializer,
        responses={status.HTTP_201_CREATED: None, status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer},
        description="Endpoint to add post to saved posts.",
    ),
    destroy=extend_schema(
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
            status.HTTP_404_NOT_FOUND: DetailedCodeSerializer,
        },
        description="Endpoint to delete post from saved.",
    ),
)
class SavedViewSet(CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    author_field = "owner"

    serializer_class = SavedSerializer
    permission_classes = permissions.IsAuthenticated, IsOwnerOrCreateOnly
    lookup_url_kwarg = "id"

    def get_queryset(self):
        queryset = self.request.user.saved_posts.filter()
        return get_full_annotated_posts_queryset(self.request, queryset, annotated_field_prefix="post").order_by(
            "-time_added"
        )

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        instance = Saved.objects.filter(
            owner=request.user, post=get_object_or_404(Post, pk=self.kwargs[self.lookup_url_kwarg])
        )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, request: Request, serializer) -> None:
        instance = Saved.objects.filter(owner=request.user, post=get_object_or_404(Post, pk=request.data["post_id"]))
        if not instance.exists():
            super().perform_create(request, serializer)


@extend_schema_view(
    pin=extend_schema(
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_401_UNAUTHORIZED: DetailedCodeSerializer,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
        },
        description="Endpoint to pin your post.",
    ),
    unpin=extend_schema(
        request=None,
        responses={
            status.HTTP_204_NO_CONTENT: None,
            status.HTTP_400_BAD_REQUEST: DetailedCodeSerializer,
            status.HTTP_401_UNAUTHORIZED: DetailedCodeSerializer,
            status.HTTP_403_FORBIDDEN: DetailedCodeSerializer,
        },
        description="Endpoint to unpin your post.",
    ),
)
class PinPostsViewSet(viewsets.GenericViewSet):
    lookup_url_kwarg = "pk"
    permission_classes = permissions.IsAuthenticated, IsOwnerOrReadOnly

    @action(methods=["post"], detail=True, url_name="pin")
    def pin(self, request: Request, pk: int) -> Response:
        post = Post.objects.get(pk=pk)
        self.check_object_permissions(request, post)
        post.pinned = True
        post.clean()
        post.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["post"], detail=True, url_name="unpin")
    def unpin(self, request: Request, pk: int) -> Response:
        post = Post.objects.get(pk=pk)
        self.check_object_permissions(request, post)
        post.pinned = False
        post.clean()
        post.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

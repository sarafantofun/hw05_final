from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_page

from .forms import CommentForm, PostForm
from .models import Follow, Group, Post, User
from .utils import get_page_obj


@cache_page(20, key_prefix='index_page')
def index(request):
    post_list = Post.objects.select_related('group', 'author').all()
    return render(
        request,
        'posts/index.html',
        {'page_obj': get_page_obj(post_list, request), }
    )


def group_posts(request, slug):
    group = get_object_or_404(Group, slug=slug)
    posts = group.posts.select_related('author').all()
    return render(
        request,
        'posts/group_list.html',
        {'group': group, 'page_obj': get_page_obj(posts, request), }
    )


def profile(request, username):
    author = get_object_or_404(User, username=username)
    userposts = author.posts.select_related('group').all()
    if request.user.is_authenticated:
        if request.user.follower.filter(author=author).exists():
            following = True
        else:
            following = False
        return render(
            request,
            'posts/profile.html',
            {
                'author': author,
                'page_obj': get_page_obj(userposts, request),
                'following': following,
            }
        )
    return render(
        request,
        'posts/profile.html',
        {
            'author': author,
            'page_obj': get_page_obj(userposts, request),
        }
    )


def post_detail(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None, )
    comments = post.comments.select_related('author').all()
    return render(
        request,
        'posts/post_detail.html',
        {'form': form, 'post': post, 'comments': comments}
    )


@login_required
def post_create(request):
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
    )
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('posts:profile', username=request.user.username)
    return render(request, 'posts/create_post.html', {'form': form, })


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if request.user != post.author:
        return redirect('posts:post_detail', post_id=post_id)
    form = PostForm(
        request.POST or None,
        files=request.FILES or None,
        instance=post,
    )
    if form.is_valid():
        form.save()
        return redirect('posts:post_detail', post_id=post_id)
    return render(
        request,
        'posts/create_post.html',
        {'form': form, 'is_edit': True, 'post': post, }
    )


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('posts:post_detail', post_id=post_id)


@login_required
def follow_index(request):
    posts_following_authors = Post.objects.filter(
        author__following__user=request.user
    )
    return render(
        request,
        'posts/follow.html',
        {'page_obj': get_page_obj(posts_following_authors, request)},
    )


@login_required
def profile_follow(request, username):
    author = get_object_or_404(User, username=username)
    if request.user != author:
        Follow.objects.get_or_create(author=author, user=request.user)
        return redirect('posts:profile', username=username)
    return redirect('posts:profile', username=username)


@login_required
def profile_unfollow(request, username):
    author = get_object_or_404(User, username=username)
    Follow.objects.filter(
        author=author, user=request.user
    ).delete()
    return redirect('posts:profile', username=username)

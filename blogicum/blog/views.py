from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, UpdateView

from .forms import PostForm, ProfileForm, CommentForm
from .models import Category, Comment, Post

User = get_user_model()


class CommentCreateView(LoginRequiredMixin, CreateView):
    post_obj = None
    model = Comment
    form_class = CommentForm

    def get(self, request, *args, **kwargs):
        return redirect('blog:post_detail', pk=kwargs['pk'])

    def dispatch(self, request, *args, **kwargs):
        self.post_obj = get_object_or_404(Post, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = self.post_obj
        response = super().form_valid(form)

        self.post_obj.comment_count = self.post_obj.comments.count()
        self.post_obj.save(update_fields=['comment_count'])
        return response

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'pk': self.kwargs['pk']})


class CommentDeleteView(DeleteView):
    model = Comment
    template_name = 'blog/comment.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user != self.get_object().author:
            return redirect('blog:post_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        comment = self.get_object()
        post_obj = comment.post
        response = super().delete(request, *args, **kwargs)

        post_obj.comment_count = post_obj.comments.count()
        post_obj.save(update_fields=['comment_count'])

        return response

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['post_id']}
        )


class CommentUpdateView(UpdateView):
    form_class = CommentForm
    model = Comment
    template_name = 'blog/comment.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user != self.get_object().author:
            return redirect('blog:post_detail', pk=kwargs['pk'])
        post_obj = get_object_or_404(Post, pk=kwargs['post_id'])
        if post_obj != self.get_object().post:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            'blog:post_detail',
            kwargs={'pk': self.kwargs['post_id']}
        )


class PostCreateView(LoginRequiredMixin, CreateView):
    form_class = PostForm
    model = Post
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostDeleteView(DeleteView):
    model = Post
    template_name = 'blog/create.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user != self.get_object().author:
            return redirect('blog:post_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PostForm(instance=self.get_object())
        return context

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


class PostUpdateView(UpdateView):
    form_class = PostForm
    model = Post
    template_name = 'blog/create.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user != self.get_object().author:
            return redirect('blog:post_detail', pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    model = User
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse(
            'blog:profile',
            kwargs={'username': self.request.user.username}
        )


def get_published_posts():
    posts = Post.objects.select_related(
        'category', 'location', 'author'
    ).filter(
        pub_date__lte=timezone.now(),
        is_published=True,
        category__is_published=True
    )
    return posts


def get_page_obj(object_list, per_page, request):
    paginator = Paginator(object_list, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return page_obj


# Create your views here.
def index(request):
    template = 'blog/index.html'
    posts = get_published_posts()
    page_obj = get_page_obj(posts, 10, request)
    context = {'page_obj': page_obj}
    return render(request, template, context)


def post_detail(request, pk):
    template = 'blog/detail.html'
    post = get_object_or_404(
        Post.objects.select_related('category', 'location', 'author'),
        pk=pk
    )
    if post.author != request.user and (
            post.pub_date > timezone.now()
            or not post.is_published
            or not post.category.is_published
    ):
        raise Http404
    form = CommentForm()
    comments = post.comments.select_related('author')
    context = {'post': post, 'form': form, 'comments': comments}
    return render(request, template, context)


def category_posts(request, category_slug):
    template = 'blog/category.html'
    category = get_object_or_404(
        Category.objects.all().filter(is_published=True), slug=category_slug
    )
    posts = category.posts.select_related(
        'category', 'location', 'author'
    ).filter(
        pub_date__lte=timezone.now(),
        is_published=True
    ).order_by('-pub_date')
    page_obj = get_page_obj(posts, 10, request)
    context = {'category': category, 'page_obj': page_obj}
    return render(request, template, context)


def profile(request, username):
    template = 'blog/profile.html'
    user = get_object_or_404(User, username=username)
    if user == request.user:
        posts = user.posts.select_related(
            'category',
            'location',
            'author'
        ).order_by('-pub_date')
    else:
        posts = user.posts.select_related(
            'category',
            'location',
            'author'
        ).filter(
            pub_date__lte=timezone.now(),
            is_published=True
        ).order_by('-pub_date')
    page_obj = get_page_obj(posts, 10, request)
    context = {'profile': user, 'page_obj': page_obj}
    return render(request, template, context)


@login_required
def profile_redirect(request):
    username = request.user.username
    return redirect('blog:profile', username=username)

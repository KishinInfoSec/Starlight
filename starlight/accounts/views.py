from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views import generic

from .forms import SignUpForm


class SignUpView(generic.CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

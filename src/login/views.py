from django.shortcuts import render
from django.views import View


class Login(View):
    def get(self, request):
        return render(request, 'login.html')

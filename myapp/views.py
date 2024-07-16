from django.http import HttpResponse


def index(request):
    return HttpResponse("Welcome to my Django API test project!")

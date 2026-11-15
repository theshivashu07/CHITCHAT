from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.contrib import messages
# Create your views here.




def index(request):
	return render(request,"auto/index.html"); 

def index(request):
	return render(request,"auto/edited-chat-fixed.html"); 



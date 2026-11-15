from urllib import request

from django.shortcuts import render,redirect

from django.contrib.auth import authenticate, login, logout
from rest_framework.response import Response
from rest_framework.decorators import api_view

from django.contrib.auth.models import User

from django.contrib import messages


# Create your views here.





def index(request):

    users = User.objects.all().order_by("-date_joined")

    context = {
        "users": users,
        "online_users_count": 0,
    }
    
    return render(request,"security/index.html",context); 



def signin(request):

    if request.method == "POST":

        identifier = request.POST.get("identifier")
        password = request.POST.get("password")

        # what if identifier me user apna email hi daal de tooo? to hm usko username me convert kar denge
        if '@' in identifier:
            user = User.objects.filter(email=identifier)
            if not user:
                messages.error(request, "Email not found!")
                return redirect("signin")
            identifier = user.first().username

        user = authenticate(
            request,
            username=identifier,
            password=password
        ) 

        if user is not None:
            login(request, user)
            

            messages.success(request, "You're logged in successfully!")
            return redirect("/profile/")

        messages.error(request, "Invalid username or password!")
        return redirect("signin")

    # all type of messages
    # messages.info(request, "You are in the login page. Please enter your credentials to log in.")
    # messages.warning(request, "This is a warning message. Please pay attention!")
    # messages.success(request, "This is a success message. You have successfully logged in!")
    # messages.error(request, "This is an error message. Something went wrong!")

    return render(request,"security/login.html"); 




def signup(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        print(username,email,password,confirm_password)

        if password != confirm_password:
            messages.error(request, "Passwords do not match each others!")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists!")
            return redirect("signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists!")
            return redirect("signup")

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        user.save()

        messages.success(request, "Account created successfully!")
        
        login(request, user)

        messages.success(request, "You're logged in successfully! Ready to setup your profile! ")
        
        return redirect("profile_setups")
        # return redirect("signin")
    
    return render(request,"security/signup.html"); 



def signout(request):
    logout(request)
    messages.info(request, "You are successfully logged out.")
    return redirect("signin")



def docs(request):
    pass




def forgot_password(request):
    identifier = request.GET.get("identifier", "root").strip()

    if request.method == "POST":
        identifier = request.POST.get("identifier").strip()

        messages.info(request, f"We saw that you have multiple accounts associated with the email: {identifier}")
        return redirect(f"/security/forgot-password/accounts/?identifier={identifier}")
    
    return render(request,"security/forgot-password.html", {"identifier": identifier});


def forgot_password_accounts(request):
    identifier = request.GET.get("identifier", 'none').strip() 

    if request.method == "POST":
        print(request.POST)

        identifier = request.POST.get("identifier").strip()
        account_id = request.POST.get("account_id", None).strip()
        print(identifier, account_id)
        
        messages.info(request, f"OTP sent to you picked account's associated email or mobile.")
        return redirect(f"/security/forgot-password/otp/?identifier={identifier}")

    return render(request,"security/forgot-password-accounts.html", {"identifier": identifier}); 


def forgot_password_otp(request):
    identifier = request.GET.get("identifier", 'none').strip()

    if request.method == "POST":
        identifier = request.POST.get("identifier").strip()

        messages.info(request, f"Your OTP is successfully verified! You can now reset your password.")
        return redirect(f"/security/reset-password/?identifier={identifier}")

    # randomly 6 digit otp generate
    import random
    otp = random.randint(100000, 999999)

    messages.info(request, f"Are rukoo yaha se hi lelooo: {otp}") 
    return render(request,"security/forgot-password-otp.html", {"identifier": identifier}); 

def reset_password(request):
    identifier = request.GET.get("identifier", "root").strip()

    if request.method == "POST":
        identifier = request.POST.get("identifier", "root").strip()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match each others!")
            return redirect(f"/security/reset-password/?identifier={identifier}")

        # agar email tha to eska username nikalooo 
        if '@' in identifier: 
            identifier = User.objects.filter(email=identifier).first().username 
        # confirm ki identifier ab username hi hoga 
        user = User.objects.filter(username=identifier).first()
        user.set_password(password)
        user.save()

        messages.success(request, "Your OTP is successfully verified!")
        messages.success(request, "Your password has been successfully reset!")

        login(request, user)
        
        messages.success(request, "You're logged in successfully!")
        return redirect("/profile/")

    return render(request,"security/reset-password.html", {"identifier": identifier}); 


def users(request):
    users = User.objects.all().order_by("-date_joined")

    context = {
        "users": users,
    }

    messages.info(request, f"Users data landed on your page! ")
    return render(request,"security/users.html",context);


"""
def errors(request,status_code=None, exception=None):    
    print('exception',exception)    
    print('status_code',status_code)    
    responses = {
        401 : { 'code' : "400", 'name' : "Bad Request !", 'discription' : "Sorry, the server could not understand your request due to invalid syntax or broken browser data. Please check your URL or clear your browser cache." },
        403 : { 'code' : "403", 'name' : "Access Denied !", 'discription' : "Sorry, you don't have permission to access this page. Please make sure you are logged into the correct account or contact the administrator." }, 
        404 : { 'code' : "404", 'name' : "Page Not Found !", 'discription' : "Sorry, the page you're looking for doesn't exist, has been removed, or the URL is incorrect. Please verify the web address and try again." },
        500 : { 'code' : "500", 'name' : "Internal Server Error !", 'discription' : "Sorry, something went wrong on our end. The server encountered an unexpected error and couldn't complete your request. Please try again later." }, 
        'auto' : { 'code' : "Unknown", 'name' : "Unknown Error !", 'discription' : "Sorry, something went wrong, I think this is unknown error, which comes out of the box. Please try again later." }, 
    }
    
    context = {
        'error' : responses.get(status_code, responses.get('auto', dict()))
    }
    print(context, request.path )
    return render(request,"errors/default.html",context);
"""
    


def errors(request, exception=None, status_code=None): # exception ko pehle rakhein, status_code ko baad me
    
    print('exception',exception)    
    print('status_code',status_code)   
    
    responses = {
        400 : { 'code' : "400", 'name' : "Bad Request !", 'discription' : "Sorry, the server could not understand your request..." },
        403 : { 'code' : "403", 'name' : "Access Denied !", 'discription' : "Sorry, you don't have permission to access this page..." }, 
        404 : { 'code' : "404", 'name' : "Page Not Found !", 'discription' : "Sorry, the page you're looking for doesn't exist..." },
        500 : { 'code' : "500", 'name' : "Internal Server Error !", 'discription' : "Sorry, something went wrong on our end..." }, 
        'auto' : { 'code' : "Unknown", 'name' : "Unknown Error !", 'discription' : "Sorry, something went wrong, I think this is unknown error, which comes out of the box. Please try again later." }, 
    }
    
    context = {
        'error' : responses.get(status_code, responses.get('auto', dict()))
    }    
    print('context :', context)
    return render(request, "errors/default.html", context)


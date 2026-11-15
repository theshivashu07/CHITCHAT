from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from django.contrib import messages

from .models import Profile
# Create your views here.




def index(request):
	return render(request,"home/index.html"); 




def profile(request):

	if not request.user.is_authenticated:
		return redirect("signin")

	return render(request,"home/profile.html"); 









'''

def profile_setups(request):

	print("GET:", request.GET)
	

	if not request.user.is_authenticated:
		return redirect("signin")
	
	if request.method == "POST":

		print("POST:", request.POST)
		print("FILES:", request.FILES)
		
		print('date_joined:',request.POST.get('date_joined', None), type(request.POST.get('date_joined')))
		print('last_updated:',request.POST.get('last_updated', None), type(request.POST.get('last_updated')))
		
		user_data = {
			key: value
			for key, value in request.POST.items()
			if key != "csrfmiddlewaretoken"
		}
		
		profile_picture = request.FILES.get("profile_picture")
		user_data["profile_picture"] = profile_picture

		print("user_data:", user_data)


		context = {
			"user": user_data,
		}

		return render(request,"home/profile-setups.html",context); 

	user = User.objects.get(username=request.user)
	print(user, user.date_joined)

	return render(request,"home/profile-setups.html"); 

'''





@login_required
def profile_setups(request):

    print('GET: ',request.GET or None)
    print('POST: ',request.POST or None)
    print("FILES:", request.FILES or None)
    
    profile, created = Profile.objects.get_or_create(
        user=request.user
    )
    
    print(profile,created)


    if request.method == "POST":

        request.user.username = request.POST.get(
            "username", ""
        ).strip()

        request.user.email = request.POST.get(
            "email", ""
        ).strip()

        # full_name → first_name + last_name
        full_name = request.POST.get(
            "full_name", ""
        ).strip()

        name_parts = full_name.split(maxsplit=1)

        request.user.first_name = name_parts[0] if name_parts else ""
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        request.user.save()


        profile.mobile = request.POST.get(
            "mobile", ""
        ).strip()

        profile.recovery_mobile = request.POST.get(
            "recovery_mobile", ""
        ).strip()

        profile.recovery_email = request.POST.get(
            "recovery_email", ""
        ).strip()

        profile.profession = request.POST.get(
            "profession", ""
        ).strip()

        profile.date_of_birth = (
            request.POST.get("date_of_birth")
            or None
        )

        profile.bio = request.POST.get(
            "bio", ""
        ).strip()

        profile.about = request.POST.get(
            "about", ""
        ).strip()

        profile.work_address = request.POST.get(
            "work_address", ""
        ).strip()

        profile.home_address = request.POST.get(
            "home_address", ""
        ).strip()


        # -------------------------
        # Profile picture
        # ------------------------- 

        if request.FILES.get("profile_picture"):
            profile.profile_picture = request.FILES[
                "profile_picture"
            ]


        profile.save()

        messages.success(
            request,
            "Profile updated successfully."
        )

        return redirect("profile")


    if not created:

        messages.success(
            request, 
            "You already have your profile, you need to update it!"
        )

        return redirect("profile_edits")
            

    context = {
        "user": request.user,
    }

    return render(
        request,
        "home/profile-setups.html",
        context
    )





@login_required
def profile_edits(request):

    print('GET: ',request.GET or None)
    print('POST: ',request.POST or None)
    print("FILES:", request.FILES or None)
    
    profile, created = Profile.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":

        request.user.username = request.POST.get(
            "username", ""
        ).strip()

        request.user.email = request.POST.get(
            "email", ""
        ).strip()

        # full_name → first_name + last_name
        full_name = request.POST.get(
            "full_name", ""
        ).strip()

        name_parts = full_name.split(maxsplit=1)

        request.user.first_name = name_parts[0] if name_parts else ""
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        request.user.save()


        profile.mobile = request.POST.get(
            "mobile", ""
        ).strip()

        profile.recovery_mobile = request.POST.get(
            "recovery_mobile", ""
        ).strip()

        profile.recovery_email = request.POST.get(
            "recovery_email", ""
        ).strip()

        profile.profession = request.POST.get(
            "profession", ""
        ).strip()

        profile.date_of_birth = (
            request.POST.get("date_of_birth")
            or None
        )

        profile.bio = request.POST.get(
            "bio", ""
        ).strip()

        profile.about = request.POST.get(
            "about", ""
        ).strip()

        profile.work_address = request.POST.get(
            "work_address", ""
        ).strip()

        profile.home_address = request.POST.get(
            "home_address", ""
        ).strip()


        # -------------------------
        # Profile picture
        # -------------------------

        if request.FILES.get("profile_picture",None):
            profile.profile_picture = request.FILES[
                "profile_picture"
            ]


        profile.save()

        messages.success(
            request,
            "Profile updated successfully."
        )

        return redirect("profile")

	
    if created:

        messages.success(
            request, 
            "You already have your profile, you need to update it!"
        )

        return redirect("profile_update")
            

    context = {
        "user": request.user,
        "profile": profile,
    }

    return render(
        request,
        "home/profile-edits.html",
        context
    )




















def notifications(request):

	if not request.user.is_authenticated:
		return redirect("signin")

	return render(request,"home/notifications.html");







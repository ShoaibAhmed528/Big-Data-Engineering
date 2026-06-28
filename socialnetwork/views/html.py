from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from matplotlib.style import context

from socialnetwork import api
from socialnetwork.api import _get_social_network_user
from socialnetwork.models import SocialNetworkUsers
from socialnetwork.serializers import PostsSerializer
from fame.models import ExpertiseAreas
from fame.models import FameLevels

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..ml_engine import get_malicious_probability, apply_adversarial_evasion

@require_http_methods(["GET"])
@login_required
def timeline(request):
    # using the serializer to get the data, then use JSON in the template!
    # avoids having to do the same thing twice

    # initialize community mode to False the first time in the session
    if 'community_mode' not in request.session:
        request.session['community_mode'] = False


    # get extra URL parameters:
    keyword = request.GET.get("search", "")
    published = request.GET.get("published", True)
    error = request.GET.get("error", None)

    # if keyword is not empty, use search method of API:
    if keyword and keyword != "":
        context = {
            "posts": PostsSerializer(
                api.search(keyword, published=published), many=True
            ).data,
            "searchkeyword": keyword,
            "error": error,
            "followers": list(api.follows(_get_social_network_user(request.user)).values_list('id', flat=True)),
        }
    else:  # otherwise, use timeline method of API:
        user = _get_social_network_user(request.user)

        super_pro = FameLevels.objects.get(name="Super Pro")
        eligible_communities = ExpertiseAreas.objects.filter(
            fame__user=user,
            fame__fame_level__numeric_value__gte=super_pro.numeric_value,
        ).exclude(community_members=user)

        context = {
            "posts": PostsSerializer(
                api.timeline(user, published=published,
                    community_mode=request.session.get('community_mode', False),
                ), many=True,
            ).data,
            "searchkeyword": "",
            "error": error,
            "followers": list(api.follows(user).values_list('id', flat=True)),
            "user_communities": user.communities.all(),
            "eligible_communities": eligible_communities,
            "community_mode": request.session.get('community_mode', False),
        }

    return render(request, "timeline.html", context=context)


@require_http_methods(["POST"])
@login_required
def follow(request):
    user = _get_social_network_user(request.user)
    user_to_follow = SocialNetworkUsers.objects.get(id=request.POST.get("user_id"))
    api.follow(user, user_to_follow)
    return redirect(reverse("sn:timeline"))


@require_http_methods(["POST"])
@login_required
def unfollow(request):
    user = _get_social_network_user(request.user)
    user_to_unfollow = SocialNetworkUsers.objects.get(id=request.POST.get("user_id"))
    api.unfollow(user, user_to_unfollow)
    return redirect(reverse("sn:timeline"))


@require_http_methods(["GET"])
@login_required
def bullshitters(request):
    context = {
        "bullshitters" : api.bullshitters(),
    }
    return render (request, "bullshitters.html", context)


@require_http_methods(["POST"])
@login_required
def toggle_community_mode(request):
    request.session['community_mode'] = not request.session.get('community_mode', False)
    return redirect(reverse("sn:timeline"))

@require_http_methods(["POST"])
@login_required
def join_community(request):
    user = _get_social_network_user(request.user)
    community_to_join = ExpertiseAreas.objects.get(id=request.POST.get("community_id"))
    api.join_community(user, community_to_join)
    return redirect(reverse("sn:timeline"))


@require_http_methods(["POST"])
@login_required
def leave_community(request):
    user = _get_social_network_user(request.user)
    community_to_leave = ExpertiseAreas.objects.get(id=request.POST.get("community_id"))
    api.leave_community(user, community_to_leave)
    return redirect(reverse("sn:timeline"))

@require_http_methods(["GET"])
@login_required
def similar_users(request):
    user = _get_social_network_user(request.user)
    matching_users = api.similar_users(user)
    
    context = {
        "users": matching_users
    }
    
    return render(request, "similar_users.html", context=context)

@login_required
def adversarial_simulator_view(request):
    context = {}
    
    if request.method == "POST":
        original_text = request.POST.get("payload_text", "")
        
        if original_text:
            # 1. Score the original text
            original_score = get_malicious_probability(original_text)
            
            # 2. Apply the hacker's evasion techniques
            evaded_text = apply_adversarial_evasion(original_text)
            
            # 3. Score the evaded text
            evaded_score = get_malicious_probability(evaded_text)
            
            # 4. Calculate the delta (how much the hacker fooled the AI)
            score_drop = original_score - evaded_score
            
            context = {
                "original_text": original_text,
                "original_score": round(original_score * 100, 2),
                "evaded_text": evaded_text,
                "evaded_score": round(evaded_score * 100, 2),
                "score_drop": round(score_drop * 100, 2),
                "has_results": True
            }

    return render(request, "adversarial_simulator.html", context)
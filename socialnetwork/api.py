from django.db.models import Q, Exists, OuterRef, When, IntegerField, FloatField, Count, ExpressionWrapper, Case, Value, F, Prefetch

from fame.models import Fame, FameLevels, FameUsers, ExpertiseAreas
from socialnetwork.models import Posts, SocialNetworkUsers


# general methods independent of html and REST views
# should be used by REST and html views


def _get_social_network_user(user) -> SocialNetworkUsers:
    """Given a FameUser, gets the social network user from the request. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise PermissionError("User does not exist")
    return user


def timeline(user: SocialNetworkUsers, start: int = 0, end: int = None, published=True, community_mode=False):
    """Get the timeline of the user. Assumes that the user is authenticated."""

    if community_mode:
        # T4
        # in community mode, posts of communities are displayed if ALL of the following criteria are met:
        # 1. the author of the post is a member of the community
        # 2. the user is a member of the community
        # 3. the post contains the community’s expertise area
        # 4. the post is published or the user is the author

        # Get all communities this user is a member of
       user_communities = user.communities.all()
       
       posts = Posts.objects.filter(
            #  published or own post
            Q(published=True) | Q(author=user),
            #  post is tagged with an expertise area the user is in
            expertise_area_and_truth_ratings__in=user_communities,
            #  the author is also a member of that same community
            author__communities__in=user_communities,
        ).distinct().order_by("-submitted")  # distinct - bcz a post can be tagged with multiple expertise areas.
    else:
        # in standard mode, posts of followed users are displayed
        _follows = user.follows.all()
        posts = Posts.objects.filter(
            (Q(author__in=_follows) & Q(published=published)) | Q(author=user)
        ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]


def search(keyword: str, start: int = 0, end: int = None, published=True):
    """Search for all posts in the system containing the keyword. Assumes that all posts are public"""
    posts = Posts.objects.filter(
        Q(content__icontains=keyword)
        | Q(author__email__icontains=keyword)
        | Q(author__first_name__icontains=keyword)
        | Q(author__last_name__icontains=keyword),
        published=published,
    ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]


def follows(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the users followed by this user. Assumes that the user is authenticated."""
    _follows = user.follows.all()
    if end is None:
        return _follows[start:]
    else:
        return _follows[start:end+1]


def followers(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the followers of this user. Assumes that the user is authenticated."""
    _followers = user.followed_by.all()
    if end is None:
        return _followers[start:]
    else:
        return _followers[start:end+1]


def follow(user: SocialNetworkUsers, user_to_follow: SocialNetworkUsers):
    """Follow a user. Assumes that the user is authenticated. If user already follows the user, signal that."""
    if user_to_follow in user.follows.all():
        return {"followed": False}
    user.follows.add(user_to_follow)
    user.save()
    return {"followed": True}


def unfollow(user: SocialNetworkUsers, user_to_unfollow: SocialNetworkUsers):
    """Unfollow a user. Assumes that the user is authenticated. If user does not follow the user anyway, signal that."""
    if user_to_unfollow not in user.follows.all():
        return {"unfollowed": False}
    user.follows.remove(user_to_unfollow)
    user.save()
    return {"unfollowed": True}


def submit_post(
    user: SocialNetworkUsers,
    content: str,
    cites: Posts = None,
    replies_to: Posts = None,
):
    """Submit a post for publication. Assumes that the user is authenticated.
    returns a tuple of three elements:
    1. a dictionary with the keys "published" and "id" (the id of the post)
    2. a list of dictionaries containing the expertise areas and their truth ratings
    3. a boolean indicating whether the user was banned and logged out and should be redirected to the login page
    """

    # create post  instance:
    post = Posts.objects.create(
        content=content,
        author=user,
        cites=cites,
        replies_to=replies_to,
    )

    # classify the content into expertise areas:
    # only publish the post if none of the expertise areas contains bullshit:
    _at_least_one_expertise_area_contains_bullshit, _expertise_areas = (
        post.determine_expertise_areas_and_truth_ratings()
    )
    post.published = not _at_least_one_expertise_area_contains_bullshit

    redirect_to_logout = False

    # auto-remove user from community if fame drops below Super Pro
    # Check each expertise area of this post
    for epa in _expertise_areas:
        expertise_area = epa["expertise_area"]
        if expertise_area is None:
           continue

        # Check if user is in this community
        if expertise_area in user.communities.all():
        # Get the user's current fame in this expertise area
            try:
               fame_entry = Fame.objects.get(user=user, expertise_area=expertise_area)
               super_pro_level = FameLevels.objects.get(name="Super Pro")
               # If fame dropped below Super Pro, remove from community
               if fame_entry.fame_level.numeric_value < super_pro_level.numeric_value:
                leave_community(user, expertise_area)
            except Fame.DoesNotExist:
               # No fame entry means they shouldn't be in the community anyways
               leave_community(user, expertise_area)

    post.save()

    return (
        {"published": post.published, "id": post.id},
        _expertise_areas,
        redirect_to_logout,
    )


def rate_post(
    user: SocialNetworkUsers, post: Posts, rating_type: str, rating_score: int
):
    """Rate a post. Assumes that the user is authenticated. If user already rated the post with the given rating_type,
    update that rating score."""
    user_rating = None
    try:
        user_rating = user.userratings_set.get(post=post, rating_type=rating_type)
    except user.userratings_set.model.DoesNotExist:
        pass

    if user == post.author:
        raise PermissionError(
            "User is the author of the post. You cannot rate your own post."
        )

    if user_rating is not None:
        # update the existing rating:
        user_rating.rating_score = rating_score
        user_rating.save()
        return {"rated": True, "type": "update"}
    else:
        # create a new rating:
        user.userratings_set.add(
            post,
            through_defaults={"rating_type": rating_type, "rating_score": rating_score},
        )
        user.save()
        return {"rated": True, "type": "new"}


def fame(user: SocialNetworkUsers):
    """Get the fame of a user. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise ValueError("User does not exist")

    return user, Fame.objects.filter(user=user)


def bullshitters():
    """Return a Python dictionary mapping each existing expertise area in the fame profiles to a list of the users
    having negative fame for that expertise area. Each list should contain Python dictionaries as entries with keys
    ``user'' (for the user) and ``fame_level_numeric'' (for the corresponding fame value), and should be ranked, i.e.,
    users with the lowest fame are shown first, in case there is a tie, within that tie sort by date_joined
    (most recent first). Note that expertise areas with no expert may be omitted.
    """
    # Get all Fame rows where the fame level is negative
    # filter on the related FameLevels model using __ (double underscore)
    negative_fame_entries = Fame.objects.filter(
        fame_level__numeric_value__lt=0
    ).select_related(
        # select_related: JOIN these tables in one SQL query
        "user",               
        "expertise_area",     
        "fame_level",         
    ).order_by(
        "fame_level__numeric_value",   # lowest fame first 
        "-user__date_joined",          # most recently joined first (- means Descending)
    )

    # Build the result dictionary
    result = {}

    for entry in negative_fame_entries:
        # entry.expertise_area.label (e.g. Computer Science)
        # entry.user                 (the FameUser object)
        # entry.fame_level.numeric_value  (-300)

        area_label = entry.expertise_area.label

        # If this expertise area isn't in the dict yet, create an empty list for it
        if area_label not in result:
            result[area_label] = []

        # Append this user's entry to that area's list
        result[area_label].append({
            "user": entry.user,
            "fame_level_numeric": entry.fame_level.numeric_value,
        })

    return result




def join_community(user: SocialNetworkUsers, community: ExpertiseAreas):
    """Join a specified community. Note that this method does not check whether the user is eligible for joining the
    community.
    """
    user.communities.add(community)
    user.save()


def leave_community(user: SocialNetworkUsers, community: ExpertiseAreas):
    """Leave a specified community."""
    
    user.communities.remove(community)
    user.save()


def similar_users(user: SocialNetworkUsers):
    """Compute the similarity of user with all other users. The method returns a QuerySet of FameUsers annotated
    with an additional field 'similarity'. Sort the result in descending order according to 'similarity', in case
    there is a tie, within that tie sort by date_joined (most recent first)"""
 
    UserModel = user.__class__
    
    # 1. Get the target user's expertise areas and fame values.
    # select_related fetches the fame_level in the same query (prevents slow N+1 queries).
    target_fames = {
        f.expertise_area_id: f.fame_level.numeric_value 
        for f in Fame.objects.filter(user=user).select_related('fame_level')
    }
    
    if not target_fames:
        return UserModel.objects.none()
        
    # 2. Build the matching rules: Area matches AND fame is within +/- 100
    conditions = Q()
    for area_id, val in target_fames.items():
        conditions |= Q(
            fame__expertise_area_id=area_id, 
            fame__fame_level__numeric_value__range=(val - 100, val + 100)
        )
        
    # 3. Find similar users and calculate similarity
    n_areas = len(target_fames)
    
    return UserModel.objects.exclude(pk=user.pk).annotate(
        # Count matching fame records based on our conditions
        matching=Count('fame', filter=conditions, distinct=True)
    ).annotate(
        # Multiply by 1.0 forces float division (no Cast needed!)
        similarity=F('matching') * 1.0 / n_areas
    ).filter(
        similarity__gt=0
    ).order_by(
        '-similarity', '-date_joined'
    )
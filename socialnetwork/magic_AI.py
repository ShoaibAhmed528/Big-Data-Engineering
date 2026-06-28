import random as rnd
import hashlib

from fame.models import ExpertiseAreas
# Import the centralized truth evaluator instead of the raw probability
from socialnetwork.ml_engine import evaluate_text_truthfulness

rnd.seed(42)

def classify_into_expertise_areas_and_check_for_bullshit(content: str):
    """
    Classify the given content into expertise areas and check for bullshit.
    """
    # 1. Keep the deterministic seed for EXPERTISE AREAS 
    seed = int(hashlib.md5(content.encode()).hexdigest(), 16)
    lre = rnd.Random(seed)
    
    expertise_areas = lre.sample(list(ExpertiseAreas.objects.all()), 2)

    # 2. Use our ML algorithm decision
    verdict = evaluate_text_truthfulness(content)

    from socialnetwork.models import TruthRatings
    
    # Map the categorical verdict to the project's TruthRatings database objects
    if verdict == "BULLSHIT":
        negative_ratings = TruthRatings.objects.filter(numeric_value__lt=0)
        truth_rating = lre.choice(negative_ratings) if negative_ratings.exists() else None
        
    elif verdict == "TRUE":
        positive_ratings = TruthRatings.objects.filter(numeric_value__gt=0)
        truth_rating = lre.choice(positive_ratings) if positive_ratings.exists() else None
        
    else: # verdict == "UNKNOWN"
        truth_rating = None

    # 3. Return the combined result
    return [
        {
            "expertise_area": s,
            "truth_rating": truth_rating,
        }
        for s in expertise_areas
    ]
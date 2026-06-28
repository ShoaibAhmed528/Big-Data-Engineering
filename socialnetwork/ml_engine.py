# socialnetwork/ml_engine.py
import random
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# --- thresholds ---
BULLSHIT_THRESHOLD = 0.50
TRUE_THRESHOLD = 0.45

# training data - spam vs normal messages
TRAINING_TEXTS = [
    "click here to claim your free money now", "urgent action required verify your account",
    "congratulations you won a gift card", "send your password to reset your account",
    "hello how are you doing today", "the meeting is scheduled for 3pm",
    "please review the attached document", "great job on the presentation yesterday",
    "i will be late to the office", "can you send me the report"
]
TRAINING_LABELS = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]  # 1 = spam, 0 = normal

# build and train the model
ml_pipeline = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('clf', LogisticRegression())
])
ml_pipeline.fit(TRAINING_TEXTS, TRAINING_LABELS)


def get_malicious_probability(text: str) -> float:
    # returns how likely the text is spam (0.0 to 1.0)
    probs = ml_pipeline.predict_proba([text])[0]
    return probs[1]

def evaluate_text_truthfulness(text: str) -> str:
    # compares probability against thresholds and returns a verdict
    prob = get_malicious_probability(text)

    if prob > BULLSHIT_THRESHOLD:
        return "BULLSHIT"
    elif prob < TRUE_THRESHOLD:
        return "TRUE"
    else:
        return "UNKNOWN"


#evasion atatcks

# swap letters with symbols to confuse the tokenizer
LEETSPEAK_MAP = {
    'a': '@', 'e': '3', 'i': '!', 'o': '0', 's': '$', 't': '7', 'c': '('
}

# normal looking words to mix in and lower the spam score
BENIGN_ML_TRIGGERS = [
    "thanks", "regards", "meeting", "attached", "schedule", "please"
]

def apply_adversarial_evasion(text: str) -> str:
    evaded_text = text

    # attack type 1 throw in a couple of innocent words
    num_benign_words = random.randint(1, 2)
    benign_injection = " ".join(random.sample(BENIGN_ML_TRIGGERS, num_benign_words))
    evaded_text = f"{evaded_text} {benign_injection}"

    # attack type 2 randomly replace letters with leet symbols
    obfuscated_words = []
    for word in evaded_text.split():
        if random.random() < 0.4:
            new_word = ""
            for char in word:
                if char.lower() in LEETSPEAK_MAP and random.random() < 0.7:
                    new_word += LEETSPEAK_MAP[char.lower()]
                else:
                    new_word += char
            obfuscated_words.append(new_word)
        else:
            obfuscated_words.append(word)
    evaded_text = " ".join(obfuscated_words)

    # attack type 3 insert invisible zerowidth spaces inside some words
    final_words = []
    for word in evaded_text.split():
        if len(word) > 3 and random.random() < 0.4:
            mid = len(word) // 2
            word = word[:mid] + "\u200b" + word[mid:]
        final_words.append(word)

    return " ".join(final_words)
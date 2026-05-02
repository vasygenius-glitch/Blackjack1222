import random
import secrets

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10, 'A': 11
}
secure_random = secrets.SystemRandom()

def get_random_card():
    return {'rank': secure_random.choice(RANKS), 'suit': secure_random.choice(SUITS)}

def calculate_score(cards):
    score = 0
    aces = 0
    for card in cards:
        score += VALUES[card['rank']]
        if card['rank'] == 'A':
            aces += 1

    while score > 21 and aces > 0:
        score -= 10
        aces -= 1

    return score

def format_cards(cards):
    return " ".join([f"{c['rank']}{c['suit']}" for c in cards])

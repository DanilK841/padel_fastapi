import json, random, math
from americano.models import Match, Tournament, generate_id
from database import PlayerORM
from typing import List

def generate_americano_rounds(players: List[str], courts: int, num_rounds: int) -> List[List[Match]]:
    """Generate Americano rounds where partners and opponents rotate."""
    rounds = []
    n = num_rounds + 1
    
    # Ensure even number of players
    if n % 4 != 0:
        # Pad if necessary (bye players)
        while len(players) % 4 != 0:
            players.append(None)
    
    active_players = [p for p in players if p]
    
    for round_num in range(num_rounds):
        round_matches = []
        available = active_players.copy()
        random.shuffle(available)
        
        court = 1
        while len(available) >= 4 and court <= courts:
            p1, p2, p3, p4 = available[:4]
            available = available[4:]
            match_id = generate_id()
            match = Match(
                id=match_id,
                round=round_num + 1,
                court=court,
                team1=[p1, p2],
                team2=[p3, p4]
            )
            round_matches.append(match)
            court += 1
        
        rounds.append(round_matches)
    
    return rounds

def generate_americano_round(players: List[str], courts: int, num_round: int) -> List[Match]:
    """Generate Americano rounds where partners and opponents rotate."""
    rounds = []
    n = len(players)
    
    # Ensure even number of players
    if n % 4 != 0:
        # Pad if necessary (bye players)
        while len(players) % 4 != 0:
            players.append(None)
            
    active_players = [p for p in players if p]
    # for round_num in range(num_rounds):
    round_matches = []
    available = active_players.copy()
    random.shuffle(available)
    
    court = 1
    match_id = 1
    while len(available) >= 4 and court <= courts:
        p1, p2, p3, p4 = available[:4]
        available = available[4:]
        
        match = Match(
            id=f"r{num_round+1}m{match_id}",
            round=num_round + 1,
            court=court,
            team1=[p1, p2],
            team2=[p3, p4]
        )
        round_matches.append(match)
        court += 1
        match_id += 1
    
    
    rounds.append(round_matches)
    return rounds

def calculate_standings(tournament: Tournament) -> List[dict]:
    standings = []
    for pid, player in tournament.players.items():
        standings.append({
            "id": pid,
            "name": player.name,
            "points": player.points,
            "games_played": player.games_played,
            "games_won": player.games_won,
            "games_lost": player.games_lost,
        })
    standings.sort(key=lambda x: (-x["points"], -x["games_won"]))
    for i, s in enumerate(standings):
        s["rank"] = i + 1
    return standings


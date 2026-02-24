import json, random, math
from americano.models import Match, Tournament
from typing import List

def generate_mexicano_round(tournament: 'Tournament', num_round: int) -> List[Match]:
    """
    Generate a Mexicano round: players sorted by current points,
    rank 1 & 2 partner together vs rank 3 & 4, etc.
    For first round falls back to random.
    """
    players = tournament.players
    courts = tournament.courts

    # Sort players by points descending (random for equal points)
    sorted_players = sorted(
        players.keys(),
        key=lambda pid: (-players[pid].points, random.random())
    )

    # Pad to multiple of 4
    active = list(sorted_players)
    while len(active) % 4 != 0:
        active.append(None)
    active = [p for p in active if p]

    round_matches = []
    court = 1
    match_id = 1
    i = 0
    while i + 3 < len(active) and court <= courts:
        # Top two partner together (rank i+1 and i+2)
        # vs next two (rank i+3 and i+4)
        p1, p2, p3, p4 = active[i], active[i+2], active[i+1], active[i+3]
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
        i += 4

    return round_matches

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
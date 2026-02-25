from dataclasses import dataclass, field, asdict
from typing import List, Optional

def generate_id():
    import uuid
    return str(uuid.uuid4())[:8]

@dataclass
class Player:
    id: str
    name: str
    sex: str
    points: int = 0
    games_played: int = 0
    games_won: int = 0
    games_lost: int = 0

@dataclass
class Match:
    id: str
    round: int
    court: int
    team1: List[str]  # player ids
    team2: List[str]  # player ids
    score1: Optional[int] = None
    score2: Optional[int] = None
    completed: bool = False

@dataclass
class Tournament:
    id: str
    name: str
    courts: int
    players: dict = field(default_factory=dict)  # id -> Player
    rounds: List[List[Match]] = field(default_factory=list)
    current_round: int = 0
    status: str = "setup"  # setup, active, finished
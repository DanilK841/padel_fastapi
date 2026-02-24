from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pathlib import Path

from functions import generate_americano_rounds, calculate_standings
from models import Player, Tournament, generate_id

app = FastAPI(title="Padel Americano")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="../templates")

# In-memory storage (could be replaced with DB)
tournaments_db: dict = {}

# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "tournaments": list(tournaments_db.values())
    })

@app.post("/tournament/create")
async def create_tournament(
    name: str = Form(...),
    courts: int = Form(...),
    num_rounds: int = Form(...),
    player_names: str = Form(...)
):
    tid = generate_id()
    names = [n.strip() for n in player_names.split("\n") if n.strip()]
    
    if len(names) < 4:
        raise HTTPException(status_code=400, detail="Введите минимум 4 имени")
    
    players = {}
    player_ids = []
    for name in names:
        pid = generate_id()
        players[pid] = Player(id=pid, name=name)
        player_ids.append(pid)
    
    rounds = generate_americano_rounds(player_ids, courts, num_rounds)
    
    tournament = Tournament(
        id=tid,
        name=name,
        courts=courts,
        players=players,
        rounds=rounds,
        status="active"
    )
    
    tournaments_db[tid] = tournament
    return RedirectResponse(f"/tournament/{tid}", status_code=303)

@app.head("/tournament/{tid}")
async def tournament_view(request: Request, tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return Response(status_code=200)

@app.get("/tournament/{tid}", response_class=HTMLResponse)
async def tournament_view(request: Request, tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    standings = calculate_standings(t)
    current_matches = t.rounds[t.current_round] if t.rounds and t.current_round < len(t.rounds) else []
    
    return templates.TemplateResponse("tournament.html", {
        "request": request,
        "tournament": t,
        "standings": standings,
        "current_matches": current_matches,
        "players": t.players,
        "total_rounds": len(t.rounds),
    })

@app.post("/tournament/{tid}/score")
async def submit_score(
    request: Request,
    tid: str,
    match_id: str = Form(...),
    score1: int = Form(...),
    score2: int = Form(...)
):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404)
    
    # Find match in current round
    for match in t.rounds[t.current_round]:
        if match.id == match_id:
            if match.completed:
                break
            
            match.score1 = score1
            match.score2 = score2
            match.completed = True
            
            # Update player stats
            for pid in match.team1:
                p = t.players[pid]
                p.games_played += 1
                p.points += score1
                if score1 > score2:
                    p.games_won += 1
                else:
                    p.games_lost += 1
            
            for pid in match.team2:
                p = t.players[pid]
                p.games_played += 1
                p.points += score2
                if score2 > score1:
                    p.games_won += 1
                else:
                    p.games_lost += 1
            break
    
    return RedirectResponse(f"/tournament/{tid}", status_code=303)

@app.post("/tournament/{tid}/next-round")
async def next_round(tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404)
    
    # Check all matches in current round completed
    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        if t.current_round + 1 < len(t.rounds):
            t.current_round += 1
        else:
            t.status = "finished"
    
    return RedirectResponse(f"/tournament/{tid}", status_code=303)

@app.post("/tournament/{tid}/delete")
async def delete_tournament(tid: str):
    tournaments_db.pop(tid, None)
    return RedirectResponse("/", status_code=303)

@app.post("/tournament/{tid}/edit-score")
async def edit_score(
    request: Request,
    tid: str,
    match_id: str = Form(...),
    score1: int = Form(...),
    score2: int = Form(...)
):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404)
    
    # Find match in any round
    for round_matches in t.rounds:
        for match in round_matches:
            if match.id == match_id and match.completed:
                old_score1 = match.score1
                old_score2 = match.score2

                # Revert old stats
                for pid in match.team1:
                    p = t.players[pid]
                    p.points -= old_score1
                    if old_score1 > old_score2:
                        p.games_won -= 1
                    else:
                        p.games_lost -= 1

                for pid in match.team2:
                    p = t.players[pid]
                    p.points -= old_score2
                    if old_score2 > old_score1:
                        p.games_won -= 1
                    else:
                        p.games_lost -= 1

                # Apply new stats
                match.score1 = score1
                match.score2 = score2

                for pid in match.team1:
                    p = t.players[pid]
                    p.points += score1
                    if score1 > score2:
                        p.games_won += 1
                    else:
                        p.games_lost += 1

                for pid in match.team2:
                    p = t.players[pid]
                    p.points += score2
                    if score2 > score1:
                        p.games_won += 1
                    else:
                        p.games_lost += 1

                return RedirectResponse(f"/tournament/{tid}", status_code=303)

    return RedirectResponse(f"/tournament/{tid}", status_code=303)


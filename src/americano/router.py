from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from americano.models import Player, Tournament, generate_id
from americano.functions import generate_americano_rounds, calculate_standings

router = APIRouter(prefix='/americano', tags=['Американо'])
templates = Jinja2Templates(directory="templates/americano")
# In-memory storage (could be replaced with DB)
tournaments_db: dict = {}
# Routes

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request
    })

@router.post("/tournament/create")
async def create_tournament(
    name: str = Form(...),
    courts: int = Form(...),
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
    
    rounds = generate_americano_rounds(player_ids, courts, len(names) - 1)
    
    tournament = Tournament(
        id=tid,
        name=name,
        courts=courts,
        players=players,
        rounds=rounds,
        status="active"
    )
    
    tournaments_db[tid] = tournament
    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.head("/tournament/{tid}")
async def tournament_view(request: Request, tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return Response(status_code=200)

@router.get("/tournament/{tid}", response_class=HTMLResponse)
async def tournament_view(request: Request, tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    
    standings = calculate_standings(t)

    print(t)

    current_matches = t.rounds[t.current_round] if t.rounds and t.current_round < len(t.rounds) else []
    
    return templates.TemplateResponse("tournament.html", {
        "request": request,
        "tournament": t,
        "standings": standings,
        "current_matches": current_matches,
        "players": t.players,
        "total_rounds": len(t.rounds),
    })

@router.post("/tournament/{tid}/score")
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
    
    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.post("/tournament/{tid}/next-round")
async def next_round(tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404)
    
    # Check all matches in current round completed
    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        t.current_round += 1

    return RedirectResponse(f"/tournament/{tid}", status_code=303)

@router.post("/tournament/{tid}/finish")
async def finish_tournament(tid: str):
    t = tournaments_db.get(tid)
    if not t:
        raise HTTPException(status_code=404)
    
    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        t.status = "finished"
    
    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.post("/tournament/{tid}/delete")
async def delete_tournament(tid: str):
    tournaments_db.pop(tid, None)
    return RedirectResponse("/americano", status_code=303)

@router.post("/tournament/{tid}/edit-score")
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

                return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)


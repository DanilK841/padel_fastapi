from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from mexicano.models import Player, Tournament, generate_id
from mexicano.functions import generate_mexicano_round, calculate_standings

router = APIRouter(prefix='/mexicano', tags=['Мексикано'])
templates = Jinja2Templates(directory="templates/mexicano")
# In-memory storage (could be replaced with DB)
mexicano_db: dict = {}
# Routes

@router.get("/", response_class=HTMLResponse)
async def mexicano_index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
    })


@router.post("/create")
async def create_mexicano(
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
    for pname in names:
        pid = generate_id()
        players[pid] = Player(id=pid, name=pname)

    tournament = Tournament(
        id=tid,
        name=name,
        courts=courts,
        players=players,
        rounds=[],
        current_round=0,
        status="active"
    )
    # Store total planned rounds in a side dict (Tournament has no field for it)
    mexicano_db[tid] = tournament
    mexicano_db[f"{tid}__total_rounds"] = num_rounds

    # Generate first round immediately
    first_round = generate_mexicano_round(tournament, 0)
    tournament.rounds.append(first_round)

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.head("/{tid}")
async def mexicano_head(tid: str):
    t = mexicano_db.get(tid)
    if not t or not isinstance(t, Tournament):
        raise HTTPException(status_code=404)
    return Response(status_code=200)


@router.get("/{tid}", response_class=HTMLResponse)
async def mexicano_view(request: Request, tid: str):
    t = mexicano_db.get(tid)
    if not t or not isinstance(t, Tournament):
        raise HTTPException(status_code=404, detail="Tournament not found")

    total_rounds = mexicano_db.get(f"{tid}__total_rounds", len(t.rounds))
    standings = calculate_standings(t)
    current_matches = t.rounds[t.current_round] if t.rounds and t.current_round < len(t.rounds) else []

    return templates.TemplateResponse("tournament.html", {
        "request": request,
        "tournament": t,
        "standings": standings,
        "current_matches": current_matches,
        "players": t.players,
        "total_rounds": total_rounds,
        "mode": "mexicano",
    })


@router.post("/{tid}/score")
async def mexicano_score(
    tid: str,
    match_id: str = Form(...),
    score1: int = Form(...),
    score2: int = Form(...)
):
    t = mexicano_db.get(tid)
    if not t or not isinstance(t, Tournament):
        raise HTTPException(status_code=404)

    for match in t.rounds[t.current_round]:
        if match.id == match_id:
            if match.completed:
                break
            match.score1 = score1
            match.score2 = score2
            match.completed = True

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

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.post("/{tid}/next-round")
async def mexicano_next_round(tid: str):
    t = mexicano_db.get(tid)
    if not t or not isinstance(t, Tournament):
        raise HTTPException(status_code=404)

    current = t.rounds[t.current_round]
    total_rounds = mexicano_db.get(f"{tid}__total_rounds", len(t.rounds))

    if all(m.completed for m in current):
        t.current_round += 1
        if t.current_round < total_rounds:
            new_round = generate_mexicano_round(t, t.current_round)
            t.rounds.append(new_round)

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.post("/{tid}/finish")
async def mexicano_finish(tid: str):
    t = mexicano_db.get(tid)
    if not t or not isinstance(t, Tournament):
        raise HTTPException(status_code=404)

    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        t.status = "finished"

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.post("/{tid}/delete")
async def mexicano_delete(tid: str):
    mexicano_db.pop(tid, None)
    mexicano_db.pop(f"{tid}__total_rounds", None)
    return RedirectResponse("/mexicano", status_code=303)


@router.post("/{tid}/edit-score")
async def mexicano_edit_score(
    tid: str,
    match_id: str = Form(...),
    score1: int = Form(...),
    score2: int = Form(...)
):
    t = mexicano_db.get(tid)
    if not t or not isinstance(t, Tournament):
        raise HTTPException(status_code=404)

    for round_matches in t.rounds:
        for match in round_matches:
            if match.id == match_id and match.completed:
                old1, old2 = match.score1, match.score2

                for pid in match.team1:
                    p = t.players[pid]
                    p.points -= old1
                    if old1 > old2: p.games_won -= 1
                    else: p.games_lost -= 1

                for pid in match.team2:
                    p = t.players[pid]
                    p.points -= old2
                    if old2 > old1: p.games_won -= 1
                    else: p.games_lost -= 1

                match.score1 = score1
                match.score2 = score2

                for pid in match.team1:
                    p = t.players[pid]
                    p.points += score1
                    if score1 > score2: p.games_won += 1
                    else: p.games_lost += 1

                for pid in match.team2:
                    p = t.players[pid]
                    p.points += score2
                    if score2 > score1: p.games_won += 1
                    else: p.games_lost += 1

                return RedirectResponse(f"/mexicano/{tid}", status_code=303)

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)

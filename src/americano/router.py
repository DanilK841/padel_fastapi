from fastapi import APIRouter, Form, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session, TournamentORM, PlayerORM, MatchORM
from americano.models import Player, Tournament, Match, generate_id
from americano.functions import generate_americano_rounds, calculate_standings

router = APIRouter(prefix='/americano', tags=['Американо'])
templates = Jinja2Templates(directory="templates")
router.mount("/static", StaticFiles(directory="static"), name="static")
# In-memory storage (could be replaced with DB)
# tournaments_db: dict = {}

def _orm_to_tournament(t_row: TournamentORM) -> Tournament:
    """Convert SQLAlchemy ORM object into the existing Tournament dataclass."""
    players = {
        p.id: Player(
            id=p.id, name=p.name, sex=p.sex,
            points=p.points, games_played=p.games_played,
            games_won=p.games_won, games_lost=p.games_lost,
        )
        for p in t_row.players
    }

    max_round = max((m.round for m in t_row.matches), default=0)
    rounds: list[list[Match]] = [[] for _ in range(max_round)]
    for m in t_row.matches:
        rounds[m.round - 1].append(Match(
            id=m.id, round=m.round, court=m.court,
            team1=list(m.team1), team2=list(m.team2),
            score1=m.score1, score2=m.score2,
            completed=m.completed,
        ))

    return Tournament(
        id=t_row.id, name=t_row.name, courts=t_row.courts,
        players=players, rounds=rounds,
        current_round=t_row.current_round,
        status=t_row.status,
    )


async def _get_tournament_orm(tid: str, session: AsyncSession) -> TournamentORM:
    result = await session.get(TournamentORM, tid)
    if not result:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return result


def _update_player_stats(
    player_orm: PlayerORM,
    score_for: int, score_against: int,
    delta: int = 1,          # +1 to apply, -1 to revert
):
    player_orm.games_played += delta
    player_orm.points       += delta * score_for
    if score_for > score_against:
        player_orm.games_won  += delta
    else:
        player_orm.games_lost += delta


# Routes

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("americano/index.html", {
        "request": request
    })

@router.post("/tournament/create")
async def create_tournament(
    name: str = Form(...),
    courts: int = Form(...),
    player_names: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    tid = generate_id()
    names = [n.strip() for n in player_names.split("\n") if n.strip()]
    
    if len(names) < 4:
        raise HTTPException(status_code=400, detail="Введите минимум 4 имени")
    
    
    player_ids = []
    player_orms = []
    for name in names:
        pid = generate_id()
        player_ids.append(pid)
        player_orms.append(PlayerORM(id=pid, tournament_id=tid, name=name))
        
    
    rounds = generate_americano_rounds(player_ids, courts, len(names) - 1)
    
    t_orm = TournamentORM(
        id=tid, mode="americano", name=name, courts=courts,
        status="active", current_round=0, total_rounds=len(rounds),
    )
    session.add(t_orm)
    session.add_all(player_orms)
    for round_matches in rounds:
        for m in round_matches:
            session.add(MatchORM(
                id=m.id, tournament_id=tid,
                round=m.round, court=m.court,
                team1=m.team1, team2=m.team2,
            ))

    await session.commit()
    
    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.head("/tournament/{tid}")
async def tournament_view(tid: str, session: AsyncSession = Depends(get_session)):
    row = await session.get(TournamentORM, tid)
    if not row:
        raise HTTPException(status_code=404)
    return Response(status_code=200)

@router.get("/tournament/{tid}", response_class=HTMLResponse)
async def tournament_view(request: Request, tid: str, session: AsyncSession = Depends(get_session)):
    t_orm = await _get_tournament_orm(tid, session)
    
    if not t_orm:
        raise HTTPException(status_code=404, detail="Tournament not found")
    t = _orm_to_tournament(t_orm)
    standings = calculate_standings(t)
    current_matches = t.rounds[t.current_round] if t.rounds and t.current_round < len(t.rounds) else []
    
    return templates.TemplateResponse("americano/tournament.html", {
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
    score2: int = Form(...),
    session: AsyncSession = Depends(get_session),
):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm:
        raise HTTPException(status_code=404)
    t = _orm_to_tournament(t_orm)
    
    match = next(
        (m for m in t.rounds[t.current_round] if m.id == match_id and not m.completed),
        None,
    )
    if not match:
        return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)
    # Update match
    match_orm = await session.get(MatchORM, match_id)
    match_orm.score1 = score1
    match_orm.score2 = score2
    match_orm.completed = True

    # Update player stats
    players_map = {p.id: p for p in t_orm.players}
    for pid in match.team1:
        _update_player_stats(players_map[pid], score1, score2, delta=1)
    for pid in match.team2:
        _update_player_stats(players_map[pid], score2, score1, delta=1)

    await session.commit()
    
    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.post("/tournament/{tid}/next-round")
async def next_round(tid: str, session: AsyncSession = Depends(get_session),):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm:
        raise HTTPException(status_code=404)
    t = _orm_to_tournament(t_orm)
    # Check all matches in current round completed
    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        t_orm.current_round += 1
        await session.commit()

    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.post("/tournament/{tid}/finish")
async def finish_tournament(tid: str, session: AsyncSession = Depends(get_session),):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm:
        raise HTTPException(status_code=404)
    t = _orm_to_tournament(t_orm)
    
    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        t_orm.status = "finished"
        await session.commit()
    
    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

@router.post("/tournament/{tid}/delete")
async def delete_tournament(tid: str, session: AsyncSession = Depends(get_session),):
    t_orm = await session.get(TournamentORM, tid)
    if t_orm:
        await session.delete(t_orm)
        await session.commit()
    return RedirectResponse("/americano", status_code=303)

@router.post("/tournament/{tid}/edit-score")
async def edit_score(
    request: Request,
    tid: str,
    match_id: str = Form(...),
    score1: int = Form(...),
    score2: int = Form(...),
    session: AsyncSession = Depends(get_session),
):
    t_orm = await _get_tournament_orm(tid, session)
    t = _orm_to_tournament(t_orm)
    match = next(
        (m for rnd in t.rounds for m in rnd if m.id == match_id and m.completed),
        None,
    )
    if not match:
        return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)

    match_orm = await session.get(MatchORM, match_id)
    old1, old2 = match_orm.score1, match_orm.score2

    # Revert old stats, apply new stats
    players_map = {p.id: p for p in t_orm.players}
    for pid in match.team1:
        _update_player_stats(players_map[pid], old1, old2, delta=-1)
        _update_player_stats(players_map[pid], score1, score2, delta=1)
    for pid in match.team2:
        _update_player_stats(players_map[pid], old2, old1, delta=-1)
        _update_player_stats(players_map[pid], score2, score1, delta=1)

    match_orm.score1 = score1
    match_orm.score2 = score2
    await session.commit()

    return RedirectResponse(f"/americano/tournament/{tid}", status_code=303)


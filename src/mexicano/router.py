from fastapi import APIRouter, Form, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from mexicano.models import Player, Tournament, Match, generate_id
from mexicano.functions import generate_mexicano_round, calculate_standings
from database import get_session, TournamentORM, PlayerORM, MatchORM

router = APIRouter(prefix='/mexicano', tags=['Мексикано'])
templates = Jinja2Templates(directory="templates/mexicano")
# In-memory storage (could be replaced with DB)
# mexicano_db: dict = {}

# -- Helpers -------------------------------------------------------------------

def _orm_to_tournament(t_row: TournamentORM) -> Tournament:
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
    if not result or result.mode != "mexicano":
        raise HTTPException(status_code=404, detail="Tournament not found")
    return result


def _update_player_stats(
    player_orm: PlayerORM,
    score_for: int, score_against: int,
    delta: int = 1,
):
    player_orm.games_played += delta
    player_orm.points       += delta * score_for
    if score_for > score_against:
        player_orm.games_won  += delta
    else:
        player_orm.games_lost += delta


def _add_round_to_session(session: AsyncSession, tid: str, matches: list[Match]):
    for m in matches:
        session.add(MatchORM(
            id=m.id, tournament_id=tid,
            round=m.round, court=m.court,
            team1=m.team1, team2=m.team2,
        ))


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
    player_names: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    names = [n.strip() for n in player_names.split("\n") if n.strip()]
    if len(names) < 4:
        raise HTTPException(status_code=400, detail="Введите минимум 4 имени")

    tid = generate_id()
    player_orms = []
    players: dict[str, Player] = {}
    for pname in names:
        pid = generate_id()
        player_orms.append(PlayerORM(id=pid, tournament_id=tid, name=pname))
        players[pid] = Player(id=pid, name=pname, sex='M')

    # Build temporary Tournament to generate the first round
    temp = Tournament(
        id=tid, name=name, courts=courts, players=players,
        rounds=[], current_round=0, status="active",
    )
    first_round = generate_mexicano_round(temp, 0)

    t_orm = TournamentORM(
        id=tid, mode="mexicano", name=name, courts=courts,
        status="active", current_round=0, total_rounds=num_rounds,
    )
    session.add(t_orm)
    session.add_all(player_orms)
    _add_round_to_session(session, tid, first_round)

    await session.commit()
    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.head("/{tid}")
async def mexicano_head(tid: str, session: AsyncSession = Depends(get_session)):
    row = await session.get(TournamentORM, tid)
    if not row or row.mode != "mexicano":
        raise HTTPException(status_code=404)
    return Response(status_code=200)


@router.get("/{tid}", response_class=HTMLResponse)
async def mexicano_view(request: Request, tid: str, session: AsyncSession = Depends(get_session)):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm:
        raise HTTPException(status_code=404, detail="Tournament not found")
    t = _orm_to_tournament(t_orm)
    
    standings = calculate_standings(t)
    current_matches = t.rounds[t.current_round] if t.rounds and t.current_round < len(t.rounds) else []

    return templates.TemplateResponse("tournament.html", {
        "request": request,
        "tournament": t,
        "standings": standings,
        "current_matches": current_matches,
        "players": t.players,
        "total_rounds": t_orm.total_rounds,
        "mode": "mexicano",
    })


@router.post("/{tid}/score")
async def mexicano_score(
    tid: str,
    match_id: str = Form(...),
    score1: int = Form(...),
    score2: int = Form(...),
    session: AsyncSession = Depends(get_session),
):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm:
        raise HTTPException(status_code=404, detail="Tournament not found")
    t = _orm_to_tournament(t_orm)

    match = next(
        (m for m in t.rounds[t.current_round] if m.id == match_id and not m.completed),
        None,
    )
    if not match:
        return RedirectResponse(f"/mexicano/{tid}", status_code=303)

    match_orm = await session.get(MatchORM, match_id)
    match_orm.score1 = score1
    match_orm.score2 = score2
    match_orm.completed = True

    players_map = {p.id: p for p in t_orm.players}
    for pid in match.team1:
        _update_player_stats(players_map[pid], score1, score2, delta=1)
    for pid in match.team2:
        _update_player_stats(players_map[pid], score2, score1, delta=1)

    await session.commit()

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.post("/{tid}/next-round")
async def mexicano_next_round(tid: str, session: AsyncSession = Depends(get_session),):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm:
        raise HTTPException(status_code=404, detail="Tournament not found")
    t = _orm_to_tournament(t_orm)

    current = t.rounds[t.current_round]

    if not all(m.completed for m in current):
        return RedirectResponse(f"/mexicano/{tid}", status_code=303)

    new_round_num = t_orm.current_round + 1
    t_orm.current_round = new_round_num

    if new_round_num < t_orm.total_rounds:
        t.current_round = new_round_num   # update so standings are correct
        new_matches = generate_mexicano_round(t, new_round_num)
        _add_round_to_session(session, tid, new_matches)

    await session.commit()
    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.post("/{tid}/finish")
async def mexicano_finish(tid: str, session: AsyncSession = Depends(get_session),):
    t_orm = await _get_tournament_orm(tid, session)
    if not t_orm :
        raise HTTPException(status_code=404, detail="Tournament not found")
    t = _orm_to_tournament(t_orm)

    current = t.rounds[t.current_round]
    if all(m.completed for m in current):
        t_orm.status = "finished"
        await session.commit()

    return RedirectResponse(f"/mexicano/{tid}", status_code=303)


@router.post("/{tid}/delete")
async def mexicano_delete(tid: str, session: AsyncSession = Depends(get_session),):
    t_orm = await session.get(TournamentORM, tid)
    if t_orm:
        await session.delete(t_orm)
        await session.commit()
    return RedirectResponse("/mexicano", status_code=303)


@router.post("/{tid}/edit-score")
async def mexicano_edit_score(
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
        return RedirectResponse(f"/mexicano/{tid}", status_code=303)

    match_orm = await session.get(MatchORM, match_id)
    old1, old2 = match_orm.score1, match_orm.score2

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
    return RedirectResponse(f"/mexicano/{tid}", status_code=303)

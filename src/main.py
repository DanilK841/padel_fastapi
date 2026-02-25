import os

from fastapi import FastAPI, Request, Form, HTTPException, Response

from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from americano.router import router as americano_router
from mexicano.router import router as mexicano_router



app = FastAPI(title="Padel Americano")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# app = FastAPI()
app.include_router(americano_router)
app.include_router(mexicano_router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
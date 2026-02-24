from os import name

from fastapi import FastAPI, Request, Form, HTTPException, Response

from fastapi.staticfiles import StaticFiles
from pathlib import Path
from americano.router import router as americano_router
from mexicano.router import router as mexicano_router



app = FastAPI(title="Padel Americano")
app.mount("/static", StaticFiles(directory="static"), name="static")



# app = FastAPI()
app.include_router(americano_router)
app.include_router(mexicano_router)
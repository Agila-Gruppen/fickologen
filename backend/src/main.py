from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.users import router as UserRouter
from .routes.auth import router as AuthRouter
from .routes.chat import router as ChatRouter


app = FastAPI(
    title = "Fickologen",
    description= "REST API for Fickologen",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(UserRouter)
app.include_router(AuthRouter)
app.include_router(ChatRouter)

@app.get("/")
async def root():
    return {
        "message": "Fickologen API",
        "version": "1.0.0",
        "docs": "/docs"
    }

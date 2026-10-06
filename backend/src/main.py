from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.users import router as UserRouter
from .routes.auth import router as AuthRouter
from .routes.chat import router as ChatRouter

from .config.database import init_db


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

@app.on_event("startup")
async def startup_event():
    """
    Run when the application starts.
    Creates database tables if they don't exist.
    """
    print("\n" + "="*60)
    print("🔧 Initializing database...")
    print("="*60)
    init_db()
    print("="*60 + "\n")

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

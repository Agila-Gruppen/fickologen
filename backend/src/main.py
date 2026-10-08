from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.users import router as UserRouter
from .routes.auth import router as AuthRouter
from .routes.chat import router as ChatRouter
from .routes.admin import router as AdminRouter
from .config.database import SessionLocal
from .models.user import User
from .utils.admin import admin_usernames


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
async def sync_admin_roles() -> None:
    names = admin_usernames()
    db = SessionLocal()
    try:
        users = db.query(User).all()
        promoted, demoted = [], []
        for user in users:
            if user.username in names and user.role != "admin":
                user.role = "admin"
                promoted.append(user.username)
            elif user.username not in names and user.role == "admin":
                user.role = "user"
                demoted.append(user.username)
        if promoted or demoted:
            db.commit()
            if promoted:
                print(f"Promoted to admin: {promoted}")
            if demoted:
                print(f"Demoted from admin: {demoted}")
    finally:
        db.close()

app.include_router(UserRouter)
app.include_router(AuthRouter)
app.include_router(ChatRouter)
app.include_router(AdminRouter)

@app.get("/")
async def root():
    return {
        "message": "Fickologen API",
        "version": "1.0.0",
        "docs": "/docs"
    }
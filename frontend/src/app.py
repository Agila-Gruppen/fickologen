import streamlit as st

from components import get_current_view, load_css, logo_path, render_sidebar
from views import chat, diary, history, home, safety, saved, treatment

st.set_page_config(
    page_title="Fickologen",
    page_icon=str(logo_path()),
    layout="centered",
    initial_sidebar_state="expanded",
)

load_css()
render_sidebar()

VIEWS = {
    "home": home.render,
    "chat": chat.render,
    "diary": diary.render,
    "treatment": treatment.render,
    "history": history.render,
    "saved": saved.render,
    "safety": safety.render,
}

VIEWS[get_current_view()]()

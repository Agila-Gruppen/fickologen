"""The 12-week exercise program (PLAN-92).

Two screens: an overview of the weeks, and one week with its theory, exercises and
a reflection. On a week page the chat sits beside the text (it stacks below on a
phone), so the user can ask a question without leaving the exercise. The chat
shares the user's current conversation and tells the backend which week is open.
"""
import html

import streamlit as st

import program_api
from api import BackendUnavailable
from chat_engine import (
    GREETING,
    generate_pending_reply,
    get_messages,
    has_pending_reply,
    is_unlocked,
    send_user_message,
)
from components import open_account_dialog, page_header
from views.chat import render_bubble

WEEK_KEY = "fk_program_week"        # the week page that is open, or None for the overview
FLASH_KEY = "fk_program_flash"      # a message to show once after completing a week
EXERCISE_KEY_PREFIX = "fk_ex_"      # widget keys of the exercise forms, cleared when the program is reset
TOTAL_WEEKS = 12
CHAT_HEIGHT = 520
KIND_LABELS = {
    "reflektion": "Reflektion",
    "tankedagbok": "Tankedagbok",
    "ovning": "Övning",
    "experiment": "Experiment",
    "exponering": "Exponering",
}


def render() -> None:
    page_header(
        "Övningsprogram",
        "Tolv veckor, ett litet steg i taget",
        "Lite teori och några övningar varje vecka. Du går i din egen takt, och "
        "Fickologen finns i chatten bredvid om du undrar över något.",
    )
    if not is_unlocked():
        _render_login_cta()
        return
    if flash := st.session_state.pop(FLASH_KEY, None):
        st.toast(flash)
    try:
        number = st.session_state.get(WEEK_KEY)
        if number:
            _render_week_page(number)
        else:
            _render_overview()
    except BackendUnavailable:
        st.error("Kunde inte nå servern just nu. Försök igen om en liten stund.")


def _render_login_cta() -> None:
    st.markdown(
        '<div class="fk-card" style="text-align:center;">'
        '<span class="fk-card-icon">🌱</span>'
        '<div class="fk-card-title">Logga in för att börja</div>'
        '<p class="fk-card-text">Programmet sparar dina övningar och hur långt du kommit, '
        "så du behöver ett konto för att använda det.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        if st.button("Logga in / skapa konto", type="primary", use_container_width=True, key="fk_program_login"):
            open_account_dialog()


# ---------- Overview ----------

def _render_overview() -> None:
    overview, error = program_api.get_overview()
    if error:
        st.warning(error)
        return
    if not overview["started"]:
        _render_intro()
        return

    weeks = overview["weeks"]
    done = len(overview["completed_weeks"])
    if overview["finished"]:
        st.success("Du har gått igenom alla tolv veckorna. Det är något att vara stolt över.")
    else:
        st.markdown(f"**Vecka {overview['current_week']} av {TOTAL_WEEKS}** · {done} klara")
    st.progress(done / TOTAL_WEEKS)
    _render_timeline(weeks)

    if not overview["finished"]:
        current = weeks[overview["current_week"] - 1]
        st.markdown(
            f"""
            <div class="fk-card">
                <div class="fk-badge">Din vecka</div>
                <div class="fk-card-title">Vecka {current["week"]}: {html.escape(current["title"])}</div>
                <p class="fk-card-text">{html.escape(current["summary"])}</p>
                <p class="fk-card-text" style="font-size:0.82rem;">Cirka {current["minutes"]} minuter</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"Fortsätt med vecka {current['week']}", type="primary", key="fk_program_continue"):
            _open_week(current["week"])

    earlier = [w for w in weeks if w["status"] == "done" or (w["status"] == "open" and w["week"] != overview["current_week"])]
    if earlier:
        with st.expander("Tidigare veckor"):
            for week in earlier:
                left, right = st.columns([4, 1])
                left.markdown(f"**Vecka {week['week']}:** {week['title']}")
                if right.button("Öppna", key=f"fk_program_open_{week['week']}"):
                    _open_week(week["week"])
    if not overview["finished"] and overview["current_week"] < TOTAL_WEEKS:
        st.caption(f"Vecka {overview['current_week'] + 1}–{TOTAL_WEEKS} öppnas en i taget, när veckan före är klar.")

    with st.expander("Börja om"):
        st.caption("Tar bort dina framsteg och allt du skrivit i programmet. Det går inte att ångra.")
        sure = st.checkbox("Jag vill börja om från vecka 1", key="fk_program_reset_sure")
        if st.button("Börja om", disabled=not sure, key="fk_program_reset"):
            _, error = program_api.reset()
            if error:
                st.error(error)
            else:
                _forget_exercise_state()
                st.session_state.pop(WEEK_KEY, None)
                st.rerun()


def _render_intro() -> None:
    st.markdown(
        """
        <div class="fk-card">
            <span class="fk-card-icon">🌱</span>
            <div class="fk-badge">Utkast</div>
            <div class="fk-card-title">Så här fungerar programmet</div>
            <p class="fk-card-text">
                Programmet följer KBT, en metod med god evidens för social ångest.
                Varje vecka får du <b>lite teori</b>, <b>en eller två övningar</b> och en
                kort reflektion, cirka 25–40 minuter. Du övar i vardagen och skriver ner
                hur det gick.
            </p>
            <p class="fk-card-text">
                Du bestämmer takten. En ny vecka öppnas först när du är klar med den förra,
                och det är okej att ta längre tid. Om något är oklart kan du fråga i chatten
                som ligger bredvid texten.
            </p>
            <p class="fk-card-text" style="font-size:0.82rem;">
                Programmet är ett stöd och ersätter inte vård. Mår du dåligt: ring 1177,
                eller 112 vid akut fara. Texterna är ett utkast som ännu inte är klinisk granskade.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Starta programmet", type="primary", key="fk_program_start"):
        _, error = program_api.start()
        if error:
            st.error(error)
        else:
            st.rerun()


def _render_timeline(weeks: list[dict]) -> None:
    circles = []
    for week in weeks:
        extra = {"done": " fk-week-done", "open": " fk-week-active", "locked": " fk-week-locked"}[week["status"]]
        mark = "✓" if week["status"] == "done" else week["week"]
        circles.append(f'<div class="fk-week{extra}" title="{html.escape(week["title"])}">{mark}</div>')
    st.markdown(f'<div class="fk-timeline">{"".join(circles)}</div>', unsafe_allow_html=True)


def _open_week(number: int) -> None:
    st.session_state[WEEK_KEY] = number
    st.rerun()


def _forget_exercise_state() -> None:
    """Drop typed-in exercise text, so nothing from a reset program shows up again."""
    for key in [k for k in st.session_state if str(k).startswith(EXERCISE_KEY_PREFIX)]:
        del st.session_state[key]


# ---------- A week ----------

def _render_week_page(number: int) -> None:
    week, error = program_api.get_week(number)
    if error:
        st.warning(error)
        if st.button("← Alla veckor", key="fk_program_back_error"):
            st.session_state.pop(WEEK_KEY, None)
            st.rerun()
        return

    # Marker for the CSS: the week page is wider, to make room for the chat.
    st.markdown('<div class="fk-wide"></div>', unsafe_allow_html=True)
    top_left, top_right = st.columns([3, 2])
    with top_left:
        if st.button("← Alla veckor", key="fk_program_back"):
            st.session_state.pop(WEEK_KEY, None)
            st.rerun()
    with top_right:
        chat_on = st.toggle("💬 Chatten bredvid", value=True, key="fk_program_chat_on")

    if chat_on:
        left, right = st.columns([3, 2], gap="large")
        with right:
            _render_chat_panel(week)
    else:
        left = st.container()
    with left:
        _render_week_content(week)


def _render_week_content(week: dict) -> None:
    number = week["week"]
    st.markdown(
        f"""
        <div class="fk-week-head">
            <div class="fk-hero-eyebrow" style="text-align:left;">Vecka {number} av {TOTAL_WEEKS}</div>
            <h2 style="margin:0 0 0.4rem 0;">{html.escape(week["title"])}</h2>
            <p class="fk-card-text">{html.escape(week["summary"])} · cirka {week["minutes"]} minuter</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if week.get("safety_note"):
        st.markdown(f'<div class="fk-note">🛟 {html.escape(week["safety_note"])}</div>', unsafe_allow_html=True)

    st.markdown("#### Teori")
    with st.container(border=True, key="fk_program_theory"):
        st.markdown(week["theory"])

    st.markdown("#### Övningar")
    logs = {log["exercise_id"]: log for log in week["logs"]}
    for exercise in week["exercises"]:
        _render_exercise(number, exercise, logs.get(exercise["id"]))

    st.markdown("#### Reflektion")
    _render_reflection(number, week["reflection_prompt"], logs.get("reflektion"))

    _render_completion(week, logs)


def _render_exercise(number: int, exercise: dict, log: dict | None) -> None:
    exercise_id = exercise["id"]
    required = "Obligatorisk" if exercise["required"] else "Valfri"
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(exercise["steps"], start=1))
    with st.container(border=True, key=f"{EXERCISE_KEY_PREFIX}box_{exercise_id}"):
        st.markdown(
            f"""
            <div class="fk-badge">{required} · {KIND_LABELS.get(exercise["kind"], "Övning")} · cirka {exercise["minutes"]} min</div>
            <div class="fk-card-title">{html.escape(exercise["title"])}</div>
            <p class="fk-card-text"><i>Varför:</i> {html.escape(exercise["why"])}</p>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(steps)
        with st.form(f"{EXERCISE_KEY_PREFIX}form_{exercise_id}", border=False):
            before = after = None
            if exercise.get("measure_label"):
                st.caption(exercise["measure_label"])
                col_before, col_after = st.columns(2)
                before = col_before.number_input(
                    "Före (0–100)", 0, 100, value=log["rating_before"] if log else None,
                    step=5, placeholder="–", key=f"{EXERCISE_KEY_PREFIX}before_{exercise_id}",
                )
                after = col_after.number_input(
                    "Efter (0–100)", 0, 100, value=log["rating_after"] if log else None,
                    step=5, placeholder="–", key=f"{EXERCISE_KEY_PREFIX}after_{exercise_id}",
                )
            note = st.text_area(
                "Dina anteckningar",
                value=(log or {}).get("reflection") or "",
                height=110,
                key=f"{EXERCISE_KEY_PREFIX}note_{exercise_id}",
            )
            done = st.checkbox(
                "Jag har gjort den här övningen",
                value=bool(log and log["done"]),
                key=f"{EXERCISE_KEY_PREFIX}done_{exercise_id}",
            )
            saved = st.form_submit_button("Spara")
        if saved:
            error = program_api.save_exercise(
                number, exercise_id, done, note,
                None if before is None else int(before), None if after is None else int(after),
            )
            if error:
                st.error(error)
            else:
                st.toast("Sparat ✓")
                st.rerun()


def _render_reflection(number: int, prompt: str, log: dict | None) -> None:
    with st.form(f"{EXERCISE_KEY_PREFIX}form_reflektion_{number}", border=False):
        text = st.text_area(
            prompt,
            value=(log or {}).get("reflection") or "",
            height=100,
            key=f"{EXERCISE_KEY_PREFIX}note_reflektion_{number}",
        )
        saved = st.form_submit_button("Spara reflektion")
    if saved:
        error = program_api.save_exercise(number, "reflektion", False, text)
        if error:
            st.error(error)
        else:
            st.toast("Sparat ✓")
            st.rerun()


def _render_completion(week: dict, logs: dict[str, dict]) -> None:
    number = week["week"]
    st.markdown("---")
    if week["status"] == "done":
        st.success("Den här veckan är klar. Du kan titta tillbaka och ändra dina anteckningar när du vill.")
        if number < TOTAL_WEEKS and st.button(f"Gå till vecka {number + 1}", key="fk_program_next"):
            _open_week(number + 1)
        return

    if week["can_complete"]:
        st.caption("Bra jobbat. När du är redo kan du avsluta veckan och öppna nästa.")
    else:
        remaining = [e["title"] for e in week["exercises"] if e["required"] and not (logs.get(e["id"]) or {}).get("done")]
        st.caption("För att gå vidare behöver du markera som gjorda: " + ", ".join(remaining) + ".")
    if st.button("Klar med veckan ✓", type="primary", disabled=not week["can_complete"], key="fk_program_complete"):
        _, error = program_api.complete_week(number)
        if error:
            st.error(error)
            return
        st.session_state[FLASH_KEY] = (
            "Bra jobbat! Du har gått igenom hela programmet. 🌱" if number == TOTAL_WEEKS
            else f"Bra jobbat! Vecka {number + 1} är öppen. 🌱"
        )
        st.session_state.pop(WEEK_KEY, None)
        st.rerun()


# ---------- The chat beside the week ----------

def _render_chat_panel(week: dict) -> None:
    number = week["week"]
    st.markdown(f'<div class="fk-program-chat-title">💬 Fråga Fickologen om vecka {number}</div>', unsafe_allow_html=True)
    box = st.container(height=CHAT_HEIGHT, border=True, key="fk_program_chatbox")
    with box:
        messages = [m for m in get_messages() if not (m["role"] == "assistant" and m["content"] == GREETING)]
        if not messages:
            st.markdown(
                '<div class="fk-chat-intro" style="margin-top:1rem;">Undrar du över något i teorin eller '
                "en övning? Skriv här, så hjälper jag dig med den här veckan.</div>",
                unsafe_allow_html=True,
            )
        for message in messages:
            render_bubble(message)
        if has_pending_reply():
            with st.spinner("Fickologen reflekterar…"):
                generate_pending_reply(program_week=number)
            st.rerun()

    text = st.chat_input("Fråga om veckan…", key="fk_program_chat_input")
    if text:
        send_user_message(text)
        st.rerun()

    if week.get("chat_tips"):
        with st.expander("Förslag på frågor"):
            for i, tip in enumerate(week["chat_tips"]):
                if st.button(tip, key=f"fk_program_tip_{number}_{i}", use_container_width=True):
                    send_user_message(tip)
                    st.rerun()
    st.caption("Fickologen är en AI och ersätter inte vård. Vid akut kris: 112, eller Självmordslinjen 90101.")

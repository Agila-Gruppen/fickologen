"""12 veckor KBT: the guided exercise program (PLAN-92).

Two screens: an overview of the weeks, and one week with its theory, exercises and
a reflection. A week is one form with one save button, and you can move between
weeks from the top of the page. On a week page the chat sits beside the text (it
stacks below on a phone), so the user can ask a question without leaving the
exercise. The chat shares the user's current conversation and tells the backend
which week is open.
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
    start_new_conversation,
)
from components import open_account_dialog, page_header
from views.chat import render_bubble

PROGRAM_NAME = "12 veckor KBT"
WEEK_KEY = "fk_program_week"        # the week page that is open, or None for the overview
FLASH_KEY = "fk_program_flash"      # a message to show once, for example after completing a week
SCROLL_TOP_KEY = "fk_program_scroll_top"  # set when the page should start at the top (new week)
EXERCISE_KEY_PREFIX = "fk_ex_"      # widget keys of the exercise forms, cleared when the program is reset
TOTAL_WEEKS = 12
CHAT_HEIGHT = 440
STATUS_MARKS = {"done": "✓", "open": "", "locked": "🔒"}
KIND_LABELS = {
    "reflektion": "Reflektion",
    "tankedagbok": "Tankedagbok",
    "ovning": "Övning",
    "experiment": "Experiment",
    "exponering": "Exponering",
}

# Scroll helpers. Constant scripts, nothing from users or the model goes into them.
_SCROLL_TOP_JS = """
<script>
setTimeout(function () {
  var main = document.querySelector('[data-testid="stMain"]') || document.querySelector('section.main');
  if (main) { main.scrollTo({ top: 0 }); }
}, 120);
</script>
"""
_SCROLL_CHAT_JS = """
<script>
/* messages: __COUNT__ */
function fkScrollChat() {
  var box = document.querySelector('[class*="st-key-fk_program_chatbox"]');
  if (!box) { return; }
  var candidates = [box].concat(Array.prototype.slice.call(box.querySelectorAll('div')));
  candidates.forEach(function (el) {
    var overflow = window.getComputedStyle(el).overflowY;
    if ((overflow === 'auto' || overflow === 'scroll') && el.scrollHeight > el.clientHeight + 4) {
      el.scrollTop = el.scrollHeight;
    }
  });
}
setTimeout(fkScrollChat, 150);
setTimeout(fkScrollChat, 600);
</script>
"""


def render() -> None:
    page_header(
        PROGRAM_NAME,
        "Tolv veckor, ett litet steg i taget",
        "Lite teori och några övningar varje vecka. Du går i din egen takt, och "
        "Fickologen finns i chatten bredvid om du undrar över något.",
    )
    if not is_unlocked():
        _render_login_cta()
        return
    if flash := st.session_state.pop(FLASH_KEY, None):
        st.toast(flash)
    if st.session_state.pop(SCROLL_TOP_KEY, False):
        st.html(_SCROLL_TOP_JS, unsafe_allow_javascript=True)
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

    with st.expander("Alla veckor", expanded=done > 0):
        for week in weeks:
            left, right = st.columns([5, 1], vertical_alignment="center")
            mark = STATUS_MARKS[week["status"]] or "●"
            left.markdown(f"{mark} **Vecka {week['week']}:** {week['title']}")
            if week["status"] == "locked":
                right.caption("Öppnas senare")
            elif right.button("Öppna", key=f"fk_program_open_{week['week']}"):
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
                och det är okej att ta längre tid. Du kan alltid gå tillbaka till en tidigare
                vecka. Om något är oklart kan du fråga i chatten som ligger bredvid texten.
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
    st.session_state[SCROLL_TOP_KEY] = True
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
    overview, error = program_api.get_overview()
    if error:
        st.warning(error)
        return

    # Marker for the CSS: the week page is wider, to make room for the chat.
    st.markdown('<div class="fk-wide"></div>', unsafe_allow_html=True)
    chat_on = _render_week_navigation(number, overview["weeks"])

    if chat_on:
        left, right = st.columns([3, 2], gap="large")
        with right:
            _render_chat_panel(week)
    else:
        left = st.container()
    with left:
        _render_week_content(week)


def _render_week_navigation(number: int, weeks: list[dict]) -> bool:
    """Back to the overview, previous/next week, a week picker and the chat switch. Returns whether the chat is on."""
    statuses = {w["week"]: w["status"] for w in weeks}
    titles = {w["week"]: w["title"] for w in weeks}
    back, previous, picker, following, chat = st.columns([1.3, 1.3, 3, 1.3, 1.8], vertical_alignment="center")
    if back.button("← Alla veckor", key="fk_program_back", use_container_width=True):
        st.session_state.pop(WEEK_KEY, None)
        st.session_state[SCROLL_TOP_KEY] = True
        st.rerun()
    if previous.button("‹ Förra veckan", key="fk_program_prev", disabled=number <= 1, use_container_width=True):
        _open_week(number - 1)
    picker_key = f"fk_program_jump_{number}"
    if picker_key not in st.session_state:
        st.session_state[picker_key] = number
    picker.selectbox(
        "Byt vecka",
        list(range(1, TOTAL_WEEKS + 1)),
        format_func=lambda n: f"{STATUS_MARKS[statuses[n]]} Vecka {n}: {titles[n]}".strip(),
        key=picker_key,
        label_visibility="collapsed",
        on_change=_jump_to_week,
        args=(number, statuses),
    )
    next_locked = number >= TOTAL_WEEKS or statuses.get(number + 1) == "locked"
    if following.button(
        "Nästa vecka ›", key="fk_program_next_nav", disabled=next_locked, use_container_width=True,
        help="Nästa vecka öppnas när du är klar med den här." if next_locked and number < TOTAL_WEEKS else None,
    ):
        _open_week(number + 1)
    chat_on = chat.toggle("💬 Chatten bredvid", value=True, key="fk_program_chat_on")
    st.caption("Tryck på Spara längst ner innan du byter vecka, så följer det du skrivit med.")
    return chat_on


def _jump_to_week(current: int, statuses: dict[int, str]) -> None:
    """Callback of the week picker: go to the chosen week, or explain why it is not open yet."""
    picker_key = f"fk_program_jump_{current}"
    chosen = st.session_state[picker_key]
    if statuses.get(chosen) == "locked":
        st.session_state[picker_key] = current
        st.session_state[FLASH_KEY] = f"Vecka {chosen} öppnas när du är klar med veckan före."
        return
    st.session_state[WEEK_KEY] = chosen
    st.session_state[SCROLL_TOP_KEY] = True


def _render_week_content(week: dict) -> None:
    number = week["week"]
    logs = {log["exercise_id"]: log for log in week["logs"]}
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

    st.markdown("#### 1. Läs")
    with st.container(border=True, key="fk_program_theory"):
        st.markdown(week["theory"])

    st.markdown("#### 2. Gör övningarna")
    _render_todo(week, logs)
    values = _render_week_form(week, logs)
    if values is not None:
        _handle_submit(week, logs, *values)


def _render_todo(week: dict, logs: dict[str, dict]) -> None:
    """A short checklist of what the week asks for, with what is already saved ticked off."""
    items = []
    for exercise in week["exercises"]:
        done = bool((logs.get(exercise["id"]) or {}).get("done"))
        optional = "" if exercise["required"] else " (valfri)"
        css = "fk-todo-item fk-todo-done" if done else "fk-todo-item"
        mark = "✓" if done else "○"
        items.append(f'<span class="{css}">{mark} {html.escape(exercise["title"])}{optional}</span>')
    st.markdown(f'<div class="fk-todo">{"".join(items)}</div>', unsafe_allow_html=True)


def _render_week_form(week: dict, logs: dict[str, dict]) -> tuple[dict, bool] | None:
    """
    All exercises and the reflection in one form, so one press on Save keeps everything.
    Returns (what was typed per exercise, whether to go on to the next week), or None if nothing was submitted.
    """
    number = week["week"]
    finished = week["status"] == "done"
    with st.form(f"{EXERCISE_KEY_PREFIX}form_week_{number}", border=False):
        values = {
            exercise["id"]: _render_exercise(exercise, logs.get(exercise["id"]))
            for exercise in week["exercises"]
        }
        st.markdown("#### 3. Avsluta med en reflektion")
        reflection_log = logs.get("reflektion")
        values["reflektion"] = {
            "done": False,
            "note": st.text_area(
                week["reflection_prompt"] + " (valfritt)",
                value=(reflection_log or {}).get("reflection") or "",
                height=100,
                key=f"{EXERCISE_KEY_PREFIX}note_reflektion_{number}",
            ),
            "before": None,
            "after": None,
        }
        save_col, go_col = st.columns(2)
        saved = save_col.form_submit_button("Spara", use_container_width=True)
        if finished and number < TOTAL_WEEKS:
            go_label = f"Spara och gå till vecka {number + 1} ›"
        elif finished:
            go_label = None
        elif number == TOTAL_WEEKS:
            go_label = "Spara och avsluta programmet ✓"
        else:
            go_label = "Spara och avsluta veckan ✓"
        proceed = bool(go_label) and go_col.form_submit_button(go_label, type="primary", use_container_width=True)
    if saved or proceed:
        return values, proceed
    return None


def _render_exercise(exercise: dict, log: dict | None) -> dict:
    """One exercise card with its fields. Returns what is currently typed (only final after a submit)."""
    exercise_id = exercise["id"]
    required = "Obligatorisk" if exercise["required"] else "Valfri"
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(exercise["steps"], start=1))
    with st.container(border=True, key=f"{EXERCISE_KEY_PREFIX}box_{exercise_id}"):
        st.markdown(
            f"""
            <div class="fk-badge">{required} · {KIND_LABELS.get(exercise["kind"], "Övning")} · cirka {exercise["minutes"]} min</div>
            <div class="fk-card-title">{html.escape(exercise["title"])}</div>
            """,
            unsafe_allow_html=True,
        )
        # .get: during a deploy the frontend can be newer than the backend for a few minutes.
        if task := exercise.get("task"):
            st.markdown(
                f'<div class="fk-task"><div class="fk-task-label">Din uppgift</div>{html.escape(task)}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("**Så här gör du**")
        st.markdown(steps)
        st.caption("Varför: " + exercise["why"])

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
            exercise.get("write_label") or "Dina anteckningar",
            value=(log or {}).get("reflection") or "",
            height=110,
            key=f"{EXERCISE_KEY_PREFIX}note_{exercise_id}",
        )
        done = st.checkbox(
            "Jag har gjort den här övningen",
            value=bool(log and log["done"]),
            key=f"{EXERCISE_KEY_PREFIX}done_{exercise_id}",
        )
    return {
        "done": done,
        "note": note,
        "before": None if before is None else int(before),
        "after": None if after is None else int(after),
    }


def _changed(old: dict | None, new: dict) -> bool:
    """Whether what is typed differs from what is saved (an empty exercise that was never saved counts as unchanged)."""
    typed = new["note"].strip()
    if old is None:
        return bool(new["done"] or typed or new["before"] is not None or new["after"] is not None)
    return (
        bool(old["done"]) != new["done"]
        or (old.get("reflection") or "") != typed
        or old.get("rating_before") != new["before"]
        or old.get("rating_after") != new["after"]
    )


def _save_changes(number: int, logs: dict[str, dict], values: dict[str, dict]) -> str | None:
    """Saves every exercise that changed. Returns an error message for the user, or None."""
    for exercise_id, new in values.items():
        if not _changed(logs.get(exercise_id), new):
            continue
        error = program_api.save_exercise(number, exercise_id, new["done"], new["note"], new["before"], new["after"])
        if error:
            return error
    return None


def _handle_submit(week: dict, logs: dict[str, dict], values: dict[str, dict], proceed: bool) -> None:
    number = week["week"]
    if error := _save_changes(number, logs, values):
        st.error(error)
        return
    if not proceed:
        st.toast("Sparat ✓")
        st.rerun()

    if week["status"] == "done":
        if number < TOTAL_WEEKS:
            _open_week(number + 1)
        st.rerun()

    missing = [e["title"] for e in week["exercises"] if e["required"] and not values[e["id"]]["done"]]
    if missing:
        st.warning(
            "Det du skrivit är sparat. För att avsluta veckan behöver du också markera som gjorda: "
            + ", ".join(missing) + "."
        )
        return
    _, error = program_api.complete_week(number)
    if error:
        st.error(error)
        return
    if number == TOTAL_WEEKS:
        st.session_state[FLASH_KEY] = "Bra jobbat! Du har gått igenom hela programmet. 🌱"
        st.session_state.pop(WEEK_KEY, None)
        st.session_state[SCROLL_TOP_KEY] = True
        st.rerun()
    st.session_state[FLASH_KEY] = f"Bra jobbat! Vecka {number + 1} är öppen. 🌱"
    _open_week(number + 1)


# ---------- The chat beside the week ----------

def _render_chat_panel(week: dict) -> None:
    number = week["week"]
    with st.container(key="fk_program_chatpanel"):
        title, new_chat = st.columns([3, 2], vertical_alignment="center")
        title.markdown(f'<div class="fk-program-chat-title">💬 Fråga om vecka {number}</div>', unsafe_allow_html=True)
        if new_chat.button("➕ Ny chatt", key="fk_program_new_chat", use_container_width=True):
            start_new_conversation()
            st.rerun()

        messages = [m for m in get_messages() if not (m["role"] == "assistant" and m["content"] == GREETING)]
        box = st.container(height=CHAT_HEIGHT, border=True, key="fk_program_chatbox")
        with box:
            if not messages:
                st.markdown(
                    '<div class="fk-chat-intro" style="margin:0.6rem 0 0.8rem 0;">Undrar du över något i teorin eller '
                    "en övning? Skriv nedan, eller välj en fråga:</div>",
                    unsafe_allow_html=True,
                )
                _render_tip_buttons(week, prefix="fk_chip_program")
            for message in messages:
                render_bubble(message, compact=True)
            if has_pending_reply():
                with st.spinner("Fickologen reflekterar…"):
                    generate_pending_reply(program_week=number)
                st.rerun()
        st.html(_SCROLL_CHAT_JS.replace("__COUNT__", str(len(messages))), unsafe_allow_javascript=True)

        text = st.chat_input("Skriv din fråga här…", key="fk_program_chat_input")
        if text:
            send_user_message(text)
            st.rerun()

        if messages and week.get("chat_tips"):
            with st.expander("Förslag på frågor"):
                _render_tip_buttons(week, prefix="fk_program_tip")
        st.caption("Fickologen är en AI och ersätter inte vård. Vid akut kris: 112, eller Självmordslinjen 90101.")


def _render_tip_buttons(week: dict, prefix: str) -> None:
    for i, tip in enumerate(week.get("chat_tips") or []):
        if st.button(tip, key=f"{prefix}_{week['week']}_{i}", use_container_width=True):
            send_user_message(tip)
            st.rerun()

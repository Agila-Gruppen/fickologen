import html
import re
from datetime import date, datetime, timedelta
from datetime_utils import STOCKHOLM, to_local

import streamlit as st

import auth
import diary_api
from api import BackendUnavailable
from components import open_account_dialog, page_header

MOODS = {
    1: "😞 Tungt",
    2: "🙁 Lite tungt",
    3: "😐 Okej",
    4: "🙂 Ganska bra",
    5: "😊 Bra",
}

WEEKDAYS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
MONTHS = [
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december",
]

WEEKDAYS_SHORT = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"]
MONTHS_SHORT = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
MOOD_EMOJI = {mood: label.split(" ", 1)[0] for mood, label in MOODS.items()}

VIEWS = {"week": "Vecka", "all": "Alla anteckningar"}

BACKEND_ERROR = "Kunde inte nå servern just nu. Försök igen om en liten stund."


def render() -> None:
    page_header(
        "Dagbok",
        "Ett ställe för tankarna mellan samtalen",
        "Inget du skriver här behöver vara ordnat eller korrekt – det räcker att "
        "det är sant för dig just nu.",
    )

    if not auth.current_user():
        _render_logged_out()
        return

    # Set before an st.rerun(), shown here once the page has redrawn.
    if flash := st.session_state.pop("fk_diary_flash", None):
        st.toast(flash)

    try:
        _render_composer()
        search = _render_search()
        view = st.segmented_control(
            "Visa",
            options=list(VIEWS),
            format_func=VIEWS.get,
            default="week",
            key="fk_diary_view",
            label_visibility="collapsed",
        )
        entries = diary_api.list_entries(search=search or None)
        if view == "all" or search:
            _render_entries(entries, search)
        else:
            _render_week(entries)
    except diary_api.SessionExpired:
        st.error(auth.SESSION_EXPIRED)
    except BackendUnavailable:
        st.error(BACKEND_ERROR)


def _render_logged_out() -> None:
    st.markdown(
        """
        <div class="fk-card">
            <span class="fk-card-icon">📓</span>
            <div class="fk-card-title">Din dagbok</div>
            <p class="fk-card-text">
                Dagboken sparas på ditt konto, så att du kan komma tillbaka till den.
                Logga in eller skapa ett konto för att börja skriva – du behöver inte
                uppge vem du är.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Logga in / skapa konto", key="diary_login_btn", type="primary"):
        open_account_dialog()


def _mood_picker(key: str, default: int | None = None) -> int | None:
    return st.segmented_control(
        "Hur mår du? (valfritt)",
        options=list(MOODS),
        format_func=lambda m: MOODS[m],
        default=default,
        key=key,
    )


def _render_composer() -> None:
    with st.container(key="fk_diary_composer"):
        st.markdown('<div class="fk-card-title">Skriv något nytt</div>', unsafe_allow_html=True)
        with st.form("fk_diary_new", border=False, clear_on_submit=True):
            title = st.text_input("Rubrik (valfri)", max_chars=200)
            content = st.text_area(
                "Anteckning",
                height=160,
                placeholder="Vad har du i tankarna just nu?",
                label_visibility="collapsed",
            )
            mood = _mood_picker("fk_diary_new_mood")
            submitted = st.form_submit_button("Spara anteckning", type="primary")
        if submitted:
            if not content.strip():
                st.warning("Skriv något i anteckningen innan du sparar.")
                return
            diary_api.create_entry(title.strip(), content.strip(), mood)
            # Jump to this week so the new entry is in view.
            st.session_state["fk_diary_week_offset"] = 0
            st.toast("Anteckningen är sparad. 🌱")
            
def _render_search() -> str:
    """Sökfält över anteckningslistan. Returnerar söktermen (stripad)."""
    value = st.text_input(
        "Sök i dagboken",
        key="fk_diary_search",
        placeholder="Sök bland dina anteckningar…",
        label_visibility="collapsed",
    )
    return (value or "").strip()


def _render_entries(entries: list[dict], search: str = "") -> None:
    st.markdown('<div class="fk-section-title">Dina anteckningar</div>', unsafe_allow_html=True)
    if not entries:
        if search:
            st.markdown(
                '<p class="fk-chat-intro" style="text-align:left;">'
                f"Inga anteckningar matchade <em>{html.escape(search)}</em>.</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p class="fk-chat-intro" style="text-align:left;">'
                "Inga anteckningar än – det du skriver hamnar här.</p>",
                unsafe_allow_html=True,
            )
        return

    for entry in entries:
        if st.session_state.get("fk_diary_editing") == entry["id"]:
            _render_edit_form(entry)
        else:
            _render_entry(entry, search)


def _today() -> date:
    return datetime.now(STOCKHOLM).date()


def _entry_day(entry: dict) -> date | None:
    dt = to_local(entry["created_at"])
    return dt.date() if dt else None


def _week_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    start = f"{monday.day} {MONTHS_SHORT[monday.month - 1]}"
    if monday.year != sunday.year:
        start += f" {monday.year}"
    end = f"{sunday.day} {MONTHS_SHORT[sunday.month - 1]} {sunday.year}"
    return f"Vecka {monday.isocalendar().week} · {start} – {end}"


def _day_mood(day_entries: list[dict]) -> int | None:
    """The day's mood: the average of the entries that have one, rounded."""
    moods = [e["mood"] for e in day_entries if e.get("mood") in MOODS]
    return round(sum(moods) / len(moods)) if moods else None


def _render_week(entries: list[dict]) -> None:
    offset = st.session_state.get("fk_diary_week_offset", 0)
    today = _today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    days = [monday + timedelta(days=i) for i in range(7)]

    by_day: dict[date, list[dict]] = {day: [] for day in days}
    for entry in entries:
        day = _entry_day(entry)
        if day in by_day:
            by_day[day].append(entry)

    prev, label, nxt = st.columns([1, 4, 1], vertical_alignment="center")
    if prev.button("◀", key="diary_week_prev", help="Föregående vecka", use_container_width=True):
        st.session_state["fk_diary_week_offset"] = offset - 1
        st.rerun()
    label.markdown(f'<div class="fk-week-label">{_week_label(monday)}</div>', unsafe_allow_html=True)
    # No browsing into the future: nothing can be written there.
    if nxt.button("▶", key="diary_week_next", help="Nästa vecka", disabled=offset >= 0, use_container_width=True):
        st.session_state["fk_diary_week_offset"] = offset + 1
        st.rerun()

    cells = []
    for day in days:
        day_entries = by_day[day]
        mood = _day_mood(day_entries)
        if mood:
            marker = f'<span class="fk-week-mood" title="{MOODS[mood]}">{MOOD_EMOJI[mood]}</span>'
        elif day_entries:
            marker = '<span class="fk-week-dot" title="Anteckning utan humör">●</span>'
        else:
            marker = '<span class="fk-week-none"></span>'
        classes = "fk-week-day"
        if day == today:
            classes += " fk-week-today"
        if day > today:
            classes += " fk-week-future"
        cells.append(
            f'<div class="{classes}">'
            f'<span class="fk-week-weekday">{WEEKDAYS_SHORT[day.weekday()]}</span>'
            f'<span class="fk-week-date">{day.day}</span>'
            f"{marker}</div>"
        )
    st.markdown(f'<div class="fk-week-strip">{"".join(cells)}</div>', unsafe_allow_html=True)

    week_entries = [e for day in days for e in by_day[day]]
    moods = [e["mood"] for e in week_entries if e.get("mood") in MOODS]
    summary = f"{len(week_entries)} {'anteckning' if len(week_entries) == 1 else 'anteckningar'}"
    if moods:
        average = sum(moods) / len(moods)
        decimal = f"{average:.1f}".replace(".", ",")
        summary += f" · humör i snitt {MOODS[round(average)]} ({decimal})"
    st.markdown(f'<p class="fk-week-summary">{summary}</p>', unsafe_allow_html=True)

    if offset != 0 and st.button("Till den här veckan", key="diary_week_today"):
        st.session_state["fk_diary_week_offset"] = 0
        st.rerun()

    if not week_entries:
        st.markdown(
            '<p class="fk-chat-intro" style="text-align:left;">'
            "Inga anteckningar den här veckan.</p>",
            unsafe_allow_html=True,
        )
        return

    # Newest day first, like the full list.
    for day in reversed(days):
        if not by_day[day]:
            continue
        st.markdown(
            f'<div class="fk-week-day-heading">{WEEKDAYS[day.weekday()].capitalize()} '
            f"{day.day} {MONTHS[day.month - 1]}</div>",
            unsafe_allow_html=True,
        )
        for entry in by_day[day]:
            if st.session_state.get("fk_diary_editing") == entry["id"]:
                _render_edit_form(entry)
            else:
                _render_entry(entry)


def _format_date(value: str) -> str:
    dt = to_local(value)
    if dt is None:
        return value
    return f"{WEEKDAYS[dt.weekday()].capitalize()} {dt.day} {MONTHS[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def _highlight(text: str, search: str) -> str:
    """Omsluter varje case-insensitive match i söktermen med <mark>."""
    if not search:
        return text
    pattern = re.compile(re.escape(search), re.IGNORECASE)
    return pattern.sub(lambda m: f'<mark class="fk-diary-mark">{m.group(0)}</mark>', text)


def _render_entry(entry: dict, search: str = "") -> None:
    entry_id = entry["id"]
    mood = f'<span class="fk-diary-mood">{MOODS[entry["mood"]]}</span>' if entry.get("mood") in MOODS else ""
    title_html = _highlight(html.escape(entry["title"]), search) if entry.get("title") else ""
    title = f'<div class="fk-card-title">{title_html}</div>' if entry.get("title") else ""
    # <br> rather than raw newlines: a blank line would end the HTML block and
    # let markdown take over the rest of the text.
    content = _highlight(
        html.escape(entry["content"]).replace("\r\n", "\n").replace("\n", "<br>"),
        search,
    )
    st.markdown(
        '<div class="fk-diary-entry">'
        f'<div class="fk-diary-meta"><span>{_format_date(entry["created_at"])}</span>{mood}</div>'
        f'{title}'
        f'<div class="fk-diary-content">{content}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("fk_diary_deleting") == entry_id:
        st.markdown(
            '<p class="fk-card-text">Vill du radera anteckningen? Det går inte att ångra.</p>',
            unsafe_allow_html=True,
        )
        yes, no, _ = st.columns([1.3, 1, 2])
        if yes.button("Ja, radera", key=f"diary_confirmdelete_{entry_id}", use_container_width=True):
            diary_api.delete_entry(entry_id)
            st.session_state.pop("fk_diary_deleting", None)
            st.session_state["fk_diary_flash"] = "Anteckningen är raderad."
            st.rerun()
        if no.button("Avbryt", key=f"diary_canceldelete_{entry_id}", use_container_width=True):
            st.session_state.pop("fk_diary_deleting", None)
            st.rerun()
    else:
        edit, delete, _ = st.columns([1, 1, 3])
        if edit.button("Redigera", key=f"diary_edit_{entry_id}", use_container_width=True):
            st.session_state["fk_diary_editing"] = entry_id
            st.session_state.pop("fk_diary_deleting", None)
            st.rerun()
        if delete.button("Radera", key=f"diary_delete_{entry_id}", use_container_width=True):
            st.session_state["fk_diary_deleting"] = entry_id
            st.rerun()
    st.markdown('<div style="height:0.8rem;"></div>', unsafe_allow_html=True)


def _render_edit_form(entry: dict) -> None:
    entry_id = entry["id"]
    with st.container(key=f"fk_diary_editbox_{entry_id}"):
        with st.form(f"fk_diary_edit_{entry_id}", border=False):
            title = st.text_input("Rubrik (valfri)", value=entry.get("title") or "", max_chars=200)
            content = st.text_area("Anteckning", value=entry["content"], height=160)
            mood = _mood_picker(f"fk_diary_edit_mood_{entry_id}", entry.get("mood"))
            save, cancel, _ = st.columns([1, 1, 2])
            saved = save.form_submit_button("Spara", type="primary", use_container_width=True)
            cancelled = cancel.form_submit_button("Avbryt", use_container_width=True)
    if cancelled:
        st.session_state.pop("fk_diary_editing", None)
        st.rerun()
    if saved:
        content_text = content or ""
        if not content_text.strip():
            st.warning("Anteckningen kan inte vara tom.")
            return
        diary_api.update_entry(entry_id, title.strip(), content_text.strip(), mood)
        st.session_state.pop("fk_diary_editing", None)
        st.session_state["fk_diary_flash"] = "Ändringarna är sparade."
        st.rerun()

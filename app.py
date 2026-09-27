import hashlib
import hmac
import secrets
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.config import settings
from src.errors import DattaAIError
from src.logger import get_logger


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="datta.ai — AI Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = settings.database_path
logger = get_logger("app")


# ============================================================
# PROFESSIONAL UI
# ============================================================

st.markdown(
    """
    <style>
        :root {
            --bg: #f6f8fc;
            --card: #ffffff;
            --text: #111827;
            --muted: #667085;
            --border: #e5e7eb;
            --accent: #4f46e5;
            --accent2: #7c3aed;
            --soft: #eef2ff;
        }

        .stApp {
            background: var(--bg);
        }

        [data-testid="stHeader"] {
            background: rgba(246, 248, 252, 0.92);
        }

        .block-container {
            max-width: 1280px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 3px;
        }

        .brand-icon {
            width: 43px;
            height: 43px;
            border-radius: 13px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            color: white;
            font-size: 21px;
            box-shadow: 0 8px 22px rgba(79, 70, 229, 0.22);
        }

        .brand-name {
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.035em;
            color: var(--text);
        }

        .brand-tag {
            color: var(--muted);
            font-size: 0.78rem;
            margin-left: 55px;
            margin-top: -7px;
            margin-bottom: 18px;
        }

        .hero {
            background:
                radial-gradient(circle at 85% 15%, rgba(99, 102, 241, 0.20), transparent 34%),
                radial-gradient(circle at 10% 90%, rgba(124, 58, 237, 0.12), transparent 30%),
                #111827;
            border-radius: 24px;
            padding: 34px 38px;
            color: white;
            margin-bottom: 22px;
            box-shadow: 0 18px 45px rgba(17, 24, 39, 0.14);
        }

        .hero-kicker {
            color: #c7d2fe;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .hero-title {
            font-size: clamp(2rem, 4vw, 3.1rem);
            line-height: 1.05;
            font-weight: 850;
            letter-spacing: -0.045em;
            margin-bottom: 12px;
        }

        .hero-copy {
            color: #d1d5db;
            font-size: 1rem;
            max-width: 760px;
            line-height: 1.65;
        }

        .feature-row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 20px;
        }

        .feature-pill {
            border: 1px solid rgba(255,255,255,0.13);
            background: rgba(255,255,255,0.07);
            color: #e5e7eb;
            padding: 7px 11px;
            border-radius: 999px;
            font-size: 0.78rem;
        }

        .section-label {
            color: var(--muted);
            font-size: 0.73rem;
            font-weight: 800;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin: 4px 0 8px;
        }

        .question-card {
            background: var(--soft);
            border: 1px solid #dfe4ff;
            border-radius: 18px;
            padding: 17px 20px;
            margin: 14px 0;
        }

        .question-label {
            color: var(--accent);
            font-size: 0.70rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 7px;
        }

        .question-text {
            color: #1f2937;
            font-size: 1rem;
            line-height: 1.55;
            font-weight: 600;
        }

        .report-card {
            background: white;
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 24px 28px;
            box-shadow: 0 8px 28px rgba(15, 23, 42, 0.05);
            margin-bottom: 20px;
        }

        .report-card h1,
        .report-card h2,
        .report-card h3 {
            color: #111827;
            letter-spacing: -0.025em;
        }

        .report-card h1 {
            font-size: 1.65rem;
            margin-top: 0.25rem;
            margin-bottom: 0.9rem;
        }

        .report-card h2 {
            font-size: 1.28rem;
            margin-top: 1.5rem;
            margin-bottom: 0.65rem;
        }

        .report-card h3 {
            font-size: 1.05rem;
        }

        .report-card p,
        .report-card li {
            font-size: 0.96rem;
            line-height: 1.7;
            color: #374151;
        }

        .empty-state {
            background: white;
            border: 1px dashed #cbd5e1;
            border-radius: 22px;
            padding: 48px 25px;
            text-align: center;
            margin-top: 18px;
        }

        .empty-icon {
            font-size: 2.2rem;
            margin-bottom: 8px;
        }

        .empty-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: #111827;
        }

        .empty-copy {
            color: #667085;
            max-width: 580px;
            margin: 7px auto 0;
            line-height: 1.55;
        }

        .history-title {
            font-size: 0.73rem;
            color: #667085;
            font-weight: 800;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin: 18px 0 8px;
        }

        .history-meta {
            color: #98a2b3;
            font-size: 0.70rem;
            margin-top: 2px;
        }

        .account-card {
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 11px 12px;
            margin: 10px 0 12px;
        }

        .account-name {
            font-weight: 750;
            color: #111827;
            font-size: 0.88rem;
        }

        .account-type {
            color: #667085;
            font-size: 0.72rem;
            margin-top: 2px;
        }

        .auth-shell {
            max-width: 620px;
            margin: 2vh auto 0;
        }

        .auth-brand {
            text-align: center;
            margin-bottom: 14px;
        }

        .auth-icon {
            width: 58px;
            height: 58px;
            margin: 0 auto 12px;
            border-radius: 17px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            color: white;
            font-size: 27px;
            box-shadow: 0 14px 32px rgba(79, 70, 229, 0.22);
        }

        .auth-title {
            font-size: 2rem;
            font-weight: 850;
            letter-spacing: -0.04em;
            color: #111827;
        }

        .auth-subtitle {
            color: #667085;
            margin-top: 4px;
            font-size: 0.95rem;
        }

        /* Compact authentication tabs */
        [data-baseweb="tab-list"] {
            gap: 6px !important;
            margin-bottom: 8px !important;
        }

        [data-baseweb="tab"] {
            color: #667085 !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            padding: 7px 8px !important;
        }

        [data-baseweb="tab"][aria-selected="true"] {
            color: #ef4444 !important;
        }

        [data-baseweb="tab-highlight"] {
            background-color: #ef4444 !important;
        }

        /* Reduce vertical whitespace in authentication forms */
        [data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
        }

        [data-testid="stTextInput"] {
            margin-bottom: 0.35rem !important;
        }

        [data-testid="stTextInput"] label {
            margin-bottom: 0.15rem !important;
        }

        [data-testid="stTextInput"] input {
            min-height: 42px !important;
        }

        .guest-box {
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 15px;
            padding: 15px 16px;
            margin-top: 16px;
        }

        /* Research report typography */
        [data-testid="stMarkdownContainer"] h1 {
            font-size: 1.95rem !important;
            line-height: 1.18 !important;
            letter-spacing: -0.035em !important;
            margin-top: 1.1rem !important;
            margin-bottom: 0.65rem !important;
            color: #111827 !important;
        }

        [data-testid="stMarkdownContainer"] h2 {
            font-size: 1.45rem !important;
            line-height: 1.25 !important;
            letter-spacing: -0.025em !important;
            margin-top: 1.45rem !important;
            margin-bottom: 0.65rem !important;
            color: #1f2937 !important;
        }

        [data-testid="stMarkdownContainer"] h3 {
            font-size: 1.12rem !important;
            line-height: 1.35 !important;
            margin-top: 1.1rem !important;
            margin-bottom: 0.45rem !important;
            color: #374151 !important;
        }

        [data-testid="stMarkdownContainer"] p {
            line-height: 1.72 !important;
        }

        [data-testid="stMarkdownContainer"] li {
            line-height: 1.65 !important;
            margin-bottom: 0.35rem !important;
        }

        [data-testid="stMarkdownContainer"] blockquote {
            border-left: 4px solid #6366f1 !important;
            background: #f8faff !important;
            padding: 0.75rem 1rem !important;
            border-radius: 0 10px 10px 0 !important;
            color: #475467 !important;
        }

        .report-shell {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
            padding: 24px 28px;
            box-shadow: 0 8px 28px rgba(15, 23, 42, 0.05);
        }

        .report-meta {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 4px;
        }

        .report-chip {
            display: inline-block;
            padding: 5px 9px;
            border-radius: 999px;
            background: #f1f5f9;
            color: #475467;
            font-size: 0.72rem;
            font-weight: 700;
        }


        .footer {
            color: #98a2b3;
            text-align: center;
            font-size: 0.74rem;
            padding-top: 22px;
        }

        .stButton > button {
            border-radius: 11px;
            font-weight: 700;
            min-height: 40px;
        }

        [data-testid="stChatInput"] {
            margin-top: 12px;
        }

        [data-testid="stSidebar"] .stButton > button {
            text-align: left;
            white-space: normal;
            height: auto;
            padding: 8px 9px;
            font-weight: 600;
            border: 1px solid transparent;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATABASE
# ============================================================

def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                password_salt TEXT,
                is_guest INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.commit()


def hash_password(password: str, salt: bytes | None = None):
    if salt is None:
        salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )

    return digest.hex(), salt.hex()


def verify_password(password: str, password_hash: str, password_salt: str):
    digest, _ = hash_password(password, bytes.fromhex(password_salt))
    return hmac.compare_digest(digest, password_hash)


def email_exists(email: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()

    return row is not None


def create_account(name: str, email: str, password: str):
    name = name.strip()
    email = email.strip().lower()

    if not name:
        return False, "Please enter your name."

    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    if email_exists(email):
        return False, "An account with this email already exists. Please sign in."

    password_hash, password_salt = hash_password(password)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO users
                (id, name, email, password_hash, password_salt, is_guest, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    name,
                    email,
                    password_hash,
                    password_salt,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."

    return True, "Account created. Please sign in with your new account."


def authenticate(email: str, password: str):
    email = email.strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT id, name, email, password_hash, password_salt
            FROM users
            WHERE email = ? AND is_guest = 0
            """,
            (email,),
        ).fetchone()

    if not row:
        return None

    if not verify_password(password, row[3], row[4]):
        return None

    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "is_guest": False,
    }


def create_guest():
    guest_id = f"guest-{uuid.uuid4()}"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO users
            (id, name, email, password_hash, password_salt, is_guest, created_at)
            VALUES (?, ?, ?, NULL, NULL, 1, ?)
            """,
            (
                guest_id,
                "Guest",
                f"{guest_id}@guest.local",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()

    return {
        "id": guest_id,
        "name": "Guest",
        "email": "",
        "is_guest": True,
    }


def save_chat(question: str, answer: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO chats (id, user_id, question, answer, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                st.session_state.user["id"],
                question,
                answer,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def load_history(limit: int = 40):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id, question, answer, created_at
            FROM chats
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (st.session_state.user["id"], limit),
        ).fetchall()

    return [
        {
            "id": row[0],
            "question": row[1],
            "answer": row[2],
            "created_at": row[3],
        }
        for row in rows
    ]


def load_chat(chat_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT id, question, answer, created_at
            FROM chats
            WHERE id = ? AND user_id = ?
            """,
            (chat_id, st.session_state.user["id"]),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "question": row[1],
        "answer": row[2],
        "created_at": row[3],
    }


def delete_chat(chat_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            DELETE FROM chats
            WHERE id = ? AND user_id = ?
            """,
            (chat_id, st.session_state.user["id"]),
        )
        conn.commit()


def delete_all_chats():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM chats WHERE user_id = ?",
            (st.session_state.user["id"],),
        )
        conn.commit()


init_database()


# ============================================================
# SESSION STATE
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user" not in st.session_state:
    st.session_state.user = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = None

if "show_delete_all" not in st.session_state:
    st.session_state.show_delete_all = False

if "scroll_to_top" not in st.session_state:
    st.session_state.scroll_to_top = False


# ============================================================
# AUTHENTICATION SCREEN
# ============================================================

def render_auth_screen():
    st.markdown(
        """
        <div class="auth-shell">
            <div class="auth-brand">
                <div class="auth-icon">🔬</div>
                <div class="auth-title">Welcome to datta.ai</div>
                <div class="auth-subtitle">
                    Evidence-focused AI research, built for deeper answers.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 2, 1])

    with center:
        tab_signup, tab_signin, tab_guest = st.tabs(
            ["Create account", "Sign in", "Continue as guest"]
        )

        with tab_signup:
            st.subheader("Create your account")
            st.caption(
                "Create an account to keep your research history available when you return."
            )

            with st.form("signup_form", clear_on_submit=False):
                name = st.text_input("Name", placeholder="Your name")
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="At least 8 characters",
                )
                confirm = st.text_input(
                    "Confirm password",
                    type="password",
                )

                submitted = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                    type="primary",
                )

                if submitted:
                    if password != confirm:
                        st.error("Passwords do not match.")
                    else:
                        success, message = create_account(
                            name,
                            email,
                            password,
                        )

                        if success:
                            st.success(message)
                        else:
                            st.error(message)

        with tab_signin:
            st.subheader("Sign in")
            st.caption("Use your account to access your saved research.")

            with st.form("signin_form"):
                email = st.text_input(
                    "Email",
                    placeholder="you@example.com",
                    key="signin_email",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    key="signin_password",
                )

                submitted = st.form_submit_button(
                    "Sign in",
                    use_container_width=True,
                    type="primary",
                )

                if submitted:
                    user = authenticate(email, password)

                    if user:
                        st.session_state.user = user
                        st.session_state.authenticated = True
                        st.session_state.messages = []
                        st.session_state.active_chat_id = None
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

        with tab_guest:
            st.subheader("Continue without an account")
            st.caption(
                "Explore datta.ai immediately without creating an account."
            )

            st.markdown(
                """
                <div class="guest-box">
                    <strong>Guest mode</strong><br>
                    <span style="color:#667085;font-size:0.86rem;">
                        You can research normally. Your guest history is tied
                        to this current app session and is not an account.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                "Continue as guest",
                use_container_width=True,
                type="primary",
            ):
                st.session_state.user = create_guest()
                st.session_state.authenticated = True
                st.session_state.messages = []
                st.session_state.active_chat_id = None
                st.rerun()

        st.markdown(
            '<div class="footer">datta.ai · Research deeper. Decide with evidence.</div>',
            unsafe_allow_html=True,
        )


if not st.session_state.authenticated:
    render_auth_screen()
    st.stop()


# ============================================================
# RESEARCH GRAPH
# ============================================================

@st.cache_resource
def load_research_graph():
    from src.graph import research_graph
    return research_graph


def reset_current_chat():
    st.session_state.messages = []
    st.session_state.active_chat_id = None


def load_saved_chat(chat_id: str):
    chat = load_chat(chat_id)
    if not chat:
        return

    st.session_state.messages = [
        {"role": "user", "content": chat["question"]},
        {"role": "assistant", "content": chat["answer"]},
    ]
    st.session_state.active_chat_id = chat_id


def clean_report_text(report: str) -> str:
    """Normalize common LLM spacing artifacts without changing the meaning."""
    text = report or ""

    # Number + unit + connector + number:
    # "5.1 billionin2024toover47 billion" -> "5.1 billion in 2024 to over 47 billion"
    text = re.sub(
        r"(\b\d+(?:\.\d+)?)\s*(billion|million|trillion|thousand)"
        r"\s*(in|to|from|by|over)\s*(\d)",
        r"\1 \2 \3 \4",
        text,
        flags=re.IGNORECASE,
    )

    # Common year/word concatenation:
    # "announcedin2026" -> "announced in 2026"
    text = re.sub(
        r"([A-Za-z])in(20\d{2})\b",
        r"\1 in \2",
        text,
    )

    # Percent spacing:
    # "40 %" -> "40%" and "40percent" -> "40 percent"
    text = re.sub(r"(\d+(?:\.\d+)?)\s+%", r"\1%", text)
    text = re.sub(
        r"(\d+(?:\.\d+)?)percent\b",
        r"\1 percent",
        text,
        flags=re.IGNORECASE,
    )

    # Clean repeated whitespace while preserving newlines.
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


def render_report(report: str):
    """Render a research report with controlled, professional typography."""
    cleaned = clean_report_text(report)

    with st.container(border=True):
        st.markdown(
            '<div class="report-meta">'
            '<span class="report-chip">Evidence-based report</span>'
            '<span class="report-chip">Citations included</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(cleaned)


def run_research(question: str):
    research_graph = load_research_graph()

    input_state = {
        "question": question,
        "sub_questions": [],
        "search_results": [],
        "sources": [],
        "verified_sources": [],
        "verified_evidence": [],
        "research_round": 0,
        "max_research_rounds": 1,
        "research_complete": False,
        "verification_failed": False,
        "answer": "",
        "llm_calls": 0,
    }

    final_state = {}
    total_sources = 0
    verified_claims = 0

    progress = st.status(
        "🔬 Researching your question...",
        expanded=True,
    )

    status_placeholder = st.empty()
    metrics_placeholder = st.empty()

    try:
        for event in research_graph.stream(
            input_state,
            stream_mode="updates",
        ):
            if not isinstance(event, dict):
                continue

            for node_name, node_state in event.items():
                if not isinstance(node_state, dict):
                    continue

                if node_state.get("sources"):
                    total_sources = len(node_state["sources"])

                if node_state.get("verified_sources"):
                    total_sources = max(
                        total_sources,
                        len(node_state["verified_sources"]),
                    )

                if node_state.get("verified_evidence") is not None:
                    verified_claims = len(node_state["verified_evidence"])

                final_state.update(node_state)

                messages = {
                    "plan_research": "🧠 Building the research plan...",
                    "search_web": "🌐 Searching multiple web sources...",
                    "verify_evidence": "🔎 Verifying evidence and citations...",
                    "deep_research": "🔬 Running targeted follow-up research...",
                    "generate_answer": "✍️ Writing the evidence-based report...",
                }

                status_placeholder.info(
                    messages.get(node_name, "⚙️ Processing research...")
                )

                cols = metrics_placeholder.columns(2)
                cols[0].metric("Sources", total_sources)
                cols[1].metric("Evidence items", verified_claims)

                if node_state.get("answer"):
                    final_state["answer"] = node_state["answer"]

        report = final_state.get("answer", "")

        if not report:
            progress.update(
                label="Research finished without a report",
                state="error",
            )
            raise RuntimeError(
                "The research graph completed without generating a report."
            )

        progress.update(
            label="Research completed successfully",
            state="complete",
        )

        status_placeholder.empty()
        metrics_placeholder.empty()

        return report

    except Exception as exc:
        progress.update(label="Research failed", state="error")
        logger.exception(
            "Research request failed | error_type=%s | message=%s",
            type(exc).__name__,
            str(exc),
        )
        if settings.debug:
            raise
        if isinstance(exc, DattaAIError):
            raise
        raise RuntimeError(
            "The research request could not be completed. "
            "Please try again. Technical details were written to the application log."
        ) from exc


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-icon">🔬</div>
            <div class="brand-name">datta.ai</div>
        </div>
        <div class="brand-tag">Evidence-focused AI research</div>
        """,
        unsafe_allow_html=True,
    )

    user = st.session_state.user

    st.markdown(
        f"""
        <div class="account-card">
            <div class="account-name">{user["name"]}</div>
            <div class="account-type">
                {"Guest mode" if user["is_guest"] else user["email"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("＋ New research", use_container_width=True):
        reset_current_chat()
        st.rerun()

    if st.button("Sign out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.messages = []
        st.session_state.active_chat_id = None
        st.rerun()

    st.divider()

    st.markdown(
        '<div class="history-title">Saved research</div>',
        unsafe_allow_html=True,
    )

    history = load_history()

    if not history:
        st.caption("Your completed research will appear here.")
    else:
        for item in history:
            title = item["question"].strip().replace("\n", " ")
            if len(title) > 48:
                title = title[:48].rstrip() + "…"

            row_left, row_right = st.columns([5, 1])

            with row_left:
                if st.button(
                    title,
                    key=f"history_open_{item['id']}",
                    use_container_width=True,
                ):
                    load_saved_chat(item["id"])
                    st.rerun()

            with row_right:
                if st.button(
                    "🗑️",
                    key=f"history_delete_{item['id']}",
                    help="Delete this research",
                ):
                    delete_chat(item["id"])

                    if st.session_state.active_chat_id == item["id"]:
                        reset_current_chat()

                    st.rerun()

    if history:
        st.divider()

        if not st.session_state.show_delete_all:
            if st.button(
                "Delete all saved research",
                use_container_width=True,
            ):
                st.session_state.show_delete_all = True
                st.rerun()
        else:
            st.warning("This will permanently delete your saved research.")

            confirm_col, cancel_col = st.columns(2)

            with confirm_col:
                if st.button(
                    "Delete all",
                    use_container_width=True,
                    type="primary",
                ):
                    delete_all_chats()
                    reset_current_chat()
                    st.session_state.show_delete_all = False
                    st.rerun()

            with cancel_col:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_delete_all = False
                    st.rerun()

    st.divider()

    with st.expander("How datta.ai works"):
        st.markdown(
            """
            **Research → Search → Verify → Deep Research → Report**

            - 🌐 Multi-source web search
            - 🔎 Evidence verification
            - 📊 Source credibility analysis
            - 🔬 Targeted follow-up research
            - 🔗 Citation tracking
            - 🛡️ Deterministic safeguards
            """
        )

    st.caption("Python · LangGraph · Groq · Streamlit")


# ============================================================
# MAIN HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">AI Research Workspace</div>
        <div class="hero-title">Research deeper.<br>Decide with evidence.</div>
        <div class="hero-copy">
            Ask a question and datta.ai searches the web, checks evidence,
            evaluates source credibility, performs targeted research, and
            produces a cited report.
        </div>
        <div class="feature-row">
            <span class="feature-pill">🌐 Multi-source search</span>
            <span class="feature-pill">🔎 Evidence verification</span>
            <span class="feature-pill">📊 Credibility scoring</span>
            <span class="feature-pill">🔗 Cited reports</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CHAT AREA
# ============================================================

st.markdown(
    '<div class="section-label">Research conversation</div>',
    unsafe_allow_html=True,
)

if st.session_state.messages:
    st.caption(
        "Ask follow-up questions naturally. Use **New research** for a separate topic."
    )
else:
    st.markdown(
        """
        <div class="empty-state">
            <div class="empty-icon">✦</div>
            <div class="empty-title">What would you like to research?</div>
            <div class="empty-copy">
                Explore technology, business, science, markets, products,
                or any topic where evidence and sources matter.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Scroll to the beginning of the newly generated report after a research run.
# Streamlit reruns can otherwise preserve the browser's previous scroll position.
if st.session_state.scroll_to_top:
    components.html(
        """
        <script>
        (() => {
            const scrollTop = () => {
                try {
                    const app = window.parent.document.querySelector(
                        '[data-testid="stAppViewContainer"]'
                    );
                    if (app) {
                        app.scrollTo({top: 0, left: 0, behavior: 'instant'});
                    }
                    window.parent.scrollTo({top: 0, left: 0, behavior: 'instant'});
                } catch (error) {
                    window.parent.scrollTo(0, 0);
                }
            };

            setTimeout(scrollTop, 50);
            setTimeout(scrollTop, 250);
            setTimeout(scrollTop, 600);
        })();
        </script>
        """,
        height=0,
    )
    st.session_state.scroll_to_top = False


for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(
            f"""
            <div class="question-card">
                <div class="question-label">You</div>
                <div class="question-text">{message["content"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="section-label">datta.ai</div>',
            unsafe_allow_html=True,
        )
        render_report(message["content"])


prompt = st.chat_input("Ask a research question…")

if prompt:
    prompt = prompt.strip()

    if prompt:
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )

        try:
            with st.spinner("Preparing your research..."):
                answer = run_research(prompt)

            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )

            save_chat(prompt, answer)
            st.session_state.scroll_to_top = True
            st.rerun()

        except Exception as exc:
            logger.error(
                "UI research request failed | error_type=%s | message=%s",
                type(exc).__name__,
                str(exc),
            )
            st.error(str(exc))
            if settings.debug:
                st.exception(exc)


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        datta.ai · Evidence-focused AI Research Agent
    </div>
    """,
    unsafe_allow_html=True,
)

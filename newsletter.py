#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Newsletter giornaliera — Rassegna Stampa Welfare & Wellbeing
Legge dal DB, genera HTML email-safe, invia via SMTP Aruba.

Variabili d'ambiente richieste (GitHub Secrets):
  SMTP_USER     — indirizzo email Aruba mittente
  SMTP_PASSWORD — password dell'account Aruba
  NEWSLETTER_TO — destinatari separati da virgola
"""

import os, re, sqlite3, smtplib, html as _html, logging, sys
from email.header import Header
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ─── Percorsi ────────────────────────────────────────────────────────────────

APP_DIR  = Path(__file__).parent
DB_PATH  = APP_DIR / "data" / "rassegna.db"
LOG_PATH = APP_DIR / "data" / "newsletter.log"

# ─── SMTP ────────────────────────────────────────────────────────────────────

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
RECIPIENTS    = [r.strip() for r in re.split(r'[,\r\n]+', os.environ.get("NEWSLETTER_TO", "").strip()) if r.strip()]

MAX_PER_CAT = 3  # articoli massimi per categoria

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ─── Struttura categorie (speculare a rassegna_stampa.py, solo icon e color) ─

CATEGORIES = {
    "Formazione & Sviluppo":   {"icon": "📚", "color": "#16a34a"},
    "Coaching & Mentoring":    {"icon": "🎯", "color": "#0d9488"},
    "Welfare Aziendale":       {"icon": "🏢", "color": "#4f46e5"},
    "Previdenza & Pensione":   {"icon": "🛡️", "color": "#64748b"},
    "Benefit & Fringe":        {"icon": "🎁", "color": "#db2777"},
    "Rimborsi & Convenzioni":  {"icon": "💳", "color": "#9333ea"},
    "Salute & Sicurezza":      {"icon": "🦺", "color": "#dc2626"},
    "Wellness & Sport":        {"icon": "🧘", "color": "#0891b2"},
    "Supporto Psicologico":    {"icon": "🧠", "color": "#8b5cf6"},
    "Wellbeing":               {"icon": "💚", "color": "#059669"},
    "Mobilità Sostenibile":    {"icon": "🚲", "color": "#0369a1"},
    "Green Benefits":          {"icon": "🌱", "color": "#166534"},
    "Smart Working":           {"icon": "💻", "color": "#7c3aed"},
    "Work-Life Balance":       {"icon": "⚖️", "color": "#d97706"},
    "Inclusione & Diversity":  {"icon": "🌈", "color": "#ea580c"},
    "Famiglia & Caregiving":   {"icon": "👨\u200d👩\u200d👧", "color": "#f59e0b"},
    "Servizi alla Persona":    {"icon": "🛎️", "color": "#6366f1"},
    "Assicurazione Auto":      {"icon": "🚗",  "color": "#dc2626"},
    "Noleggio Lungo Termine":  {"icon": "🚙",  "color": "#7c3aed"},
    "Conto Corrente Online":   {"icon": "🏦",  "color": "#0891b2"},
    "Prestiti Personali":      {"icon": "💸",  "color": "#d97706"},
    "Mutuo Prima Casa":        {"icon": "🏠",  "color": "#16a34a"},
    "Surroga Mutuo":           {"icon": "🔄",  "color": "#0369a1"},
    "Cessione del Quinto":     {"icon": "📋",  "color": "#9333ea"},
    "Conto Deposito":          {"icon": "💰",  "color": "#f59e0b"},
    "Fondo Pensione":          {"icon": "🛡️",  "color": "#475569"},
    "Assicurazione Sanitaria": {"icon": "🏥",  "color": "#059669"},
    "Consolidamento Debiti":   {"icon": "⚖️",  "color": "#ea580c"},
    "Mutuo Green":             {"icon": "🌱",  "color": "#166534"},
    "PAC ETF":                 {"icon": "📈",  "color": "#4f46e5"},
    "Bonifico Istantaneo":     {"icon": "⚡",  "color": "#db2777"},
}

# Sezioni della newsletter (ordine e raggruppamento identici alla rassegna stampa)
SECTIONS = [
    {"label": "Welfare Aziendale",           "icon": "🏢", "color": "#4f46e5",
     "items": ["Welfare Aziendale"]},
    {"label": "Smart Working",               "icon": "💻", "color": "#7c3aed",
     "items": ["Smart Working"]},
    {"label": "Crescita Personale",          "icon": "🌟", "color": "#16a34a",
     "items": ["Formazione & Sviluppo", "Coaching & Mentoring"]},
    {"label": "Benefit Aziendali",           "icon": "🎁", "color": "#db2777",
     "items": ["Previdenza & Pensione", "Benefit & Fringe", "Rimborsi & Convenzioni"]},
    {"label": "Benessere Fisico ed Emotivo", "icon": "💚", "color": "#059669",
     "items": ["Salute & Sicurezza", "Wellness & Sport", "Supporto Psicologico", "Wellbeing"]},
    {"label": "Eco & Mobilità",              "icon": "🌍", "color": "#0369a1",
     "items": ["Mobilità Sostenibile", "Green Benefits"]},
    {"label": "Supporto Quotidiano",         "icon": "🤝", "color": "#d97706",
     "items": ["Work-Life Balance", "Inclusione & Diversity", "Famiglia & Caregiving",
               "Servizi alla Persona"]},
    {"label": "Benessere Finanziario",       "icon": "💰", "color": "#1d4ed8",
     "items": [
         "Assicurazione Auto", "Noleggio Lungo Termine", "Conto Corrente Online",
         "Prestiti Personali", "Mutuo Prima Casa", "Surroga Mutuo",
         "Cessione del Quinto", "Conto Deposito", "Fondo Pensione",
         "Assicurazione Sanitaria", "Consolidamento Debiti", "Mutuo Green",
         "PAC ETF", "Bonifico Istantaneo",
     ]},
]

# ─── DB ──────────────────────────────────────────────────────────────────────

def load_articles_24h() -> dict[str, list[dict]]:
    """Articoli con pub_date >= ieri, raggruppati per categoria."""
    cutoff = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT title, abstract, url, source, category, pub_date
           FROM articles
           WHERE pub_date >= ?
           ORDER BY pub_date DESC, fetch_date DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(dict(r))
    return by_cat

# ─── HTML ────────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return _html.escape(s or "")

def _trunc(s: str, n: int = 200) -> str:
    s = (s or "").strip()
    return s[:n] + "…" if len(s) > n else s

def _fmt_date(pub_date: str) -> str:
    try:
        return datetime.strptime(pub_date, "%Y-%m-%d").strftime("%d %b %Y")
    except (ValueError, TypeError):
        return pub_date or ""


def build_newsletter_html(by_cat: dict[str, list[dict]], total: int, date_str: str) -> str:
    sections_html = ""

    for section in SECTIONS:
        # Raccoglie le categorie di questa sezione che hanno articoli
        section_cats: dict[str, list[dict]] = {}
        for cat in section["items"]:
            arts = by_cat.get(cat, [])[:MAX_PER_CAT]
            if arts:
                section_cats[cat] = arts
        if not section_cats:
            continue

        sc = section["color"]

        # Articoli della sezione
        articles_rows = ""
        for cat, arts in section_cats.items():
            info = CATEGORIES.get(cat, {"icon": "📰", "color": "#64748b"})
            cc   = info["color"]

            articles_rows += f"""
            <tr>
              <td style="background:{cc}15;border-left:4px solid {cc};
                         padding:10px 18px;">
                <span style="color:{cc};font-weight:bold;font-size:13px;">
                  {info['icon']}&nbsp;{_esc(cat)}
                </span>
              </td>
            </tr>"""

            for a in arts:
                title    = _esc(_html.unescape(a.get("title", "") or ""))
                abstract = _esc(_trunc(_html.unescape(a.get("abstract", "") or "")))
                source   = _esc(a.get("source", ""))
                url      = _esc(a.get("url", "#"))
                date_fmt = _fmt_date(a.get("pub_date", ""))
                meta     = "&nbsp;·&nbsp;".join(filter(None, [source, date_fmt]))

                articles_rows += f"""
            <tr>
              <td style="background:#ffffff;border-bottom:1px solid #f1f5f9;
                         padding:14px 20px;">
                <a href="{url}"
                   style="color:#1e293b;font-size:14px;font-weight:600;
                          text-decoration:none;line-height:1.4;display:block;
                          margin-bottom:6px;">{title}</a>
                {"<p style='color:#64748b;font-size:13px;margin:0 0 8px 0;line-height:1.5;'>" + abstract + "</p>" if abstract else ""}
                <span style="color:#94a3b8;font-size:11px;">{meta}</span>
              </td>
            </tr>"""

        sections_html += f"""
    <!-- {section['label']} -->
    <tr><td style="padding-top:12px;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-radius:8px;overflow:hidden;
                    border:1px solid {sc}40;">
        <tr>
          <td style="background:{sc};padding:13px 20px;">
            <span style="color:#ffffff;font-size:15px;font-weight:bold;">
              {section['icon']}&nbsp;&nbsp;{_esc(section['label'])}
            </span>
          </td>
        </tr>
        {articles_rows}
      </table>
    </td></tr>"""

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Rassegna Stampa — {date_str}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
             font-family:Arial,Helvetica,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0"
       style="background:#f1f5f9;">
<tr><td align="center" style="padding:24px 16px;">

<table width="600" cellpadding="0" cellspacing="0"
       style="max-width:600px;width:100%;">

  <!-- HEADER -->
  <tr><td style="border-radius:12px 12px 0 0;overflow:hidden;font-size:0;line-height:0;">
    <img src="https://ashitaka-76.github.io/rassegna-stampa/Header_WM_dem.gif"
         alt="WellMakers by BNP Paribas — Tutte le nostre forme del Benessere"
         width="600" style="display:block;width:100%;max-width:600px;border:0;">
  </td></tr>
  <tr><td style="background:#0d4f4f;padding:10px 24px 14px;text-align:center;">
    <span style="color:#a7d8d8;font-size:12px;">
      Rassegna Stampa &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; {total} articoli delle ultime 24 ore
    </span>
  </td></tr>

  <!-- SEZIONI -->
  {sections_html}

  <!-- FOOTER -->
  <tr><td style="background:#1e293b;border-radius:0 0 12px 12px;
                 padding:18px 24px;text-align:center;margin-top:12px;">
    <div style="color:#64748b;font-size:11px;">
      Newsletter generata automaticamente
      &nbsp;·&nbsp; Rassegna Stampa Welfare &amp; Wellbeing
    </div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

# ─── SMTP ────────────────────────────────────────────────────────────────────

def send(html_body: str, date_str: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"📰 Rassegna Stampa — {date_str}", "utf-8")
    msg["From"]    = SMTP_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.starttls()
        srv.login(SMTP_USER, SMTP_PASSWORD)
        srv.sendmail(SMTP_USER, RECIPIENTS, msg.as_bytes())

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=== Newsletter avviata ===")

    missing = [v for v in ("SMTP_USER", "SMTP_PASSWORD", "NEWSLETTER_TO")
               if not os.environ.get(v)]
    if missing:
        log.error("Variabili d'ambiente mancanti: %s", ", ".join(missing))
        sys.exit(1)

    if not DB_PATH.exists():
        log.error("DB non trovato: %s", DB_PATH)
        sys.exit(1)

    by_cat = load_articles_24h()
    total  = sum(len(v) for v in by_cat.values())

    if total == 0:
        log.warning("Nessun articolo nelle ultime 24h — newsletter non inviata.")
        sys.exit(0)

    date_str  = datetime.now().strftime("%d/%m/%Y")
    html_body = build_newsletter_html(by_cat, total, date_str)

    try:
        send(html_body, date_str)
        log.info("Inviata a %d destinatari — %d articoli", len(RECIPIENTS), total)
    except Exception as exc:
        log.error("Errore invio SMTP: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

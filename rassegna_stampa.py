#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         RASSEGNA STAMPA  ·  Welfare & Wellbeing          ║
║   Applicazione stand-alone per le imprese italiane       ║
╚══════════════════════════════════════════════════════════╝

Avvia lo script per aggiornare le notizie e aprire il report.
Non richiede alcun server web.
"""

import os, sys, sqlite3, webbrowser, hashlib, re, json, time
from datetime import datetime, timedelta
from pathlib import Path

# ─── Auto-install dipendenze ─────────────────────────────────────────────────
def _ensure(pip_name, import_name=None):
    """Installa il pacchetto pip se il modulo non è importabile."""
    mod = import_name or pip_name
    try:
        __import__(mod)
    except ImportError:
        import subprocess
        print(f"  → Installazione {pip_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Verifica dipendenze...")
_ensure("feedparser")
_ensure("requests")
_ensure("python-dateutil", "dateutil")
print("  ✓ Dipendenze OK\n")

import feedparser
import requests
from dateutil import parser as dateparser

# ─── Configurazione percorsi ─────────────────────────────────────────────────
APP_DIR  = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH   = DATA_DIR / "rassegna.db"
HTML_PATH = DATA_DIR / "rassegna.html"

# ─── Categorie e keyword ──────────────────────────────────────────────────────
CATEGORIES = {
    "Welfare Aziendale": {
        "icon": "🏢",
        "color": "#4f46e5",
        "keywords": [
            "welfare aziendale", "welfare in azienda", "piano welfare",
            "flexible benefit", "welfare state", "welfare 4.0",
            "portale welfare", "piattaforma welfare"
        ]
    },
    "Wellbeing": {
        "icon": "💚",
        "color": "#059669",
        "keywords": [
            "wellbeing", "well-being", "benessere organizzativo",
            "benessere dei lavoratori", "benessere aziendale",
            "employee wellbeing", "people care"
        ]
    },
    "Wellness": {
        "icon": "🧘",
        "color": "#0891b2",
        "keywords": [
            "wellness", "salute e benessere", "programmi wellness",
            "wellness aziendale", "health wellness", "mental health lavoro",
            "salute mentale lavoratori", "psicologia lavoro"
        ]
    },
    "Smart Working": {
        "icon": "💻",
        "color": "#7c3aed",
        "keywords": [
            "smart working", "lavoro agile", "lavoro da remoto",
            "telelavoro", "remote working", "hybrid work",
            "lavoro ibrido", "accordo smart working"
        ]
    },
    "Work-Life Balance": {
        "icon": "⚖️",
        "color": "#d97706",
        "keywords": [
            "work life balance", "work-life balance", "conciliazione lavoro",
            "equilibrio vita lavoro", "qualità vita lavorativa",
            "orario flessibile", "flessibilità oraria"
        ]
    },
    "Benefit & Fringe": {
        "icon": "🎁",
        "color": "#db2777",
        "keywords": [
            "fringe benefit", "benefit aziendali", "buoni pasto",
            "ticket restaurant", "rimborso spese", "auto aziendale",
            "polizza sanitaria dipendenti", "assicurazione sanitaria integrativa"
        ]
    },
    "Previdenza": {
        "icon": "🛡️",
        "color": "#64748b",
        "keywords": [
            "previdenza complementare", "fondo pensione", "pensione integrativa",
            "secondo pilastro", "tfr previdenza", "fondi pensione chiusi"
        ]
    },
    "Salute & Sicurezza": {
        "icon": "🦺",
        "color": "#dc2626",
        "keywords": [
            "salute sicurezza lavoro", "medicina del lavoro", "infortuni lavoro",
            "malattia professionale", "rischi professionali", "dlgs 81",
            "stress lavoro correlato", "burn-out"
        ]
    },
    "Inclusione & Diversity": {
        "icon": "🌈",
        "color": "#ea580c",
        "keywords": [
            "diversity inclusion", "inclusione lavorativa", "pari opportunità",
            "gender gap azienda", "disabilità lavoro", "diversità aziendale",
            "gender pay gap", "donne lavoro parità"
        ]
    },
    "Formazione": {
        "icon": "📚",
        "color": "#16a34a",
        "keywords": [
            "formazione dipendenti", "upskilling", "reskilling",
            "sviluppo professionale", "lifelong learning", "academy aziendale",
            "coaching aziendale", "corporate learning"
        ]
    },
}

# ─── Fonti RSS ────────────────────────────────────────────────────────────────
RSS_SOURCES = [
    # Google News – una query per categoria (no API key)
    ("Google News · Welfare Aziendale",
     "https://news.google.com/rss/search?q=welfare+aziendale&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Wellbeing Lavoro",
     "https://news.google.com/rss/search?q=wellbeing+benessere+lavoratori&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Wellness Dipendenti",
     "https://news.google.com/rss/search?q=wellness+aziendale+dipendenti&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Smart Working",
     "https://news.google.com/rss/search?q=smart+working+italia+2025&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Work-Life Balance",
     "https://news.google.com/rss/search?q=%22work+life+balance%22+lavoro+italia&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Fringe Benefit",
     "https://news.google.com/rss/search?q=fringe+benefit+dipendenti+2025&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Previdenza Complementare",
     "https://news.google.com/rss/search?q=previdenza+complementare+fondo+pensione&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Salute Sicurezza Lavoro",
     "https://news.google.com/rss/search?q=salute+sicurezza+lavoro+infortuni&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Diversity Inclusion",
     "https://news.google.com/rss/search?q=diversity+inclusion+azienda+italia&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Formazione Aziendale",
     "https://news.google.com/rss/search?q=formazione+dipendenti+aziendale+upskilling&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Benessere Imprese",
     "https://news.google.com/rss/search?q=benessere+imprese+dipendenti+italia&hl=it&gl=IT&ceid=IT:it"),
    # Fonti specializzate & generaliste italiane
    ("Il Sole 24 Ore",
     "https://www.ilsole24ore.com/rss/economia.xml"),
    ("Google News · Burnout Stress Lavoro",
     "https://news.google.com/rss/search?q=burnout+stress+lavoro+azienda&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Orario Flessibile",
     "https://news.google.com/rss/search?q=orario+flessibile+conciliazione+famiglia&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · Polizza Sanitaria Integrativa",
     "https://news.google.com/rss/search?q=polizza+sanitaria+integrativa+dipendenti&hl=it&gl=IT&ceid=IT:it"),
    ("Google News · ESG Imprese",
     "https://news.google.com/rss/search?q=ESG+sostenibilità+imprese+lavoratori+italia&hl=it&gl=IT&ceid=IT:it"),
]

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            abstract    TEXT,
            url         TEXT NOT NULL,
            source      TEXT,
            category    TEXT,
            pub_date    TEXT,
            fetch_date  TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON articles(pub_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cat  ON articles(category)")
    conn.commit()
    conn.close()

def article_id(url: str, title: str) -> str:
    return hashlib.md5(f"{url}{title}".encode()).hexdigest()

def save_articles(articles: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for a in articles:
        aid = article_id(a["url"], a["title"])
        try:
            conn.execute("""
                INSERT INTO articles (id, title, abstract, url, source, category, pub_date, fetch_date)
                VALUES (?,?,?,?,?,?,?,?)
            """, (aid, a["title"], a["abstract"], a["url"],
                  a["source"], a["category"], a["pub_date"], a["fetch_date"]))
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # già presente
    conn.commit()
    conn.close()
    return inserted

def load_articles(days_back: int = 90) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM articles
        WHERE pub_date >= ?
        ORDER BY pub_date DESC, fetch_date DESC
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def cleanup_old(days: int = 92):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM articles WHERE pub_date < ?", (cutoff,))
    conn.commit()
    conn.close()

# ─── FETCH & PARSING RSS ─────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

def clean_html(text: str) -> str:
    """Rimuove tag HTML e normalizza spazi."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def truncate(text: str, n: int = 280) -> str:
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0] + "…"

def parse_date(entry) -> str:
    for attr in ("published", "updated", "created"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return dateparser.parse(val).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m-%d")

def categorize(title: str, abstract: str) -> str | None:
    text = (title + " " + abstract).lower()
    for cat, info in CATEGORIES.items():
        for kw in info["keywords"]:
            if kw in text:
                return cat
    return None

def fetch_feed(source_name: str, url: str) -> list[dict]:
    articles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            title    = clean_html(entry.get("title", "")).strip()
            abstract = clean_html(
                entry.get("summary", "") or entry.get("description", "")
            )
            abstract = truncate(abstract, 350)
            link     = entry.get("link", "")
            if not title or not link:
                continue
            cat = categorize(title, abstract)
            if cat is None:
                continue
            articles.append({
                "title":      title,
                "abstract":   abstract,
                "url":        link,
                "source":     source_name,
                "category":   cat,
                "pub_date":   parse_date(entry),
                "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
    except Exception as e:
        print(f"  ⚠ Errore su {source_name}: {e}")
    return articles

def refresh_news():
    print(f"Aggiornamento notizie — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    total = 0
    for i, (name, url) in enumerate(RSS_SOURCES, 1):
        print(f"  [{i:2d}/{len(RSS_SOURCES)}] {name}...", end=" ", flush=True)
        arts = fetch_feed(name, url)
        saved = save_articles(arts)
        print(f"✓  {saved} nuovi")
        total += saved
        time.sleep(0.4)   # gentile verso i server
    cleanup_old()
    print(f"\n  ✓ Totale nuovi articoli: {total}\n")

# ─── GENERATORE HTML ──────────────────────────────────────────────────────────
def build_html(articles: list[dict]) -> str:
    # Raggruppa per data e categoria
    by_date: dict[str, dict[str, list]] = {}
    for a in articles:
        d = a["pub_date"]
        c = a["category"]
        by_date.setdefault(d, {}).setdefault(c, []).append(a)

    dates_sorted = sorted(by_date.keys(), reverse=True)

    # Conta totali per categoria
    cat_counts: dict[str, int] = {}
    for a in articles:
        cat_counts[a["category"]] = cat_counts.get(a["category"], 0) + 1

    # Costruisce timeline JSON per JS
    timeline_data = json.dumps(
        {d: {c: len(v) for c, v in cats.items()} for d, cats in by_date.items()},
        ensure_ascii=False
    )

    # Articoli JSON (per filtri live JS)
    arts_json = json.dumps(articles[:2000], ensure_ascii=False)   # max 2000

    # Badge colori
    def cat_style(cat):
        color = CATEGORIES.get(cat, {}).get("color", "#64748b")
        return f'style="background:{color}20;color:{color};border:1px solid {color}40"'

    def cat_icon(cat):
        return CATEGORIES.get(cat, {}).get("icon", "📰")

    # Sidebar items (badge inizialmente mostra totale; JS aggiornerà a non-letti)
    def cat_slug(s):
        return re.sub(r'[^a-z0-9]', '-', s.lower()).strip('-')

    sidebar_items = '\n'.join(
        f'<li class="nav-item" data-cat="{cat}" onclick="filterCat(this)">'
        f'  <span class="nav-icon">{info["icon"]}</span>'
        f'  <span class="nav-label">{cat}</span>'
        f'  <span class="nav-badge" id="badge-{cat_slug(cat)}" style="background:{info["color"]}">'
        f'    {cat_counts.get(cat, 0)}</span>'
        f'  <button class="cat-mark-btn"'
        f'          title="Segna tutto letto: {cat}"'
        f'          onclick="event.stopPropagation();markAllRead(&quot;{cat}&quot;,null)">'
        f'    ✓</button>'
        f'</li>'
        for cat, info in CATEGORIES.items()
    )

    # Genera cards
    def render_article(a):
        safe_title    = a["title"].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        safe_abstract = a["abstract"].replace('<', '&lt;').replace('>', '&gt;')
        safe_source   = a["source"].replace('<', '&lt;')
        cat   = a["category"]
        color = CATEGORIES.get(cat, {}).get("color", "#64748b")
        icon  = cat_icon(cat)
        domain = re.sub(r"https?://(www\.)?", "", a["url"]).split("/")[0]
        d_fmt = datetime.strptime(a["pub_date"], "%Y-%m-%d").strftime("%d %b %Y") \
                if a["pub_date"] else ""
        return f'''
<article class="card" data-cat="{cat}" data-date="{a["pub_date"]}">
  <div class="card-header">
    <span class="cat-badge" {cat_style(cat)}>{icon} {cat}</span>
    <span class="card-date">{d_fmt}</span>
  </div>
  <h3 class="card-title">
    <a href="{a["url"]}" target="_blank" rel="noopener">{safe_title}</a>
  </h3>
  <p class="card-abstract">{safe_abstract}</p>
  <div class="card-footer">
    <span class="source-chip">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      {safe_source}
    </span>
    <a href="{a["url"]}" target="_blank" rel="noopener" class="read-more">
      Leggi articolo →
    </a>
  </div>
</article>'''

    all_cards = "\n".join(render_article(a) for a in articles[:2000])

    # Stats header
    today_count = sum(1 for a in articles if a["pub_date"] == datetime.now().strftime("%Y-%m-%d"))
    week_cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    week_count  = sum(1 for a in articles if a["pub_date"] >= week_cutoff)
    total_count = len(articles)

    now_str = datetime.now().strftime("%d %B %Y, %H:%M")

    # ──────────────────────────────────────────────────────────────────────────
    return f'''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Rassegna Stampa · Welfare & Wellbeing</title>
<style>
/* ── RESET & BASE ─────────────────────────────────────────────────────────── */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:         #0f172a;
  --surface:    #1e293b;
  --surface2:   #263144;
  --border:     #334155;
  --text:       #e2e8f0;
  --text-muted: #94a3b8;
  --accent:     #6366f1;
  --accent2:    #818cf8;
  --radius:     12px;
  --shadow:     0 4px 24px rgba(0,0,0,.35);
  --sidebar-w:  260px;
}}
html{{scroll-behavior:smooth}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh;
  display:flex;flex-direction:column;
}}

/* ── TOPBAR ──────────────────────────────────────────────────────────────── */
.topbar{{
  position:fixed;top:0;left:0;right:0;z-index:200;
  height:60px;background:var(--surface);
  border-bottom:1px solid var(--border);
  display:flex;align-items:center;padding:0 1.5rem;gap:1rem;
  backdrop-filter:blur(10px);
}}
.logo{{
  font-size:1.15rem;font-weight:700;
  background:linear-gradient(135deg,#6366f1,#a78bfa);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  white-space:nowrap;
}}
.logo small{{font-size:.7rem;font-weight:400;color:var(--text-muted);display:block;
  -webkit-text-fill-color:var(--text-muted);}}
.topbar-spacer{{flex:1}}
.update-info{{font-size:.78rem;color:var(--text-muted);text-align:right;line-height:1.4}}
.stats-chips{{display:flex;gap:.5rem;align-items:center}}
.chip{{
  padding:.25rem .75rem;border-radius:20px;font-size:.75rem;font-weight:600;
  background:var(--surface2);border:1px solid var(--border);
}}
.chip.today{{color:#34d399;border-color:#34d39940}}
.chip.week{{color:#60a5fa;border-color:#60a5fa40}}
.chip.total{{color:#a78bfa;border-color:#a78bfa40}}

/* ── LAYOUT ──────────────────────────────────────────────────────────────── */
.layout{{
  display:flex;min-height:100vh;padding-top:60px;
}}

/* ── SIDEBAR ─────────────────────────────────────────────────────────────── */
.sidebar{{
  position:fixed;left:0;top:60px;bottom:0;
  width:var(--sidebar-w);
  background:var(--surface);border-right:1px solid var(--border);
  overflow-y:auto;padding:1.25rem .75rem;
  display:flex;flex-direction:column;gap:.25rem;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent;
}}
.sidebar-title{{
  font-size:.68rem;font-weight:700;letter-spacing:.1em;
  text-transform:uppercase;color:var(--text-muted);
  padding:.5rem .75rem 1rem;
}}
.nav-item{{
  display:flex;align-items:center;gap:.6rem;
  padding:.6rem .85rem;border-radius:8px;cursor:pointer;
  transition:background .15s,transform .1s;
  font-size:.88rem;border:1px solid transparent;
}}
.nav-item:hover{{background:var(--surface2);border-color:var(--border)}}
.nav-item.active{{
  background:linear-gradient(135deg,#4f46e520,#7c3aed20);
  border-color:#6366f140;color:var(--accent2);
}}
.nav-icon{{font-size:1rem;width:22px;text-align:center}}
.nav-label{{flex:1;font-weight:500}}
.nav-badge{{
  font-size:.68rem;font-weight:700;padding:.15rem .5rem;
  border-radius:20px;color:#fff;min-width:22px;text-align:center;
}}
.nav-all{{
  display:flex;align-items:center;gap:.6rem;
  padding:.6rem .85rem;border-radius:8px;cursor:pointer;
  background:linear-gradient(135deg,#4f46e520,#7c3aed20);
  border:1px solid #6366f140;color:var(--accent2);
  font-size:.88rem;font-weight:700;margin-bottom:.5rem;
}}
.nav-all:hover{{filter:brightness(1.15)}}
.sidebar-section{{
  padding:.75rem .75rem .25rem;font-size:.68rem;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;color:var(--text-muted);
  margin-top:.75rem;
}}

/* Calendario storico */
.date-picker-wrap{{padding:.5rem .75rem 0}}
.date-picker-wrap label{{
  font-size:.72rem;color:var(--text-muted);font-weight:600;
  letter-spacing:.05em;text-transform:uppercase;display:block;margin-bottom:.4rem;
}}
#date-range{{
  width:100%;padding:.45rem .6rem;border-radius:6px;
  background:var(--surface2);border:1px solid var(--border);
  color:var(--text);font-size:.82rem;cursor:pointer;
}}
#date-range option{{background:var(--surface2)}}

/* ── MAIN CONTENT ─────────────────────────────────────────────────────────── */
.main{{
  margin-left:var(--sidebar-w);flex:1;padding:1.75rem 2rem;
  max-width:1200px;
}}

/* Search bar */
.search-wrap{{position:relative;margin-bottom:1.5rem}}
.search-icon{{
  position:absolute;left:.9rem;top:50%;transform:translateY(-50%);
  color:var(--text-muted);pointer-events:none;
}}
#search{{
  width:100%;padding:.7rem 1rem .7rem 2.5rem;
  border-radius:var(--radius);background:var(--surface);
  border:1px solid var(--border);color:var(--text);font-size:.92rem;
  transition:border-color .2s,box-shadow .2s;
}}
#search:focus{{
  outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px #6366f120;
}}
#search::placeholder{{color:var(--text-muted)}}

/* Section header */
.section-header{{
  display:flex;align-items:center;gap:.75rem;margin-bottom:1.25rem;
}}
.section-icon{{font-size:1.5rem}}
.section-title{{font-size:1.2rem;font-weight:700}}
.section-count{{
  font-size:.78rem;color:var(--text-muted);
  background:var(--surface);padding:.2rem .6rem;
  border-radius:20px;border:1px solid var(--border);
}}

/* Cards grid */
.cards-grid{{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
  gap:1rem;margin-bottom:2.5rem;
}}

/* Card */
.card{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:var(--radius);padding:1.1rem 1.2rem;
  display:flex;flex-direction:column;gap:.65rem;
  transition:transform .2s,box-shadow .2s,border-color .2s;
}}
.card:hover{{
  transform:translateY(-2px);box-shadow:var(--shadow);
  border-color:#6366f150;
}}
.card-header{{display:flex;align-items:center;justify-content:space-between;gap:.5rem}}
.cat-badge{{
  font-size:.7rem;font-weight:700;padding:.22rem .65rem;
  border-radius:20px;white-space:nowrap;letter-spacing:.02em;
}}
.card-date{{font-size:.74rem;color:var(--text-muted);white-space:nowrap}}
.card-title{{font-size:.97rem;font-weight:600;line-height:1.4}}
.card-title a{{
  color:var(--text);text-decoration:none;transition:color .15s;
}}
.card-title a:hover{{color:var(--accent2)}}
.card-abstract{{
  font-size:.83rem;color:var(--text-muted);line-height:1.6;flex:1;
}}
.card-footer{{
  display:flex;align-items:center;justify-content:space-between;
  margin-top:.25rem;
}}
.source-chip{{
  display:flex;align-items:center;gap:.35rem;
  font-size:.73rem;color:var(--text-muted);
}}
.read-more{{
  font-size:.78rem;font-weight:600;color:var(--accent2);
  text-decoration:none;transition:color .15s;
}}
.read-more:hover{{color:#c4b5fd}}

/* Gruppi per data */
.date-group{{margin-bottom:2rem}}
.date-label{{
  font-size:.8rem;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:var(--text-muted);
  padding:.3rem 0 .8rem;
  border-bottom:1px solid var(--border);margin-bottom:1rem;
  display:flex;align-items:center;gap:.5rem;
}}
.date-today-badge{{
  background:#34d39920;color:#34d399;border:1px solid #34d39940;
  border-radius:20px;font-size:.65rem;padding:.1rem .45rem;
}}
.date-label-spacer{{flex:1}}

/* ── LETTO / NON LETTO ───────────────────────────────────────────────────── */
.card.read{{
  opacity:.42;
  transition:opacity .3s,filter .3s;
}}
.card.read:hover{{opacity:.85}}
.unread-dot{{
  width:8px;height:8px;border-radius:50%;flex-shrink:0;
  cursor:pointer;transition:transform .15s,opacity .2s;
  display:inline-block;
}}
.unread-dot:hover{{transform:scale(1.5)}}

/* Mark-read buttons (inline, tiny) */
.mark-read-btn{{
  background:none;border:1px solid var(--border);
  color:var(--text-muted);font-size:.7rem;font-weight:600;
  padding:.2rem .6rem;border-radius:20px;cursor:pointer;
  transition:background .15s,color .15s,border-color .15s;
  white-space:nowrap;line-height:1.4;
}}
.mark-read-btn:hover{{
  background:#34d39918;color:#34d399;border-color:#34d39945;
}}

/* Per-category ✓ button in sidebar (shows on hover) */
.cat-mark-btn{{
  background:none;border:none;color:transparent;font-size:.82rem;
  cursor:pointer;padding:.1rem .25rem;border-radius:4px;
  transition:color .15s,background .15s;line-height:1;flex-shrink:0;
}}
.nav-item:hover .cat-mark-btn,
.nav-item.active .cat-mark-btn{{
  color:var(--text-muted);
}}
.cat-mark-btn:hover{{
  color:#34d399 !important;background:#34d39918;
}}

/* Topbar action buttons */
.topbar-btn{{
  background:none;border:1px solid var(--border);
  color:var(--text-muted);font-size:.78rem;font-weight:600;
  padding:.35rem .85rem;border-radius:20px;cursor:pointer;
  transition:all .15s;white-space:nowrap;
}}
.topbar-btn:hover{{background:var(--surface2)}}
.topbar-btn.green{{color:#34d399;border-color:#34d39940}}
.topbar-btn.green:hover{{background:#34d39915}}
.topbar-btn.active{{
  background:#6366f120;color:var(--accent2);border-color:#6366f150;
}}

/* "Solo non letti" in search row */
.search-row{{display:flex;gap:.75rem;align-items:center;margin-bottom:1.5rem}}
.search-row .search-wrap{{flex:1;margin-bottom:0}}

/* Toast */
#rs-toast{{
  position:fixed;bottom:1.75rem;left:50%;transform:translateX(-50%);
  background:var(--surface2);border:1px solid var(--border);
  color:var(--text);padding:.55rem 1.25rem;border-radius:10px;
  font-size:.82rem;z-index:999;opacity:0;
  transition:opacity .25s;pointer-events:none;white-space:nowrap;
  box-shadow:var(--shadow);
}}

/* Empty state */
.empty{{
  text-align:center;padding:4rem 2rem;color:var(--text-muted);
}}
.empty-icon{{font-size:3rem;margin-bottom:1rem}}
.empty h3{{font-size:1.1rem;font-weight:600;margin-bottom:.5rem}}

/* Scrollbar */
::-webkit-scrollbar{{width:6px}}
::-webkit-scrollbar-track{{background:transparent}}
::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px}}

/* Responsive */
@media(max-width:768px){{
  .sidebar{{display:none}}
  .main{{margin-left:0;padding:1rem}}
  .cards-grid{{grid-template-columns:1fr}}
  .stats-chips{{display:none}}
}}

/* Animazioni */
@keyframes fadeIn{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
.card{{animation:fadeIn .25s ease both}}
</style>
</head>
<body>

<!-- TOPBAR -->
<header class="topbar">
  <div class="logo">
    📰 Rassegna Stampa
    <small>Welfare · Wellbeing · Wellness</small>
  </div>
  <div class="topbar-spacer"></div>
  <div class="stats-chips">
    <span class="chip today">Oggi: {today_count}</span>
    <span class="chip week">7gg: {week_count}</span>
    <span class="chip total">Totale: {total_count}</span>
  </div>
  <button class="topbar-btn" id="only-unread-btn" onclick="toggleOnlyUnread()"
          title="Mostra solo le notizie non ancora lette">
    👁 Solo non letti
  </button>
  <button class="topbar-btn green" onclick="markVisibleRead()"
          id="mark-all-btn" title="Segna come lette tutte le notizie visibili">
    ✓ Segna tutto letto
  </button>
  <div class="update-info">
    Aggiornato<br>{now_str}
  </div>
</header>

<!-- LAYOUT -->
<div class="layout">

  <!-- SIDEBAR -->
  <nav class="sidebar">
    <div class="sidebar-title">Categorie</div>

    <div class="nav-all">
      <span class="nav-icon" onclick="filterCat(null)" style="cursor:pointer">🗞️</span>
      <span class="nav-label" onclick="filterCat(null)" style="cursor:pointer">Tutte le notizie</span>
      <span class="nav-badge" id="badge-all" style="background:#6366f1">{total_count}</span>
      <button class="cat-mark-btn" title="Segna tutto letto"
              onclick="markAllRead(null,null)" style="color:var(--text-muted)">✓</button>
    </div>

    <ul style="list-style:none;display:flex;flex-direction:column;gap:.2rem">
      {sidebar_items}
    </ul>

    <div class="sidebar-section">Storico</div>
    <div class="date-picker-wrap">
      <label for="date-range">Periodo</label>
      <select id="date-range" onchange="filterDate(this.value)">
        <option value="7">Ultimi 7 giorni</option>
        <option value="30">Ultimo mese</option>
        <option value="60">Ultimi 2 mesi</option>
        <option value="90" selected>Ultimi 3 mesi</option>
      </select>
    </div>
  </nav>

  <!-- MAIN -->
  <main class="main" id="main-content">

    <!-- Search row -->
    <div class="search-row">
      <div class="search-wrap">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input type="text" id="search" placeholder="Cerca notizie, fonti, keyword…"
               oninput="filterSearch(this.value)">
      </div>
    </div>

    <div id="articles-container">
      {all_cards}
    </div>

    <div class="empty" id="empty-state" style="display:none">
      <div class="empty-icon">🔍</div>
      <h3>Nessuna notizia trovata</h3>
      <p>Prova a modificare il filtro o aggiorna la rassegna.</p>
    </div>

  </main>
</div>

<script>
// ── DATI EMBEDDED ────────────────────────────────────────────────────────────
const ARTICLES = {arts_json};
const CATEGORIES_LIST = {json.dumps(list(CATEGORIES.keys()))};

// ── STATO ────────────────────────────────────────────────────────────────────
let activeCat   = null;
let activeDays  = 90;
let searchQuery = "";
let onlyUnread  = false;

// ── READ STATE (localStorage) ────────────────────────────────────────────────
const READ_KEY = 'rassegna_read_v1';

function getReadIds() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); }}
  catch {{ return new Set(); }}
}}
function saveReadIds(ids) {{
  try {{
    // Limita a 8000 ID per non saturare localStorage
    const arr = [...ids].slice(-8000);
    localStorage.setItem(READ_KEY, JSON.stringify(arr));
  }} catch(e) {{ console.warn('localStorage pieno:', e); }}
}}

// Segna un singolo articolo come letto (chiamato al click su "Leggi articolo")
function markOneRead(id) {{
  if (!id) return;
  const ids = getReadIds();
  if (ids.has(id)) return;
  ids.add(id);
  saveReadIds(ids);
  refreshBadges();
  const card = document.querySelector(`.card[data-id="${{id}}"]`);
  if (card) {{
    card.classList.add('read');
    const dot = card.querySelector('.unread-dot');
    if (dot) applyDotRead(dot, true);
  }}
}}

// Toggle letto/non-letto sul pallino
function toggleRead(evt, dotEl, id) {{
  evt.stopPropagation();
  if (!id) return;
  const ids = getReadIds();
  const card = dotEl.closest('.card');
  const nowRead = ids.has(id);
  if (nowRead) {{ ids.delete(id); }} else {{ ids.add(id); }}
  saveReadIds(ids);
  card.classList.toggle('read', !nowRead);
  applyDotRead(dotEl, !nowRead);
  refreshBadges();
  if (onlyUnread && !nowRead) {{
    // Articolo appena segnato letto: rimuovilo dalla vista
    setTimeout(() => {{ card.style.opacity='0'; card.style.height='0'; card.style.overflow='hidden';
      setTimeout(() => card.remove(), 300); }}, 50);
  }}
}}

function applyDotRead(dot, isRead) {{
  if (isRead) {{
    dot.style.background = 'transparent';
    dot.style.border = '1.5px solid #475569';
    dot.title = 'Letto — clicca per segnare come non letto';
  }} else {{
    const c = dot.dataset.color || 'var(--accent2)';
    dot.style.background = c;
    dot.style.border = 'none';
    dot.title = 'Non letto — clicca per segnare come letto';
  }}
}}

// ── MARK ALL ──────────────────────────────────────────────────────────────────
// cat: filtra per categoria (null = tutte)
// date: filtra per data  (null = tutte nel periodo)
function markAllRead(cat, date) {{
  const ids = getReadIds();
  const cutoff = getCutoff(activeDays);
  let count = 0;
  ARTICLES.forEach(a => {{
    if (!a.id) return;
    if (a.pub_date < cutoff) return;
    if (cat  && a.category !== cat)  return;
    if (date && a.pub_date  !== date) return;
    if (!ids.has(a.id)) {{ ids.add(a.id); count++; }}
  }});
  saveReadIds(ids);
  refreshBadges();
  // Aggiorna le card nel DOM senza re-render completo
  const selector = date  ? `.card[data-date="${{date}}"]`
                  : cat   ? `.card[data-cat="${{cat}}"]`
                          : '.card';
  document.querySelectorAll(selector).forEach(card => {{
    card.classList.add('read');
    const dot = card.querySelector('.unread-dot');
    if (dot) applyDotRead(dot, true);
  }});
  if (onlyUnread) render(); // se il filtro è attivo, rifai render
  const label = date  ? `del ${{date}}`
               : cat   ? `"${{cat}}"`
                       : 'visibili';
  showToast(`✓ ${{count}} articol${{count===1?'o':'i'}} ${{label}} segnati come letti`);
}}

// Segna ciò che è attualmente visibile (rispetta filtro categoria)
function markVisibleRead() {{
  markAllRead(activeCat, null);
  // Aggiorna testo pulsante topbar brevemente
  const btn = document.getElementById('mark-all-btn');
  if (btn) {{
    const prev = btn.textContent;
    btn.textContent = '✓ Fatto!';
    setTimeout(() => btn.textContent = prev, 1800);
  }}
}}

// ── TOGGLE "SOLO NON LETTI" ──────────────────────────────────────────────────
function toggleOnlyUnread() {{
  onlyUnread = !onlyUnread;
  const btn = document.getElementById('only-unread-btn');
  if (btn) {{
    btn.classList.toggle('active', onlyUnread);
    btn.textContent = onlyUnread ? '👁 Tutti' : '👁 Solo non letti';
  }}
  render();
}}

// ── REFRESH BADGE SIDEBAR (mostra non-letti) ─────────────────────────────────
function refreshBadges() {{
  const cutoff = getCutoff(activeDays);
  const readIds = getReadIds();
  const unread = {{}};
  let totalUnread = 0;
  ARTICLES.forEach(a => {{
    if (a.pub_date < cutoff) return;
    if (!readIds.has(a.id)) {{
      unread[a.category] = (unread[a.category] || 0) + 1;
      totalUnread++;
    }}
  }});
  // Aggiorna badge per categoria
  document.querySelectorAll('.nav-item[data-cat]').forEach(item => {{
    const cat = item.dataset.cat;
    const badge = item.querySelector('.nav-badge');
    if (!badge) return;
    const n = unread[cat] || 0;
    badge.textContent = n;
    badge.style.opacity = n > 0 ? '1' : '0.3';
  }});
  const badgeAll = document.getElementById('badge-all');
  if (badgeAll) {{
    badgeAll.textContent = totalUnread;
    badgeAll.style.opacity = totalUnread > 0 ? '1' : '0.3';
  }}
}}

// ── TOAST ────────────────────────────────────────────────────────────────────
function showToast(msg) {{
  let t = document.getElementById('rs-toast');
  if (!t) {{
    t = document.createElement('div'); t.id = 'rs-toast';
    document.body.appendChild(t);
  }}
  t.textContent = msg;
  t.style.opacity = '1';
  clearTimeout(t._tid);
  t._tid = setTimeout(() => t.style.opacity = '0', 2600);
}}

// ── UTILITY ──────────────────────────────────────────────────────────────────
function getCutoff(days) {{
  const d = new Date(); d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}}

function formatDate(d) {{
  const parts = d.split("-");
  const dt = new Date(+parts[0], +parts[1]-1, +parts[2]);
  const today = new Date(); today.setHours(0,0,0,0);
  const months = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
  const label = `${{dt.getDate()}} ${{months[dt.getMonth()]}} ${{dt.getFullYear()}}`;
  return dt.getTime() === today.getTime()
    ? `${{label}} <span class="date-today-badge">OGGI</span>` : label;
}}

function esc(s) {{
  return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")
                .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}}

// ── RENDER ───────────────────────────────────────────────────────────────────
const CAT_INFO = {{
  "Welfare Aziendale":      {{icon:"🏢", color:"#4f46e5"}},
  "Wellbeing":              {{icon:"💚", color:"#059669"}},
  "Wellness":               {{icon:"🧘", color:"#0891b2"}},
  "Smart Working":          {{icon:"💻", color:"#7c3aed"}},
  "Work-Life Balance":      {{icon:"⚖️", color:"#d97706"}},
  "Benefit & Fringe":       {{icon:"🎁", color:"#db2777"}},
  "Previdenza":             {{icon:"🛡️", color:"#64748b"}},
  "Salute & Sicurezza":     {{icon:"🦺", color:"#dc2626"}},
  "Inclusione & Diversity": {{icon:"🌈", color:"#ea580c"}},
  "Formazione":             {{icon:"📚", color:"#16a34a"}},
}};

function cardHtml(a, readIds) {{
  const ci = CAT_INFO[a.category] || {{icon:"📰", color:"#64748b"}};
  const dParts = a.pub_date.split("-");
  const months = ["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
  const dFmt = `${{+dParts[2]}} ${{months[+dParts[1]-1]}} ${{dParts[0]}}`;
  const c = ci.color;
  const isRead = readIds.has(a.id);
  const readCls = isRead ? ' read' : '';
  const dotBg   = isRead ? 'background:transparent;border:1.5px solid #475569' : `background:${{c}}`;
  const dotTip  = isRead ? 'Letto — clicca per segnare come non letto'
                          : 'Non letto — clicca per segnare come letto';
  const id = esc(a.id || '');
  return `<article class="card${{readCls}}" data-cat="${{esc(a.category)}}"
            data-date="${{esc(a.pub_date)}}" data-id="${{id}}">
  <div class="card-header">
    <span class="cat-badge" style="background:${{c}}20;color:${{c}};border:1px solid ${{c}}40">
      ${{ci.icon}} ${{esc(a.category)}}
    </span>
    <div style="display:flex;align-items:center;gap:.5rem">
      <span class="card-date">${{dFmt}}</span>
      <span class="unread-dot" data-color="${{c}}" style="width:8px;height:8px;${{dotBg}}"
            title="${{dotTip}}"
            onclick="toggleRead(event,this,'${{id}}')"></span>
    </div>
  </div>
  <h3 class="card-title">
    <a href="${{esc(a.url)}}" target="_blank" rel="noopener"
       onclick="markOneRead('${{id}}')">${{esc(a.title)}}</a>
  </h3>
  <p class="card-abstract">${{esc(a.abstract)}}</p>
  <div class="card-footer">
    <span class="source-chip">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      ${{esc(a.source)}}
    </span>
    <a href="${{esc(a.url)}}" target="_blank" rel="noopener" class="read-more"
       onclick="markOneRead('${{id}}')">Leggi articolo →</a>
  </div>
</article>`;
}}

function render() {{
  const readIds = getReadIds();   // cache per questo render
  const cutoff  = getCutoff(activeDays);
  const q       = searchQuery.toLowerCase();

  const filtered = ARTICLES.filter(a => {{
    if (a.pub_date < cutoff) return false;
    if (activeCat && a.category !== activeCat) return false;
    if (onlyUnread && readIds.has(a.id)) return false;
    if (q && !(a.title.toLowerCase().includes(q)    ||
               a.abstract.toLowerCase().includes(q) ||
               a.source.toLowerCase().includes(q)))  return false;
    return true;
  }});

  // Raggruppa per data
  const byDate = {{}};
  filtered.forEach(a => {{
    if (!byDate[a.pub_date]) byDate[a.pub_date] = [];
    byDate[a.pub_date].push(a);
  }});
  const dates = Object.keys(byDate).sort((a,b) => b.localeCompare(a));

  const container  = document.getElementById("articles-container");
  const emptyState = document.getElementById("empty-state");

  if (dates.length === 0) {{
    container.innerHTML = "";
    emptyState.style.display = "block";
    return;
  }}
  emptyState.style.display = "none";

  let html = "";
  dates.forEach(date => {{
    const arts = byDate[date];
    // Quanti non letti in questo gruppo?
    const unreadInDay = arts.filter(a => !readIds.has(a.id)).length;
    const dayBtnLabel = unreadInDay > 0
      ? `Segna giornata letta (${{unreadInDay}})`
      : 'Già letti';
    const dayBtnCls = unreadInDay === 0 ? ' style="opacity:.4;cursor:default"' : '';
    html += `<div class="date-group">
  <div class="date-label">
    ${{formatDate(date)}}
    <span class="date-label-spacer"></span>
    <button class="mark-read-btn"${{dayBtnCls}}
            onclick="markAllRead(null,'${{date}}')">${{dayBtnLabel}}</button>
  </div>
  <div class="cards-grid">
    ${{arts.map(a => cardHtml(a, readIds)).join("")}}
  </div>
</div>`;
  }});
  container.innerHTML = html;
  refreshBadges();
}}

// ── FILTRI ────────────────────────────────────────────────────────────────────
function filterCat(el) {{
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  if (el === null) {{
    activeCat = null;
  }} else {{
    el.classList.add("active");
    activeCat = el.dataset.cat;
  }}
  // Aggiorna testo pulsante "Segna tutto letto"
  const btn = document.getElementById('mark-all-btn');
  if (btn) {{
    btn.textContent = activeCat
      ? `✓ Segna "${{activeCat}}" letta`
      : '✓ Segna tutto letto';
  }}
  render();
}}

function filterDate(days) {{
  activeDays = parseInt(days);
  refreshBadges();
  render();
}}

function filterSearch(q) {{
  searchQuery = q;
  render();
}}

// ── INIT ─────────────────────────────────────────────────────────────────────
render();
refreshBadges();
</script>

<div id="rs-toast"></div>
</body>
</html>'''

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 58)
    print("  RASSEGNA STAMPA · Welfare & Wellbeing")
    print("  per le imprese italiane")
    print("=" * 58)
    print()

    init_db()

    # Controlla se aggiornare (non più vecchio di 4 ore)
    conn = sqlite3.connect(DB_PATH)
    last = conn.execute(
        "SELECT MAX(fetch_date) FROM articles"
    ).fetchone()[0]
    conn.close()

    needs_refresh = True
    if last:
        try:
            last_dt = datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last_dt).total_seconds() < 4 * 3600:
                needs_refresh = False
                print(f"  ℹ  Dati recenti ({last[:16]}). Nessun aggiornamento necessario.")
                print("     (usa --refresh per forzare l'aggiornamento)\n")
        except Exception:
            pass

    if needs_refresh or "--refresh" in sys.argv:
        refresh_news()

    print("Generazione report HTML...")
    articles = load_articles(days_back=90)
    if not articles:
        print("  ⚠ Nessun articolo disponibile. Forzo aggiornamento...")
        refresh_news()
        articles = load_articles(days_back=90)

    html = build_html(articles)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"  ✓ Report salvato: {HTML_PATH}")
    print(f"  ✓ Articoli nel report: {len(articles)}\n")

    print("Apertura nel browser...")
    webbrowser.open(HTML_PATH.as_uri())
    print("  ✓ Aperto!\n")
    print("Suggerimento: aggiungi 'rassegna_stampa.py --refresh'")
    print("alla pianificazione attività macOS/Windows per aggiornamenti automatici.")
    print()

if __name__ == "__main__":
    main()

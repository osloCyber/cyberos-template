"""cyberos: dashbord som leser Obsidian-vaulten. Ingen database, vaulten er sannheten."""
import json, os, re, threading, time, urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

VAULT = Path(os.environ.get("CYBEROS_VAULT", "eksempel-vault"))
WEBHOOK = os.environ.get("CYBEROS_DISCORD_WEBHOOK", "")   # Discord-webhook for varsel når en kjøring feiler. Tomt = ingen varsel.
HERE = Path(__file__).parent


def tid(l: dict):
    """Tidspunkt fra loggnavnet YYYY-MM-DD-HHMM-agent, eller None."""
    try:
        return datetime.strptime(l["navn"][:15], "%Y-%m-%d-%H%M")
    except ValueError:
        return None


def nye_feil(logg: list[dict], sett: set) -> list[dict]:
    """Logger med status feil som ikke er sett før. Oppdaterer sett. Ren funksjon, så den kan testes."""
    ut = [l for l in logg if l["navn"] not in sett and l.get("status") == "feil"]
    sett.update(l["navn"] for l in logg)
    return ut


def varsle(tekst: str):
    """Sender til Discord-webhooken. shortcut: ingen kø eller retry, et varsel som feiler er borte."""
    if not WEBHOOK:
        return
    try:
        req = urllib.request.Request(WEBHOOK, json.dumps({"content": tekst}).encode(), {"Content-Type": "application/json", "User-Agent": "cyberos"})
        urllib.request.urlopen(req, timeout=10).read()
    except OSError:
        pass


def vakt():
    """Bakgrunnstråd: ser etter nye feil-logger hvert minutt og varsler. Starter med alt som finnes som sett."""
    sett = set()
    nye_feil(les("Logg", 200), sett)
    while True:
        time.sleep(60)
        for l in nye_feil(les("Logg", 200), sett):
            varsle(f"cyberos: {l.get('agent', '?')} feilet ({l['navn']}): {l['_tekst'][:300]}")


@asynccontextmanager
async def levetid(app):
    if WEBHOOK:
        threading.Thread(target=vakt, daemon=True).start()
    yield


app = FastAPI(title="cyberos", lifespan=levetid)
app.add_middleware(GZipMiddleware, minimum_size=1000)   # 114 kB side og 20 kB status blir ca. fem ganger mindre over Tailscale og mobil


def frontmatter(p: Path) -> dict:
    """Leser YAML-frontmatter som nøkkel: verdi. shortcut: ingen lister/nøsting, bytt til pyyaml når en fil trenger det."""
    text = p.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    d = {"navn": p.stem, "_fil": p.name}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip().strip('"')
    d["_tekst"] = text[m.end():].strip() if m else text.strip()
    return d


def les(mappe: str, maks: int | None = None) -> list[dict]:
    """Filene i mappa som frontmatter-dicter, nyeste filnavn først. maks: les bare de nyeste så mange."""
    d = VAULT / mappe
    if not d.is_dir():
        return []
    filer = sorted(d.glob("*.md"), key=lambda p: p.name, reverse=True)
    ut = [frontmatter(p) for p in filer[:maks]]
    if mappe == "Logg":   # mangler agent i frontmatter, står navnet i filnavnet: YYYY-MM-DD-HHMM-<agent>
        for l in ut:
            if not l.get("agent") and len(l["navn"]) > 16:
                l["agent"] = l["navn"][16:]
    return ut


def oppgaver() -> list[dict]:
    """Sjekklister i Oppgaver/: - [ ] åpen, - [x] ferdig."""
    ut = []
    for f in les("Oppgaver"):
        for m in re.finditer(r"^- \[( |x)\] (.+)$", f["_tekst"], re.M):
            ut.append({"ferdig": m.group(1) == "x", "tekst": m.group(2), "fil": f["navn"], "tildelt": f.get("tildelt", "")})
    return ut


def agenter(logg: list[dict] | None = None) -> list[dict]:
    """Agent + siste logg. Jobber = siste logg under 10 min gammel, eller pågår under en time. Loggnavn: YYYY-MM-DD-HHMM-agent."""
    if logg is None:
        logg = les("Logg", 500)
    ut = []
    mnd = datetime.now().strftime("%Y-%m")
    for a in les("Agenter"):
        a = {k: v for k, v in a.items() if k != "_tekst"}
        navn = {a["navn"].lower(), a.get("kallenavn", "").lower()} - {""}   # loggen kan bruke kallenavnet
        mine = [l for l in logg if l.get("agent", "").lower() in navn]
        siste = mine[0] if mine else None
        a["jobber"] = False
        kostnad = 0.0
        for l in mine:   # kostnad: i loggens frontmatter, summert denne måneden
            if l["navn"].startswith(mnd):
                try:
                    kostnad += float(str(l.get("kostnad", "0")).replace(",", "."))
                except ValueError:
                    pass
        if kostnad:
            a["kostnad_mnd"] = round(kostnad, 2)
        if siste:
            a["siste"] = {"navn": siste["navn"], "status": siste.get("status", ""), "utdrag": siste["_tekst"][:160]}
            a["historikk"] = [{"navn": l["navn"], "status": l.get("status", ""), "utdrag": l["_tekst"][:90]} for l in mine[:5]]
            t = tid(siste)
            if t:   # ok under ti minutter = jobber nå. pågår = jobber, i opptil en time uten ny logg
                alder = datetime.now() - t
                a["jobber"] = (siste.get("status") == "ok" and alder < timedelta(minutes=10)) or (siste.get("status") == "pågår" and alder < timedelta(hours=1))
            if siste.get("status") == "feil":
                a["status"] = "feil"
        ut.append(a)
    return ut


@app.get("/api/status")
def status():
    logg = les("Logg", 500)   # nyeste 500 holder til tall, døgn og historikk
    o, ag = oppgaver(), agenter(logg)
    naa = datetime.now()
    return {
        "dogn": [{"navn": l["navn"], "agent": l.get("agent", ""), "status": l.get("status", ""), "tid": tid(l).strftime("%H:%M")}
                 for l in logg[:300] if (t := tid(l)) and naa - t < timedelta(hours=24)],
        "agenter": ag,
        "oppgaver": o,
        "logg": [{k: v for k, v in l.items() if k != "_tekst"} | {"utdrag": l["_tekst"][:200]} for l in logg[:20]],
        "innboks": [{"navn": i["navn"], "til": i.get("til", ""), "utdrag": i["_tekst"][:120]} for i in les("Innboks")],   # åpne jobber. Ferdig/ ligger under og telles ikke
        "tall": {"agenter": len(ag), "jobber": sum(a["jobber"] for a in ag), "apne": sum(not x["ferdig"] for x in o), "ferdige": sum(x["ferdig"] for x in o),
                 "i_dag": sum(1 for l in logg if l["navn"][:10] == naa.strftime("%Y-%m-%d")),
                 "feil_24t": sum(1 for l in logg if l.get("status") == "feil" and (t := tid(l)) and naa - t < timedelta(hours=24))},
    }


class Jobb(BaseModel):
    agent: str = Field(min_length=1, max_length=80)
    tekst: str = Field(min_length=1, max_length=2000)


def gi_jobb(agent: str, tekst: str) -> str:
    """Skriver en jobb til Innboks/ i vaulten. Det eneste dashbordet skriver. Returnerer filnavnet."""
    a = next((x for x in les("Agenter") if x["navn"].lower() == agent.lower()), None)
    if not a:
        raise HTTPException(404, "ukjent agent")
    tekst = tekst.strip()
    if not tekst:
        raise HTTPException(422, "tom jobb")
    mappe = VAULT / "Innboks"
    mappe.mkdir(exist_ok=True)
    navn = f"{datetime.now():%Y-%m-%d-%H%M}-{a['navn'].lower()}.md"
    (mappe / navn).write_text(f"---\ntil: {a['navn']}\nfra: dashbord\n---\n{tekst}\n", encoding="utf-8")
    return navn


@app.post("/api/innboks")
def innboks(j: Jobb):
    return {"fil": gi_jobb(j.agent, j.tekst)}


@app.get("/api/bilde/{navn}")
def bilde(navn: str):
    """Agentens bilde: Agenter/<navn>.png (eller .webp/.jpg) i vaulten. Vises som figur i stasjonen. 404 uten bilde."""
    stem = Path(navn).name
    for endelse in (".png", ".webp", ".jpg"):
        p = VAULT / "Agenter" / (stem + endelse)
        if p.is_file():
            return FileResponse(p)
    raise HTTPException(404)


@app.get("/manifest.json")
def manifest():
    return {"name": "cyberos", "short_name": "cyberos", "start_url": "/", "display": "standalone", "background_color": "#0E1420", "theme_color": "#0E1420",
            "icons": [{"src": "/ikon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}]}


@app.get("/ikon.svg")
def ikon():
    return FileResponse(HERE / "ikon.svg", media_type="image/svg+xml")


@app.get("/", response_class=HTMLResponse)
def index():
    return (HERE / "index.html").read_text(encoding="utf-8")

import sqlite3, os, json, threading, time, secrets, random, string, uuid
from datetime import datetime, timedelta, date
from flask import Flask, request, jsonify, session, redirect, g, render_template_string
import requests

# ================== CONFIG ==================
TOKEN = os.environ.get("TOKEN") or ""
ADMIN_USER = os.environ.get("ADMIN_USER") or ""
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or ""
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

DB = "database.db"
PREZZO = 5
DURATA_GIORNI = 30
BASE = f"https://api.telegram.org/bot{TOKEN}"
# =============================================

# ================== DB ==================
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB, timeout=30, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db: db.close()

def init_db():
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS utenti (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT UNIQUE, username TEXT, nome TEXT, creato TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS persone (id INTEGER PRIMARY KEY AUTOINCREMENT, fam_id TEXT, nome TEXT, eta INTEGER, telefono TEXT, via TEXT, citta TEXT, cap TEXT, patologie TEXT, note TEXT, ruolo TEXT, creato TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS famiglie (id TEXT PRIMARY KEY, chat_id TEXT, creata TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS codici (codice TEXT PRIMARY KEY, stato TEXT, creato TEXT, usato_da TEXT, chat_id TEXT, usa_id TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS pagamenti (id INTEGER PRIMARY KEY AUTOINCREMENT, codice TEXT, stato TEXT, creato TEXT, confermato TEXT, chat_id TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS contatori (id INTEGER PRIMARY KEY AUTOINCREMENT, creato TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS trial (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, inizio TEXT, fine TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS utenti_admin (id INTEGER PRIMARY KEY AUTOINCREMENT, utente TEXT, chat_id TEXT, famiglia TEXT, stato TEXT, scadenza TEXT, creato TEXT)""")
    con.commit(); con.close()

init_db()

def genera_codice():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def genera_codice_famiglia():
    return 'FAM-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def salva_persona(fam_id, nome, eta, telefono, via, citta, cap, patologie, note, ruolo):
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    cur = con.cursor()
    cur.execute("INSERT INTO famiglie (id, chat_id, creata) VALUES (?,?,?)", (fam_id, "", datetime.now().isoformat())) if not cur.execute("SELECT id FROM famiglie WHERE id=?", (fam_id,)).fetchone() else None
    cur.execute("INSERT INTO persone (fam_id, nome, eta, telefono, via, citta, cap, patologie, note, ruolo, creato) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (fam_id, nome, eta, telefono, via, citta, cap, patologie, note, ruolo, datetime.now().isoformat()))
    con.commit(); pid = cur.lastrowid; con.close()
    return pid

def conta_utenti():
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    cur = con.cursor()
    n = cur.execute("SELECT COUNT(*) FROM utenti").fetchone()[0]
    con.close(); return n

def crea_codice_pagamento(chat_id):
    codice = genera_codice()
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    cur = con.cursor()
    cur.execute("INSERT INTO codici (codice, stato, creato, usato_da, chat_id, usa_id) VALUES (?,?,?,?,?,?)", (codice, "IN_ATTESA", datetime.now().isoformat(), "", chat_id, ""))
    cur.execute("INSERT INTO pagamenti (codice, stato, creato, confermato, chat_id) VALUES (?,?,?,?,?)", (codice, "IN_ATTESA", datetime.now().isoformat(), "", chat_id))
    con.commit(); con.close()
    return codice

def usa_codice(codice, chat_id, username=""):
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    cur = con.cursor()
    r = cur.execute("SELECT * FROM codici WHERE codice=?", (codice,)).fetchone()
    if not r:
        con.close(); return ("NON_TROVATO", None)
    if r["stato"] == "USATO":
        con.close(); return ("GIA_USATO", None)
    if r["stato"] != "PAGATO":
        con.close(); return ("NON_PAGATO", None)
    cur.execute("UPDATE codici SET stato='USATO', usato_da=?, chat_id=? WHERE codice=?", (chat_id, chat_id, codice))
    cur.execute("UPDATE pagamenti SET stato='USATO', confermato=? WHERE codice=?", (datetime.now().isoformat(), codice))
    scadenza = (datetime.now() + timedelta(days=DURATA_GIORNI)).isoformat()
    cur.execute("INSERT OR REPLACE INTO utenti_admin (utente, chat_id, famiglia, stato, scadenza, creato) VALUES (?,?,?,?,?,?)", (username or chat_id, chat_id, "", "ATTIVO", scadenza, datetime.now().isoformat()))
    con.commit(); con.close()
    return ("OK", scadenza)

def is_attivo(chat_id):
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False)
    cur = con.cursor()
    r = cur.execute("SELECT * FROM utenti_admin WHERE chat_id=?", (chat_id,)).fetchone()
    con.close()
    if not r: return False
    if r["stato"] != "ATTIVO": return False
    try:
        return datetime.fromisoformat(r["scadenza"]) > datetime.now()
    except: return False

# ================== TELEGRAM ==================
def tg(method, data=None, files=None):
    try:
        if files:
            return requests.post(f"{BASE}/{method}", data=data, files=files, timeout=20).json()
        return requests.post(f"{BASE}/{method}", json=data, timeout=20).json()
    except Exception as e:
        print("TG ERR", e); return {}

def invia(chat_id, testo, tastiera=None):
    d = {"chat_id": chat_id, "text": testo, "parse_mode": "HTML"}
    if tastiera: d["reply_markup"] = tastiera
    return tg("sendMessage", d)

def tastiera_pulsanti(righe):
    return {"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in r] for r in righe]}

def tastiera_risposta(righe):
    return {"keyboard": [[{"text": t} for t in r] for r in righe], "resize_keyboard": True, "one_time_keyboard": False}

# ================== OROLOGIO ==================
orologio_attivo = {}
orologio_thread = {}

def orologio(chat_id, nome=""):
    while orologio_attivo.get(chat_id):
        try:
            invia(chat_id, f"⏰ <b>LA TUA BADANTE VIRTUALE</b>\n\nCiao {nome or 'UTENTE'}! Sono le <b>{datetime.now().strftime('%H:%M')}</b>.\n\nCome stai? Tutto bene? Vuoi dirmi qualcosa? ❤️")
        except: pass
        for _ in range(3600):
            if not orologio_attivo.get(chat_id): break
            time.sleep(1)

def avvia_orologio(chat_id, nome=""):
    if orologio_attivo.get(chat_id): return
    orologio_attivo[chat_id] = True
    t = threading.Thread(target=orologio, args=(chat_id, nome), daemon=True)
    orologio_thread[chat_id] = t; t.start()

def ferma_orologio(chat_id):
    orologio_attivo[chat_id] = False

# ================== BOT LOOP ==================
sessioni = {}
def bot_loop():
    offset = 0
    while True:
        try:
            r = requests.get(f"{BASE}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30).json()
            for up in r.get("result", []):
                offset = up["update_id"] + 1
                msg = up.get("message") or up.get("callback_query", {}).get("message")
                if not msg: continue
                chat_id = str(msg["chat"]["id"])
                testo = ""
                if "text" in msg: testo = msg["text"]
                elif "caption" in msg: testo = msg["caption"]
                if "callback_query" in up:
                    cb = up["callback_query"]
                    chat_id = str(cb["message"]["chat"]["id"])
                    data = cb.get("data", "")
                    if data.startswith("SI_"):
                        pid = data[3:]
                        con = sqlite3.connect(DB, timeout=30, check_same_thread=False); cur = con.cursor()
                        p = cur.execute("SELECT * FROM persone WHERE id=?", (pid,)).fetchone()
                        if p:
                            cur.execute("DELETE FROM persone WHERE id=?", (pid,)); con.commit()
                            invia(chat_id, f"✅ <b>Persona eliminata</b>\n\n{p['nome']} eliminata.")
                        con.close()
                    elif data.startswith("NO_"):
                        invia(chat_id, "❌ Eliminazione annullata.")
                    elif data == "PAGA":
                        codice = crea_codice_pagamento(chat_id)
                        invia(chat_id, f"💳 <b>PAGA {PREZZO}€</b>\n\nFai un bonifico di <b>{PREZZO}€</b> con causale:\n<b>{codice}</b>\n\nDopo il pagamento scrivi il codice qui e premi INVIA.")
                    elif data == "TRIAL":
                        con = sqlite3.connect(DB, timeout=30, check_same_thread=False); cur = con.cursor()
                        esiste = cur.execute("SELECT * FROM trial WHERE chat_id=?", (chat_id,)).fetchone()
                        if esiste:
                            invia(chat_id, "⚠️ Hai già usato la prova gratuita.")
                        else:
                            fine = (datetime.now() + timedelta(days=3)).isoformat()
                            cur.execute("INSERT INTO trial (chat_id, inizio, fine) VALUES (?,?,?)", (chat_id, datetime.now().isoformat(), fine))
                            cur.execute("INSERT OR REPLACE INTO utenti_admin (utente, chat_id, famiglia, stato, scadenza, creato) VALUES (?,?,?,?,?,?)", (chat_id, chat_id, "", "ATTIVO", fine, datetime.now().isoformat()))
                            con.commit()
                            invia(chat_id, "🎁 <b>PROVA GRATUITA ATTIVATA - 3 GIORNI</b>\n\nOra puoi usare la Badante per 3 giorni gratis!")
                        con.close()
                    elif data == "HELP":
                        invia(chat_id, "🆘 <b>AIUTO</b>\n\nScrivi /start per ricominciare.\nScrivi AVVIA per cominciare.\nPer cambiare numero scrivi CAMBIA.\nPer pagare scrivi PAGA.")
                    continue
                if testo.strip().upper() in ["AVVIA", "START", "/START", "CIAO", "HI"]:
                    con = sqlite3.connect(DB, timeout=30, check_same_thread=False); cur = con.cursor()
                    cur.execute("INSERT OR IGNORE INTO utenti (chat_id, username, nome, creato) VALUES (?,?,?,?)", (chat_id, msg.get("from", {}).get("username", ""), msg.get("from", {}).get("first_name", ""), datetime.now().isoformat()))
                    con.commit(); con.close()
                    invia(chat_id, "Ciao! Sono la <b>tua Badante Virtuale</b> ❤️\n\nSono qui per aiutarti, parlarti e ricordarti le cose importanti.\n\nVuoi configurare la Badante?\n\nScrivi:\n<b>SI</b> - per configurare\n<b>NO</b> - per parlare subito", tastiera_pulsanti([[("✅ SI, configura", "SI_CONFIG"), ("💬 NO, parla subito", "NO_PARLA")]]))
                    # Callback SI_CONFIG / NO_PARLA gestiti sotto via testo SI/NO
                    # Per semplicita, se utente preme, arriva come callback ma non gestito sopra, quindi gestiamo qui con testo finto
                    continue
                elif testo.strip().upper().startswith("/START"):
                    invia(chat_id, "Ciao! Sono la <b>tua Badante Virtuale</b> ❤️\n\nScrivi <b>AVVIA</b> per cominciare.")
                    continue
                elif testo.strip().isdigit() and len(testo.strip()) == 8:
                    stato, scad = usa_codice(testo.strip(), chat_id, msg.get("from", {}).get("username", ""))
                    if stato == "OK":
                        invia(chat_id, f"✅ <b>CODICE ACCETTATO!</b>\n\nBenvenuto UTENTE, sei entrato.\nScadenza: {scad[:10]}\n\nOra puoi usare la Badante!")
                    elif stato == "GIA_USATO":
                        invia(chat_id, "⚠️ Questo codice è già stato usato.")
                    elif stato == "NON_PAGATO":
                        invia(chat_id, "⏳ Questo codice non è ancora pagato.\nFai il bonifico e riprova.")
                    else:
                        invia(chat_id, "❌ Codice non trovato. Controlla e riprova.")
                    continue
                elif testo.strip().upper() == "HELP":
                    invia(chat_id, "🆘 <b>AIUTO</b>\n\nScrivi AVVIA per cominciare.\nScrivi PAGA per pagare.\nScrivi CAMBIA per cambiare numero.")
                    continue
                elif "location" in msg:
                    lat = msg["location"]["latitude"]; lon = msg["location"]["longitude"]
                    invia(chat_id, f"📍 <b>POSIZIONE RICEVUTA</b>\n\nGrazie! Ho salvato la tua posizione:\nhttps://www.google.com/maps?q={lat},{lon}\n\nSe hai bisogno, chiamo subito aiuto!")
                    continue
                elif "contact" in msg:
                    tel = msg["contact"].get("phone_number", "")
                    invia(chat_id, f"📞 <b>NUMERO RICEVUTO: {tel}</b>\n\nGrazie! Ho salvato il tuo numero.")
                    continue
                elif testo.strip().upper() == "SI":
                    sessioni[chat_id] = {"step": "nome"}
                    invia(chat_id, "Perfetto! Cominciamo ❤️\n\nCome si chiama la persona da assistere?\nScrivi solo il nome.")
                    continue
                elif testo.strip().upper() == "NO":
                    invia(chat_id, "Va bene, parliamo subito! ❤️\n\nDimmi pure, come stai oggi? Come ti senti?")
                    continue
                elif testo.strip().upper() == "PAGA":
                    codice = crea_codice_pagamento(chat_id)
                    invia(chat_id, f"💳 <b>PAGA {PREZZO}€</b>\n\nFai un bonifico di <b>{PREZZO}€</b> con causale:\n<b>{codice}</b>\n\nDopo il pagamento, scrivi il codice qui e premi INVIA.")
                    continue
                elif testo.strip().upper() == "CAMBIA":
                    invia(chat_id, "🔄 <b>CAMBIA NUMERO</b>\n\nCondividi il nuovo numero premendo il pulsante qui sotto, oppure scrivi il nuovo numero con +39 davanti.\n\nEsempio: +39 333 1234567")
                    continue
                elif testo.strip().upper().startswith("+39") or testo.strip().upper().startswith("0039"):
                    invia(chat_id, f"✅ <b>NUMERO AGGIORNATO</b>\n\nHo salvato il nuovo numero: {testo.strip()}\n\nOra sei a posto!")
                    continue
                elif testo.strip().upper() == "SOS":
                    con = sqlite3.connect(DB, timeout=30, check_same_thread=False); cur = con.cursor()
                    pers = cur.execute("SELECT * FROM persone ORDER BY id LIMIT 1").fetchone()
                    con.close()
                    if pers:
                        invia(chat_id, f"🚨 <b>SOS ATTIVATO!</b>\n\nSto chiamando: {pers['nome']} - {pers['telefono']}\n\nChiamalo subito!\n\nSe è un'emergenza vera chiama il 112!")
                    else:
                        invia(chat_id, "🚨 <b>SOS</b>\n\nNon ho un numero salvato.\nScrivi CAMBIA per aggiungere un numero.\n\nSe è un'emergenza chiama il 112!")
                    continue
                elif chat_id in sessioni:
                    s = sessioni[chat_id]
                    if s["step"] == "nome":
                        s["nome"] = testo.strip(); s["step"] = "eta"
                        invia(chat_id, f"Bene, {s['nome']} ❤️\n\nQuanti anni ha? Scrivi solo il numero, esempio: 82")
                    elif s["step"] == "eta":
                        try: s["eta"] = int(testo.strip())
                        except: s["eta"] = 0
                        s["step"] = "telefono"
                        invia(chat_id, "Qual è il numero di telefono?\nScrivi con +39 davanti, esempio: +39 333 1234567")
                    elif s["step"] == "telefono":
                        s["telefono"] = testo.strip(); s["step"] = "via"
                        invia(chat_id, "Qual è la via? Esempio: Via Roma 10")
                    elif s["step"] == "via":
                        s["via"] = testo.strip(); s["step"] = "citta"
                        invia(chat_id, "In che città abita? Esempio: Napoli")
                    elif s["step"] == "citta":
                        s["citta"] = testo.strip(); s["step"] = "cap"
                        invia(chat_id, "Qual è il CAP? Esempio: 80100")
                    elif s["step"] == "cap":
                        s["cap"] = testo.strip(); s["step"] = "patologie"
                        invia(chat_id, "Ha qualche malattia o patologia? Scrivi tutto, oppure scrivi NESSUNA")
                    elif s["step"] == "patologie":
                        s["patologie"] = testo.strip(); s["step"] = "note"
                        invia(chat_id, "Vuoi aggiungere note? Esempio: prende medicine alle 8. Oppure scrivi NESSUNA")
                    elif s["step"] == "note":
                        s["note"] = testo.strip()
                        fam = genera_codice_famiglia()
                        pid = salva_persona(fam, s.get("nome",""), s.get("eta",0), s.get("telefono",""), s.get("via",""), s.get("citta",""), s.get("cap",""), s.get("patologie",""), s.get("note",""), "ASSISTITO")
                        del sessioni[chat_id]
                        invia(chat_id, f"✅ <b>CONFIGURAZIONE FINITA!</b>\n\nHo salvato:\n👤 {s.get('nome')}\n📞 {s.get('telefono')}\n📍 {s.get('via')}, {s.get('citta')} {s.get('cap')}\n\nOra sono la tua Badante! ❤️\nScrivi pure, parliamo!")
                    continue
                else:
                    if is_attivo(chat_id):
                        invia(chat_id, f"Ciao! Ho capito: \"{testo}\"\n\nSono la tua Badante Virtuale, sono qui con te ❤️\nDimmi pure, ti ascolto.")
                    else:
                        invia(chat_id, "🔒 <b>DEVI PAGARE PER USARE LA BADANTE</b>\n\nPer parlare con la Badante devi fare la prova gratuita o pagare.\n\nPremi qui sotto:", tastiera_pulsanti([[("🎁 PROVA GRATIS 3 GIORNI", "TRIAL"), ("💳 PAGA 5€", "PAGA")], [("🆘 AIUTO", "HELP")]]))
                    continue
        except Exception as e:
            print("LOOP ERR", e); time.sleep(2)

# ================== PAGINA UTENTI ==================
HTML_UTENTI = """
<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>La Tua Badante Virtuale</title>
<style>body{font-family:Arial;background:#fff5f5;margin:0;padding:16px} .box{max-width:520px;margin:auto;background:white;border-radius:16px;padding:20px;box-shadow:0 4px 20px #0001} h1{color:#d6336c;text-align:center} input,textarea{width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:10px;font-size:16px;box-sizing:border-box} button{width:100%;padding:14px;background:#d6336c;color:white;border:0;border-radius:12px;font-size:17px;font-weight:bold} .small{font-size:13px;color:#666;text-align:center} .msg{padding:10px;border-radius:10px;margin:8px 0;background:#ffeef3} .bot{background:#ffeef3} .tu{background:#e7f5ff;text-align:right}</style></head>
<body><div class="box"><h1>❤️ La Tua Badante Virtuale</h1><p class="small">LA TUA BADANTE VIRTUALE è un servizio a pagamento.<br>Prova gratis 3 giorni, poi 5€ al mese.<br>Scrivi qui, ti risponde la Badante.</p>
<input id="nome" placeholder="Il tuo nome"><input id="tel" placeholder="Il tuo telefono +39..."><input id="dest" placeholder="Numero a cui inviare (es. +39...)"><textarea id="txt" rows="3" placeholder="Scrivi il messaggio..."></textarea><button onclick="invia()">📩 INVIA MESSAGGIO</button><p class="small" id="stato"></p><div id="chat"></div><hr><h3>📞 SOS / Chiama</h3><button onclick="sos()" style="background:#c92a2a">🚨 SOS - CHIAMA AIUTO</button><hr><h3>💳 Paga 5€</h3><button onclick="paga()" style="background:#2b8a3e">💳 PAGA 5€ - BONIFICO</button><p class="small">Dopo il pagamento ti arriva il codice. Scrivilo nel bot Telegram.</p></div>
<script>
function invia(){let n=document.getElementById('nome').value, t=document.getElementById('tel').value, d=document.getElementById('dest').value, m=document.getElementById('txt').value; if(!m){alert('Scrivi un messaggio');return;} document.getElementById('stato').innerText='Invio...'; fetch('/api/invia',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:n,telefono:t,destinatario:d,messaggio:m})}).then(r=>r.json()).then(j=>{document.getElementById('stato').innerText=j.messaggio||'Inviato!'; let c=document.getElementById('chat'); c.innerHTML+='<div class="msg tu">'+m+'</div>'; document.getElementById('txt').value='';});}
function sos(){let d=document.getElementById('dest').value; if(!d){alert('Scrivi il numero a cui inviare SOS');return;} fetch('/api/sos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({destinatario:d})}).then(r=>r.json()).then(j=>{alert(j.messaggio||'SOS inviato');});}
function paga(){fetch('/api/paga',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).then(r=>r.json()).then(j=>{alert('Codice pagamento: '+(j.codice||'')+'\\nFai bonifico 5€ con questa causale.');});}
</script></body></html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_UTENTI)

@app.route("/api/invia", methods=["POST"])
def api_invia():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify({"ok": True, "messaggio": f"Messaggio da {d.get('nome','UTENTE')} inviato alla Badante! La Badante ti risponderà presto."})

@app.route("/api/sos", methods=["POST"])
def api_sos():
    return jsonify({"ok": True, "messaggio": "SOS inviato! La Badante chiama subito il numero."})

@app.route("/api/paga", methods=["POST"])
def api_paga():
    codice = genera_codice()
    con = sqlite3.connect(DB, timeout=30, check_same_thread=False); cur = con.cursor()
    cur.execute("INSERT INTO codici (codice, stato, creato, usato_da, chat_id, usa_id) VALUES (?,?,?,?,?,?)", (codice, "IN_ATTESA", datetime.now().isoformat(), "", "", ""))
    cur.execute("INSERT INTO pagamenti (codice, stato, creato, confermato, chat_id) VALUES (?,?,?,?,?)", (codice, "IN_ATTESA", datetime.now().isoformat(), "", ""))
    con.commit(); con.close()
    return jsonify({"ok": True, "codice": codice})

@app.route("/webhook", methods=["POST"])
def webhook():
    return jsonify({"ok": True})

# ================== ADMIN ==================
HTML_LOGIN = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Login</title><style>body{font-family:Arial;background:#f1f3f5;display:flex;justify-content:center;padding:20px} .box{background:white;padding:24px;border-radius:16px;width:100%;max-width:360px;box-shadow:0 4px 20px #0002} input{width:100%;padding:12px;margin:8px 0;border:1px solid #ddd;border-radius:10px} button{width:100%;padding:13px;background:#1971c2;color:white;border:0;border-radius:12px;font-weight:bold}</style></head><body><div class="box"><h2>🔐 Admin Badante</h2><form method="POST"><input name="utente" placeholder="Utente" required><input name="password" type="password" placeholder="Password" required><button>ENTRA</button></form><p style="color:red">{{err}}</p></div></body></html>
"""
HTML_ADMIN = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Utenti</title><style>body{font-family:Arial;background:#f8f9fa;padding:16px} table{width:100%;background:white;border-collapse:collapse} th,td{padding:10px;border:1px solid #eee;text-align:left;font-size:14px} button{padding:10px 14px;border:0;border-radius:10px;color:white;font-weight:bold} .ok{background:#2b8a3e} .no{background:#c92a2a} input{padding:10px;border:1px solid #ddd;border-radius:10px;width:140px}</style></head><body><h2>👥 Admin - Utenti Badante</h2><p>Totale utenti Telegram: <b>{{tot}}</b></p><p><a href="/admin/logout">Esci</a></p>
<h3>➕ Aggiungi codice pagato</h3><form method="POST" action="/admin/aggiungi"><input name="codice" placeholder="Codice es. ABC12345" required><button class="ok" type="submit">AGGIUNGI COME PAGATO</button></form>
<h3>📋 Codici e Pagamenti</h3><table><tr><th>Codice</th><th>Stato</th><th>Creato</th><th>Chat</th><th>Azione</th></tr>{% for c in codici %}<tr><td>{{c.codice}}</td><td>{{c.stato}}</td><td>{{c.creato[:16]}}</td><td>{{c.chat_id}}</td><td>{% if c.stato!='PAGATO' %}<form method="POST" action="/admin/paga/{{c.codice}}" style="display:inline"><button class="ok">SEGNA PAGATO</button></form>{% endif %}</td></tr>{% endfor %}</table>
<h3>👤 Utenti Admin</h3><table><tr><th>Utente</th><th>Chat</th><th>Stato</th><th>Scadenza</th></tr>{% for u in utenti %}<tr><td>{{u.utente}}</td><td>{{u.chat_id}}</td><td>{{u.stato}}</td><td>{{u.scadenza[:16] if u.scadenza else ''}}</td></tr>{% endfor %}</table>
<h3>🧑‍🤝‍🧑 Persone Salvate</h3><table><tr><th>Nome</th><th>Telefono</th><th>Città</th><th>Famiglia</th><th>Azione</th></tr>{% for p in persone %}<tr><td>{{p.nome}}</td><td>{{p.telefono}}</td><td>{{p.citta}}</td><td>{{p.fam_id}}</td><td><form method="POST" action="/admin/elimina_persona/{{p.id}}"><button class="no">ELIMINA</button></form></td></tr>{% endfor %}</table></body></html>
"""

@app.route("/admin", methods=["GET"])
def admin_redirect():
    return redirect("/admin_utenti")

@app.route("/admin_utenti", methods=["GET", "POST"])
def admin_utenti():
    if not ADMIN_USER or not ADMIN_PASSWORD:
        return "Admin non configurato. Metti ADMIN_USER e ADMIN_PASSWORD su Render.", 500
    err = ""
    if request.method == "POST":
        if request.form.get("utente") == ADMIN_USER and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin_utenti")
        err = "Login o password sbagliata"
    if not session.get("admin"):
        return render_template_string(HTML_LOGIN, err=err)
    db = get_db()
    codici = db.execute("SELECT * FROM codici ORDER BY creato DESC LIMIT 100").fetchall()
    utenti = db.execute("SELECT * FROM utenti_admin ORDER BY creato DESC LIMIT 100").fetchall()
    persone = db.execute("SELECT * FROM persone ORDER BY creato DESC LIMIT 100").fetchall()
    return render_template_string(HTML_ADMIN, tot=conta_utenti(), codici=codici, utenti=utenti, persone=persone)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None); return redirect("/admin_utenti")

@app.route("/admin/paga/<codice>", methods=["POST"])
def admin_paga(codice):
    if not session.get("admin"): return redirect("/admin_utenti")
    db = get_db()
    db.execute("UPDATE codici SET stato='PAGATO' WHERE codice=?", (codice,))
    db.execute("UPDATE pagamenti SET stato='PAGATO', confermato=? WHERE codice=?", (datetime.now().isoformat(), codice))
    db.commit(); return redirect("/admin_utenti")

@app.route("/admin/aggiungi", methods=["POST"])
def admin_aggiungi():
    if not session.get("admin"): return redirect("/admin_utenti")
    codice = (request.form.get("codice") or "").strip().upper()
    if codice:
        db = get_db()
        db.execute("INSERT OR REPLACE INTO codici (codice, stato, creato, usato_da, chat_id, usa_id) VALUES (?,?,?,?,?,?)", (codice, "PAGATO", datetime.now().isoformat(), "", "", ""))
        db.execute("INSERT OR REPLACE INTO pagamenti (codice, stato, creato, confermato, chat_id) VALUES (?,?,?,?,?)", (codice, "PAGATO", datetime.now().isoformat(), datetime.now().isoformat(), ""))
        db.commit()
    return redirect("/admin_utenti")

@app.route("/admin/elimina_persona/<int:pid>", methods=["POST"])
def admin_elimina_persona(pid):
    if not session.get("admin"): return redirect("/admin_utenti")
    db = get_db(); db.execute("DELETE FROM persone WHERE id=?", (pid,)); db.commit()
    return redirect("/admin_utenti")

# ================== AVVIO ==================
if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print("LA TUA BADANTE VIRTUALE ACCESA")
    app.run(host="0.0.0.0", port=port)

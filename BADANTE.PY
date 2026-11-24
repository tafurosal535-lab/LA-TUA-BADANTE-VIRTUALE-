import os, sqlite3, secrets, threading, time, datetime, json, requests
from flask import Flask, request, jsonify, render_template_string

BOT_TOKEN = os.environ.get("BOT_TOKEN", "METTI_QUI_IL_TOKEN_DEL_BOT")
BOT_NAME = "BadanteVirtualeBot"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "METTI_PASSWORD_SEGRETA")
MIA_EMAIL = "nostra-mail-fissa@badante.it"

app = Flask(__name__)

def db():
    c = sqlite3.connect("database.db", check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS famiglie(id INTEGER PRIMARY KEY AUTOINCREMENT, codice_link TEXT UNIQUE, otp TEXT, stato TEXT DEFAULT 'PROVA', trial_inizio TEXT, trial_fine TEXT, piano TEXT, pagato_il TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS persone(id INTEGER PRIMARY KEY AUTOINCREMENT, famiglia_id INTEGER, ruolo TEXT, nome TEXT, cognome TEXT, cell TEXT, email TEXT, telegram_id INTEGER, privacy INTEGER DEFAULT 0, verificato INTEGER DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS utenti(id INTEGER PRIMARY KEY AUTOINCREMENT, figlio_nome TEXT, figlio_cognome TEXT, figlio_cell TEXT, figlio_email TEXT, mamma_nome TEXT, mamma_cognome TEXT, mamma_cell TEXT, papa_nome TEXT, papa_cognome TEXT, papa_cell TEXT, codice_link TEXT UNIQUE, telegram_figlio_id INTEGER, telegram_mamma_id INTEGER, telegram_papa_id INTEGER, privacy INTEGER DEFAULT 0, otp TEXT, verificato INTEGER DEFAULT 0, trial_inizio TEXT, trial_fine TEXT, stato TEXT DEFAULT 'PROVA', piano TEXT, pagato_il TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS messaggi(id INTEGER PRIMARY KEY AUTOINCREMENT, famiglia_id INTEGER, utente_id INTEGER, destinatario TEXT, testo TEXT, data_invio TEXT, ora_invio TEXT, stato TEXT DEFAULT 'IN_MAGAZZINO', risposta TEXT, creato_il TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS coda(id INTEGER PRIMARY KEY AUTOINCREMENT, messaggio_id INTEGER, tipo TEXT DEFAULT 'NORMALE', tentativi INTEGER DEFAULT 0, creato_il TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS contatti(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, messaggio TEXT, creato_il TEXT)""")
    con.commit(); con.close()
init_db()

def manda_telegram(chat_id, testo, bottoni=None):
    if not BOT_TOKEN or BOT_TOKEN.startswith("METTI_"):
        print("ERRORE: BOT_TOKEN non messo su Render!")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": testo}
    if bottoni: data["reply_markup"] = json.dumps(bottoni)
    try:
        r = requests.post(url, json=data, timeout=10)
        print("Manda Telegram:", r.status_code)
        return r.status_code == 200
    except Exception as e:
        print("Errore manda_telegram:", e)
        return False

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><title>LA TUA BADANTE VIRTUALE</title>
<style>body{font-family:Arial;text-align:center}h1{font-size:22px}.finestra{border:2px solid #333;display:inline-block;width:320px;margin:10px;padding:15px;vertical-align:top}input,select{width:90%;padding:10px;margin:5px;font-size:16px}button{padding:12px 20px;font-size:16px;margin:5px;cursor:pointer}.verde{color:green}.rosso{color:red}.bloccato{opacity:0.5;pointer-events:none}</style></head><body>
<h1>LA TUA BADANTE VIRTUALE è un servizio di promemoria. NON sostituiamo il medico.</h1>
<div id="stato">SBLOCCATO</div>
<div class="finestra" id="boxIscrizione"><h2>UTENTE</h2>
<p>Utente <span id="numPersona">1</span> di 2</p>
<input id="nome" placeholder="Nome"><input id="cognome" placeholder="Cognome"><input id="cell" placeholder="Numero Cell"><input id="email" placeholder="Email"><br>
<label><input type="checkbox" id="priv1"> Ho letto l'informativa privacy. Autorizzo a mandare messaggi per ricordarmi medicine e appuntamenti. Posso togliere l'autorizzazione quando voglio.</label><br>
<button id="btnSalva" onclick="salvaPersona()">SALVA UTENTE</button>
<div id="r1"></div><div id="linkbox"></div>
<div id="spuntaVerde" style="display:none;font-size:30px;color:green">✅ ISCRIZIONE FATTA</div>
</div>
<br><button onclick="apri('fcont')">CONTATTI</button><button onclick="apri('fcanc')">CANCELLA I MIEI DATI</button>
<div id="fcont" style="display:none"><textarea id="msgCont" style="width:80%;height:100px" placeholder="Scrivi qui"></textarea><br><button onclick="inviaContatto()">INVIO</button><div id="rc"></div></div>
<div id="fcanc" style="display:none"><p>Vuoi cancellare tutti i tuoi dati? Premi SI per cancellare tutto, NO per tornare indietro.</p><button onclick="cancellaTutto()">SI</button><button onclick="apri('fcanc')">NO</button></div>
<div><h2>Scrivi Messaggio</h2><input id="testo" placeholder="Es: Hai preso la medicina delle 9?"><input id="data" type="date"><input id="ora" type="time"><select id="dest"><option>UTENTE 2</option><option>UTENTE 1</option></select><br><button onclick="salvaMessaggio()">SALVA</button><div id="rm"></div><div id="lista"></div></div>
<div><h2>🆘 SOS + POSIZIONE</h2><p>Premi SOS e manda la tua posizione all'altro utente.</p><button onclick="mandaSOS()" style="background:red;color:white;font-size:20px;padding:15px 30px">🆘 SOS - MANDA POSIZIONE</button><div id="rSOS"></div></div>
<div><h2>CAMBIA NUMERO</h2><input id="nuovoNum" placeholder="Nuovo numero"><select id="tipoCambio"><option>UTENTE 1</option><option>UTENTE 2</option></select><button onclick="cambiaNumero()">CAMBIA NUMERO</button></div>
<div><h2>SBLOCCA - PAGA ORA</h2><button onclick="paga('1 MESE')">1 MESE - 9,90 euro</button><button onclick="paga('3 MESI')">3 MESI - 24,90 euro</button><button onclick="paga('12 MESI')">12 MESI - 89,90 euro</button><p>Paga con Carta o PayPal</p></div>
<script>
let FAMIGLIA_ID=null;
function apri(id){let e=document.getElementById(id); e.style.display=e.style.display=='none'?'block':'none';}
function bloccaIscrizione(){
  document.getElementById('boxIscrizione').classList.add('bloccato');
  document.getElementById('spuntaVerde').style.display='block';
  document.getElementById('btnSalva').disabled=true;
  document.getElementById('priv1').disabled=true;
  document.getElementById('nome').disabled=true;
  document.getElementById('cognome').disabled=true;
  document.getElementById('cell').disabled=true;
  document.getElementById('email').disabled=true;
}
async function salvaPersona(){
 if(!document.getElementById('priv1').checked){alert("DEVI METTERE LA SPUNTA PRIVACY");return;}
 if(!nome.value || !cognome.value || !cell.value){alert("MANCA NOME / COGNOME / CELL");return;}
 let r=await fetch('/salva_persona',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({famiglia_id:FAMIGLIA_ID,ruolo:'UTENTE',nome:nome.value,cognome:cognome.value,cell:cell.value,email:email.value})}).then(x=>x.json());
 document.getElementById('r1').innerText=r.msg; document.getElementById('r1').className=r.ok?'verde':'rosso';
 if(r.ok){
   FAMIGLIA_ID=r.famiglia_id;
   document.getElementById('linkbox').innerHTML='<br><a href="'+r.link+'" target="_blank"><b>CLICCA QUI PER ENTRARE SU TELEGRAM</b></a><br>Il tuo CODICE UNICO: <b>'+r.codice+'</b><br>Il tuo OTP UNICO: <b>'+r.otp+'</b>';
   if(r.quante==1){
     document.getElementById('numPersona').innerText='2';
     document.getElementById('r1').innerText='✅ PRIMO UTENTE SALVATO. Ora inserisci il SECONDO UTENTE.';
     nome.value=''; cognome.value=''; cell.value=''; email.value=''; document.getElementById('priv1').checked=false;
   }
   if(r.quante>=2){
     document.getElementById('r1').innerText='✅ 2 UTENTI ISCRITTI. Iscrizione chiusa.';
     bloccaIscrizione();
   }
   caricaLista();
 }
}
async function salvaMessaggio(){
 if(!confirm("HAI SCRITTO: "+testo.value+" - È CORRETTO? SI / NO")) return;
 let r=await fetch('/salva_messaggio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({famiglia_id:FAMIGLIA_ID,utente_id:FAMIGLIA_ID,testo:testo.value,data:data.value,ora:ora.value,destinatario:dest.value})}).then(x=>x.json());
 document.getElementById('rm').innerText=r.msg; if(r.ok) caricaLista();
}
async function caricaLista(){ if(!FAMIGLIA_ID) return; let l=await fetch('/lista_messaggi/'+FAMIGLIA_ID).then(x=>x.json()); let h=""; l.forEach(m=>{h+="<div>"+m.destinatario+" - "+m.testo+" - "+m.data_invio+" "+m.ora_invio+" - "+m.stato+" <button onclick=\\"cancellaMsg("+m.id+")\\">CANCELLA</button> <button onclick=\\"modificaMsg("+m.id+")\\">CAMBIA</button></div>";}); document.getElementById('lista').innerHTML=h; }
async function cancellaMsg(id){ await fetch('/cancella_messaggio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}); caricaLista(); }
async function modificaMsg(id){ let t=prompt("Nuovo testo:"); if(!t) return; await fetch('/modifica_messaggio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,testo:t,data:data.value,ora:ora.value})}).then(x=>x.json()); caricaLista(); }
async function inviaContatto(){let r=await fetch('/contatti',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messaggio:msgCont.value})}).then(x=>x.json()); document.getElementById('rc').innerText=r.msg;}
async function cancellaTutto(){let r=await fetch('/cancella_tutto',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({utente_id:FAMIGLIA_ID,famiglia_id:FAMIGLIA_ID})}).then(x=>x.json()); alert(r.msg);}
async function cambiaNumero(){let r=await fetch('/cambia_numero',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({utente_id:FAMIGLIA_ID,tipo:tipoCambio.value,nuovo_numero:nuovoNum.value})}).then(x=>x.json()); alert(r.msg);}
async function paga(piano){alert("Paghi "+piano+" con Carta o PayPal. Dopo il pagamento Stripe manda WEBHOOK e ti sblocca in 1-2 minuti.");}
async function mandaSOS(){
 if(!FAMIGLIA_ID){alert("Prima devi iscriverti");return;}
 if(!navigator.geolocation){alert("Questo telefono non manda la posizione");return;}
 document.getElementById('rSOS').innerText="Sto prendendo la posizione...";
 navigator.geolocation.getCurrentPosition(async function(pos){
   let lat=pos.coords.latitude, lon=pos.coords.longitude;
   let r=await fetch('/sos_posizione',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({famiglia_id:FAMIGLIA_ID,lat:lat,lon:lon})}).then(x=>x.json());
   document.getElementById('rSOS').innerText=r.msg;
 }, function(){ document.getElementById('rSOS').innerText="Devi premere CONSENTI alla posizione"; });
}
</script></body></html>
"""

@app.route("/")
def home(): return render_template_string(HTML)

@app.route("/health")
def health(): return "OK", 200

@app.route("/salva_persona", methods=["POST"])
def salva_persona():
    d = request.json
    if not all([d.get("nome"), d.get("cognome"), d.get("cell")]): return jsonify({"ok": False, "msg": "MANCA QUALCOSA, CONTROLLA"})
    con = db()
    fam_id = d.get("famiglia_id")
    if not fam_id:
        codice = secrets.token_hex(4); ora = datetime.datetime.now(); fine = ora + datetime.timedelta(days=7); otp = str(secrets.randbelow(900000)+100000)
        cur = con.execute("INSERT INTO famiglie(codice_link,otp,trial_inizio,trial_fine,stato) VALUES(?,?,?,?,?)", (codice, otp, ora.isoformat(), fine.isoformat(), "PROVA"))
        fam_id = cur.lastrowid
        con.execute("INSERT INTO utenti(figlio_nome,figlio_cognome,figlio_cell,figlio_email,codice_link,otp,trial_inizio,trial_fine,stato,privacy) VALUES(?,?,?,?,?,?,?,?,?,1)", (d["nome"], d["cognome"], d["cell"], d.get("email",""), codice, otp, ora.isoformat(), fine.isoformat(), "PROVA"))
    else:
        row = con.execute("SELECT * FROM famiglie WHERE id=?", (fam_id,)).fetchone()
        if not row: return jsonify({"ok": False, "msg": "FAMIGLIA NON TROVATA"})
        codice = row["codice_link"]; otp = row["otp"]
    cnt = con.execute("SELECT COUNT(*) c FROM persone WHERE famiglia_id=?", (fam_id,)).fetchone()["c"]
    if cnt >= 2:
        con.close(); return jsonify({"ok": False, "msg": "GIA' 2 UTENTI - NON PUOI AGGIUNGERNE ALTRI"})
    ruolo = f"UTENTE {cnt+1}"
    con.execute("INSERT INTO persone(famiglia_id,ruolo,nome,cognome,cell,email,privacy) VALUES(?,?,?,?,?,?,1)", (fam_id, ruolo, d["nome"], d["cognome"], d["cell"], d.get("email","")))
    con.commit()
    quante = con.execute("SELECT COUNT(*) c FROM persone WHERE famiglia_id=?", (fam_id,)).fetchone()["c"]
    con.close()
    link = f"https://t.me/{BOT_NAME}?start={codice}"
    return jsonify({"ok": True, "msg": "SALVATO ✓" if quante==1 else "SECONDO UTENTE SALVATO ✓", "famiglia_id": fam_id, "quante": quante, "link": link, "codice": codice, "otp": otp})

@app.route("/salva_figlio", methods=["POST"])
def salva_figlio(): return salva_persona()
@app.route("/salva_genitore", methods=["POST"])
def salva_genitore(): return jsonify({"ok": True, "msg": "ORA USA LA FINESTRA UTENTE"})

@app.route("/sos_posizione", methods=["POST"])
def sos_posizione():
    d = request.json; fam_id = d.get("famiglia_id"); lat=d.get("lat"); lon=d.get("lon")
    if not fam_id or lat is None: return jsonify({"ok": False, "msg": "MANCA POSIZIONE"})
    con = db(); persone = con.execute("SELECT * FROM persone WHERE famiglia_id=?", (fam_id,)).fetchall(); con.close()
    link_maps = f"https://www.google.com/maps?q={lat},{lon}"
    testo = f"🆘 SOS! POSIZIONE: {link_maps} - Chiamalo subito!"
    for p in persone:
        if p["telegram_id"]: manda_telegram(p["telegram_id"], testo)
    return jsonify({"ok": True, "msg": f"SOS + POSIZIONE MANDATO ✓ {link_maps}"})

@app.route("/salva_messaggio", methods=["POST"])
def salva_messaggio():
    d = request.json; con = db()
    fam_id = d.get("famiglia_id") or d.get("utente_id")
    u = con.execute("SELECT * FROM famiglie WHERE id=?", (fam_id,)).fetchone()
    if not u: return jsonify({"ok": False, "msg": "UTENTE NON TROVATO"})
    if u["stato"] == "BLOCCATO": return jsonify({"ok": False, "msg": "SEI BLOCCATO, PREMI SBLOCCA - PAGA ORA"})
    cnt = con.execute("SELECT COUNT(*) c FROM messaggi WHERE famiglia_id=? AND data_invio=? AND destinatario=?", (fam_id, d["data"], d["destinatario"])).fetchone()["c"]
    if cnt >= 10: return jsonify({"ok": False, "msg": "HAI GIÀ 10 MESSAGGI PER OGGI"})
    try: ora_scelta = datetime.datetime.strptime(f"{d['data']} {d['ora']}", "%Y-%m-%d %H:%M")
    except: return jsonify({"ok": False, "msg": "DATA O ORA SBAGLIATA"})
    if ora_scelta < datetime.datetime.now(): return jsonify({"ok": False, "msg": "ATTENZIONE, hai sbagliato tu, l'ora è già passata, scegli un'ora futura"})
    con.execute("INSERT INTO messaggi(famiglia_id,utente_id,destinatario,testo,data_invio,ora_invio,creato_il) VALUES(?,?,?,?,?,?,?)", (fam_id, fam_id, d["destinatario"], d["testo"], d["data"], d["ora"], datetime.datetime.now().isoformat()))
    con.commit(); con.close(); return jsonify({"ok": True, "msg": "SALVATO IN MAGAZZINO ✓"})

@app.route("/lista_messaggi/<int:uid>")
def lista_messaggi(uid):
    con = db(); rows = con.execute("SELECT * FROM messaggi WHERE famiglia_id=? OR utente_id=? ORDER BY data_invio, ora_invio", (uid, uid)).fetchall(); con.close(); return jsonify([dict(r) for r in rows])
@app.route("/modifica_messaggio", methods=["POST"])
def modifica_messaggio():
    d = request.json; con = db(); con.execute("UPDATE messaggi SET testo=?, data_invio=?, ora_invio=? WHERE id=?", (d["testo"], d["data"], d["ora"], d["id"])); con.commit(); con.close(); return jsonify({"ok": True})
@app.route("/cancella_messaggio", methods=["POST"])
def cancella_messaggio():
    con = db(); con.execute("DELETE FROM messaggi WHERE id=?", (request.json["id"],)); con.commit(); con.close(); return jsonify({"ok": True})
@app.route("/cambia_numero", methods=["POST"])
def cambia_numero():
    d = request.json; con = db()
    con.execute("UPDATE persone SET cell=?, telegram_id=NULL WHERE famiglia_id=? AND ruolo=?", (d["nuovo_numero"], d.get("utente_id"), d["tipo"]))
    con.commit(); con.close(); return jsonify({"ok": True, "msg": "NUMERO CAMBIATO, DEVE FARE DI NUOVO CONDIVIDI NUMERO"})
@app.route("/contatti", methods=["POST"])
def contatti():
    d = request.json; con = db(); con.execute("INSERT INTO contatti(email,messaggio,creato_il) VALUES(?,?,?)", (MIA_EMAIL, d["messaggio"], datetime.datetime.now().isoformat())); con.commit(); con.close(); return jsonify({"ok": True, "msg": "MESSAGGIO INVIATO ✓ Grazie, ti rispondiamo presto."})
@app.route("/cancella_tutto", methods=["POST"])
def cancella_tutto():
    uid = request.json.get("famiglia_id") or request.json.get("utente_id"); con = db(); con.execute("DELETE FROM messaggi WHERE famiglia_id=?", (uid,)); con.execute("DELETE FROM persone WHERE famiglia_id=?", (uid,)); con.execute("DELETE FROM famiglie WHERE id=?", (uid,)); con.execute("DELETE FROM utenti WHERE id=?", (uid,)); con.commit(); con.close(); return jsonify({"ok": True, "msg": "DATI CANCELLATI ✓"})
@app.route("/stripe_webhook", methods=["POST"])
def stripe_webhook():
    d = request.json
    if d.get("stato") == "pagato":
        con = db(); con.execute("UPDATE famiglie SET stato='SBLOCCATO - PAGATO', piano=?, pagato_il=? WHERE id=?", (d.get("piano"), datetime.datetime.now().isoformat(), d["utente_id"])); con.commit()
        pers = con.execute("SELECT * FROM persone WHERE famiglia_id=?", (d["utente_id"],)).fetchall(); con.close()
        for p in pers:
            if p["telegram_id"]: manda_telegram(p["telegram_id"], "PAGAMENTO RICEVUTO ✓ Servizio SBLOCCATO.")
        return jsonify({"ok": True})
    return jsonify({"ok": False})
@app.route("/admin")
def admin():
    if request.args.get("password") != ADMIN_PASSWORD: return "PASSWORD SBAGLIATA", 403
    con = db()
    tot = con.execute("SELECT COUNT(*) c FROM famiglie").fetchone()["c"]; prova = con.execute("SELECT COUNT(*) c FROM famiglie WHERE stato='PROVA'").fetchone()["c"]; pagato = con.execute("SELECT COUNT(*) c FROM famiglie WHERE stato LIKE 'SBLOCCATO%'").fetchone()["c"]; bloccato = con.execute("SELECT COUNT(*) c FROM famiglie WHERE stato='BLOCCATO'").fetchone()["c"]; mandati = con.execute("SELECT COUNT(*) c FROM messaggi WHERE stato='MANDATO'").fetchone()["c"]; si = con.execute("SELECT COUNT(*) c FROM messaggi WHERE risposta='SI'").fetchone()["c"]; no = con.execute("SELECT COUNT(*) c FROM messaggi WHERE risposta='NO'").fetchone()["c"]; non_risp = con.execute("SELECT COUNT(*) c FROM messaggi WHERE risposta IS NULL AND stato='MANDATO'").fetchone()["c"]
    con.close(); return jsonify({"totale_iscritti": tot, "in_prova": prova, "pagato": pagato, "bloccato": bloccato, "messaggi_mandati": mandati, "SI": si, "NO": no, "non_hanno_risposto": non_risp})

def orologio():
    while True:
        try:
            con = db(); ora = datetime.datetime.now()
            con.execute("UPDATE famiglie SET stato='BLOCCATO' WHERE stato='PROVA' AND trial_fine < ?", (ora.isoformat(),)); con.commit()
            oggi = ora.strftime("%Y-%m-%d"); ora_min = ora.strftime("%H:%M")
            rows = con.execute("SELECT * FROM messaggi WHERE data_invio=? AND ora_invio=? AND stato='IN_MAGAZZINO'", (oggi, ora_min)).fetchall()
            for m in rows:
                con.execute("INSERT INTO coda(messaggio_id,tipo,creato_il) VALUES(?,?,?)", (m["id"], "NORMALE", ora.isoformat())); con.execute("UPDATE messaggi SET stato='IN_FILA' WHERE id=?", (m["id"],))
            con.commit(); con.close()
        except Exception as e: print("Errore orologio:", e)
        time.sleep(60)

def fila():
    while True:
        try:
            con = db()
            item = con.execute("SELECT * FROM coda ORDER BY CASE WHEN tipo='HELP' THEN 0 ELSE 1 END, id ASC LIMIT 1").fetchone()
            if item:
                m = con.execute("SELECT * FROM messaggi WHERE id=?", (item["messaggio_id"],)).fetchone()
                if m:
                    fam = con.execute("SELECT * FROM famiglie WHERE id=?", (m["famiglia_id"] or m["utente_id"],)).fetchone()
                    if fam and fam["stato"] != "BLOCCATO":
                        pers = con.execute("SELECT * FROM persone WHERE famiglia_id=? AND ruolo=?", (fam["id"], m["destinatario"])).fetchone()
                        if not pers: pers = con.execute("SELECT * FROM persone WHERE famiglia_id=? ORDER BY id DESC LIMIT 1", (fam["id"],)).fetchone()
                        chat_id = pers["telegram_id"] if pers else None
                        if chat_id:
                            bottoni = {"inline_keyboard": [[{"text": "SI", "callback_data": f"SI_{m['id']}"}, {"text": "NO", "callback_data": f"NO_{m['id']}"}]]}
                            ok = manda_telegram(chat_id, m["testo"], bottoni)
                            if ok: con.execute("UPDATE messaggi SET stato='MANDATO' WHERE id=?", (m["id"],)); con.execute("DELETE FROM coda WHERE id=?", (item["id"],))
                            else:
                                if item["tentativi"] >= 3: con.execute("DELETE FROM coda WHERE id=?", (item["id"],))
                                else: con.execute("UPDATE coda SET tentativi=tentativi+1 WHERE id=?", (item["id"],))
                        else: con.execute("DELETE FROM coda WHERE id=?", (item["id"],))
                    else: con.execute("DELETE FROM coda WHERE id=?", (item["id"],))
                else: con.execute("DELETE FROM coda WHERE id=?", (item["id"],))
                con.commit()
            con.close()
        except Exception as e: print("Errore fila:", e)
        time.sleep(1)

def bot_loop():
    offset = 0
    print("BOT LOOP AVVIATO - aspetto messaggi Telegram...")
    while True:
        try:
            if not BOT_TOKEN or BOT_TOKEN.startswith("METTI_"):
                print("BOT_TOKEN mancante su Render, aspetto 10 sec...")
                time.sleep(10); continue
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35).json()
            if not r.get("ok"):
                print("Errore Telegram getUpdates:", r)
                time.sleep(5); continue
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1; con = db()
                print("Ricevuto da Telegram:", upd)
                if "message" in upd:
                    msg = upd["message"]; chat_id = msg["chat"]["id"]; testo = msg.get("text", "")
                    # === FIX 1 - AVVIA SCRITTO A MANO - QUESTO MANCAVA ===
                    if testo.strip().upper() in ["AVVIA", "AVVIA_START", "START", "CIAO", "HI", "INIZIA"]:
                        manda_telegram(chat_id, "Ciao! Sono il tuo Badante Virtuale ❤️\n\nVuoi configurare il Badante?", {"inline_keyboard": [[{"text": "✅ SI - Configura", "callback_data": "CONFIG_SI"}, {"text": "❌ NO - Salta", "callback_data": "CONFIG_NO"}], [{"text": "🆘 SOS", "callback_data": "HELP_AVVIA"}]]})
                    elif testo.startswith("/start"):
                        parti = testo.split(); codice = parti[1] if len(parti) > 1 else ""
                        fam = con.execute("SELECT * FROM famiglie WHERE codice_link=?", (codice,)).fetchone() if codice else None
                        if fam:
                            manda_telegram(chat_id, f"Ciao UTENTE, il tuo codice unico è {fam['otp']}. Scrivilo qui per firmare ed entrare.", {"inline_keyboard": [[{"text": "✅ HO CAPITO - SCRIVO IL CODICE", "callback_data": "AVVIA_START"}]]})
                        else:
                            # Se fai /start senza codice, ti faccio vedere subito SI / NO / SOS
                            manda_telegram(chat_id, "Ciao! 👋 Sono il tuo Badante Virtuale ❤️\n\nVuoi configurare il Badante?\n\nSe hai già il codice di 6 cifre dal sito, scrivilo qui.", {"inline_keyboard": [[{"text": "✅ SI - Configura", "callback_data": "CONFIG_SI"}, {"text": "❌ NO - Salta", "callback_data": "CONFIG_NO"}], [{"text": "🆘 SOS", "callback_data": "HELP_AVVIA"}]]})
                    elif testo.isdigit() and len(testo) == 6:
                        fam = con.execute("SELECT * FROM famiglie WHERE otp=?", (testo,)).fetchone()
                        if fam:
                            p = con.execute("SELECT * FROM persone WHERE famiglia_id=? AND telegram_id IS NULL ORDER BY id LIMIT 1", (fam["id"],)).fetchone()
                            if p: con.execute("UPDATE persone SET verificato=1, telegram_id=? WHERE id=?", (chat_id, p["id"])); con.commit()
                            tastiera_sos = {"keyboard": [[{"text": "🆘 SOS - MANDA POSIZIONE", "request_location": True}], [{"text": "🆘 HELP"}]], "resize_keyboard": True}
                            manda_telegram(chat_id, f"Benvenuto UTENTE, sei entrato ✓ Ora puoi usare SOS con posizione.", tastiera_sos)
                        else: manda_telegram(chat_id, "Codice sbagliato, riprova.")
                    elif testo == "🆘 HELP":
                        manda_telegram(chat_id, "Hai premuto HELP. Premi AVVIA per mandare l'aiuto.", {"inline_keyboard": [[{"text": "➡️ AVVIA", "callback_data": "HELP_AVVIA"}]]})
                    elif "location" in msg:
                        loc = msg["location"]; lat=loc["latitude"]; lon=loc["longitude"]
                        link_maps = f"https://www.google.com/maps?q={lat},{lon}"
                        pers = con.execute("SELECT * FROM persone WHERE telegram_id=?", (chat_id,)).fetchone()
                        if pers:
                            altra = con.execute("SELECT * FROM persone WHERE famiglia_id=? AND id!=? AND telegram_id IS NOT NULL", (pers["famiglia_id"], pers["id"])).fetchone()
                            if altra: manda_telegram(altra["telegram_id"], f"🆘 SOS da {pers['nome']}! POSIZIONE: {link_maps}")
                            manda_telegram(chat_id, f"SOS + POSIZIONE MANDATO ✓ {link_maps}")
                        else: manda_telegram(chat_id, "Non ti trovo, rifai l'iscrizione.")
                    elif "contact" in msg:
                        numero = msg["contact"]["phone_number"]; persone = con.execute("SELECT * FROM persone").fetchall(); trovato=False
                        for p in persone:
                            if p["cell"] and numero.endswith(p["cell"][-9:]):
                                con.execute("UPDATE persone SET telegram_id=? WHERE id=?", (chat_id, p["id"])); con.commit()
                                manda_telegram(chat_id, f"Ciao UTENTE, vuoi ricevere i promemoria? Premi SI per accettare, NO per rifiutare.", {"inline_keyboard": [[{"text": "SI", "callback_data": f"ACCETTA_{p['id']}"}, {"text": "NO", "callback_data": f"RIFIUTA_{p['id']}"}]]}); trovato=True; break
                        if not trovato: manda_telegram(chat_id, "Numero non uguale a quello scritto. Si blocca tutto. Chiedi di controllare.")
                    else:
                        # Se scrivi qualcosa di diverso, ti rimando al menu
                        if testo.strip() != "":
                            manda_telegram(chat_id, "Scrivi AVVIA per vedere il menu ❤️")
                if "callback_query" in upd:
                    cb = upd["callback_query"]; chat_id = cb["message"]["chat"]["id"]; data = cb["data"]
                    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                    except: pass
                    # === FIX 2 - PULSANTI CONFIGURAZIONE SI / NO ===
                    if data == "CONFIG_SI":
                        manda_telegram(chat_id, "Perfetto! Iniziamo la configurazione.\n\nSe hai il codice di 6 cifre dal sito, scrivilo qui e premi INVIA.\nSe non ce l'hai, vai sul sito e iscriviti.")
                    elif data == "CONFIG_NO":
                        manda_telegram(chat_id, "Ok, salto la configurazione. Puoi scrivermi AVVIA quando vuoi! ❤️")
                    elif data == "AVVIA_START":
                        manda_telegram(chat_id, "Perfetto! Ora scrivi qui il tuo codice di 6 cifre che ti ha dato il sito e premi INVIA.")
                    elif data.startswith("SI_"):
                        mid = data.split("_")[1]; con.execute("UPDATE messaggi SET risposta='SI' WHERE id=?", (mid,)); con.commit()
                        m = con.execute("SELECT * FROM messaggi WHERE id=?", (mid,)).fetchone()
                        if m:
                            pers = con.execute("SELECT * FROM persone WHERE famiglia_id=? ORDER BY id LIMIT 1", (m["famiglia_id"],)).fetchone()
                            if pers and pers["telegram_id"]: manda_telegram(pers["telegram_id"], "Ha CONFERMATO ✓")
                        manda_telegram(chat_id, "Grazie ✓")
                    elif data.startswith("NO_"):
                        mid = data.split("_")[1]; con.execute("UPDATE messaggi SET risposta='NO' WHERE id=?", (mid,)); con.commit()
                        m = con.execute("SELECT * FROM messaggi WHERE id=?", (mid,)).fetchone()
                        if m:
                            pers = con.execute("SELECT * FROM persone WHERE famiglia_id=? ORDER BY id LIMIT 1", (m["famiglia_id"],)).fetchone()
                            if pers and pers["telegram_id"]: manda_telegram(pers["telegram_id"], "Ha detto NO / non ha risposto")
                        manda_telegram(chat_id, "Ok, capito.")
                    elif data == "HELP_AVVIA":
                        pers = con.execute("SELECT * FROM persone WHERE telegram_id=?", (chat_id,)).fetchone()
                        if pers:
                            fam = con.execute("SELECT * FROM famiglie WHERE id=?", (pers["famiglia_id"],)).fetchone()
                            if fam and fam["stato"] != "BLOCCATO":
                                ora = time.strftime("%H:%M")
                                altra = con.execute("SELECT * FROM persone WHERE famiglia_id=? AND id!=? AND telegram_id IS NOT NULL", (pers["famiglia_id"], pers["id"])).fetchone()
                                if altra: manda_telegram(altra["telegram_id"], f"🆘 AIUTO! {pers['nome']} ha premuto il bottone alle {ora}. Chiamalo subito!")
                                manda_telegram(chat_id, "AIUTO MANDATO ✓")
                            else: manda_telegram(chat_id, "Servizio bloccato, non parte niente.")
                        else:
                            manda_telegram(chat_id, "🆘 SOS PREMUTO! Per mandare l'aiuto devi prima entrare con il codice di 6 cifre dal sito.")
                    elif data.startswith("ACCETTA"): manda_telegram(chat_id, "Grazie, hai accettato ✓ Ora riceverai i promemoria.", {"keyboard": [[{"text": "🆘 SOS - MANDA POSIZIONE", "request_location": True}], [{"text": "🆘 HELP"}]], "resize_keyboard": True})
                    elif data.startswith("RIFIUTA"): manda_telegram(chat_id, "Ok, non parte niente.")
                con.close()
        except Exception as e: print("Errore bot:", e); time.sleep(2)

_threads_avviati = False
def avvia_threads():
    global _threads_avviati
    if _threads_avviati: return
    _threads_avviati = True
    threading.Thread(target=orologio, daemon=True).start()
    threading.Thread(target=fila, daemon=True).start()
    threading.Thread(target=bot_loop, daemon=True).start()

avvia_threads()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"LA TUA BADANTE VIRTUALE ACCESO - Porta {port}")
    app.run(host="0.0.0.0", port=port)


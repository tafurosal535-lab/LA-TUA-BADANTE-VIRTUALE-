import os, random, string, sqlite3
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
import math
import requests

app = Flask(__name__)
DB = "badante.db"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS famiglie (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        otp TEXT,
        codice_link TEXT,
        telegram_id TEXT,
        data_iscrizione TEXT,
        trial_fine TEXT,
        abbonato INTEGER DEFAULT 0,
        tipo_abbonamento TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS utenti (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        famiglia_id INTEGER,
        ruolo TEXT,
        nome TEXT,
        cognome TEXT,
        email TEXT,
        cellulare TEXT,
        privacy INTEGER DEFAULT 0
    )""")
    try: c.execute("ALTER TABLE famiglie ADD COLUMN data_iscrizione TEXT")
    except: pass
    try: c.execute("ALTER TABLE famiglie ADD COLUMN trial_fine TEXT")
    except: pass
    try: c.execute("ALTER TABLE famiglie ADD COLUMN abbonato INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE famiglie ADD COLUMN tipo_abbonamento TEXT")
    except: pass
    c.commit(); c.close()
init_db()

def gen_codice(n=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

HTML = """
<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Iscrizione Badante</title>
<style>
body{font-family:Arial;padding:16px;background:#f2f2f2}
.box{background:white;padding:18px;border-radius:14px;max-width:480px;margin:auto}
input{width:100%;padding:12px;margin:6px 0;border:1px solid #ccc;border-radius:8px;font-size:16px;box-sizing:border-box}
button{width:100%;padding:13px;margin:6px 0;border:0;border-radius:10px;font-size:16px;cursor:pointer}
.btn-blue{background:#007bff;color:white}
.btn-grey{background:#6c757d;color:white}
.btn-red{background:#dc3545;color:white}
.btn-green{background:#28a745;color:white}
.btn-orange{background:#fd7e14;color:white}
.btn-gold{background:#FFD700;color:#000;font-weight:bold;font-size:20px;padding:18px}
label{font-size:14px}
.success{background:#d4edda;color:#155724;padding:12px;border-radius:10px;text-align:center;font-weight:bold}
.blocco{background:#f8d7da;color:#721c24;padding:14px;border-radius:10px;text-align:center;font-weight:bold}
.trial{background:#fff3cd;color:#856404;padding:12px;border-radius:10px;text-align:center;font-weight:bold}
.premio{background:#fff8dc;padding:20px;border:3px solid #FFD700;border-radius:14px;text-align:center}
.premio-verde{background:#eaf7ee;padding:20px;border:3px solid #28a745;border-radius:14px;text-align:center}
.hidden{display:none}
.row{display:flex;gap:8px}
.row button{flex:1}
</style></head>
<body>
<div class='box'>

<div id='trialBox' class='hidden trial'></div>

<div id='sezioneIscrizione'>
<h2 id='titolo'>ISCRIZIONE - UTENTE 1</h2>
<div id='formIscrizione'>
<input id='nome' placeholder='Nome'>
<input id='cognome' placeholder='Cognome'>
<input id='email' placeholder='Email' type='email'>
<input id='cellulare' placeholder='Numero Cellulare' type='tel'>
<label><input type='checkbox' id='privacy'> Ho letto e accetto la Privacy</label>
<div class='row'>
<button class='btn-grey' onclick='indietro()'>⬅️ INDIETRO</button>
<button class='btn-blue' id='btnAvanti' onclick='avanti()'>SALVA UTENTE 1 - AVANTI ➡️</button>
</div>
<div id='msg'></div>
</div>

<div id='fatto' class='hidden'>
<div class='success'>✅✅ FATTO - ISCRIZIONE COMPLETA<br>Ora fate Condividi Numero su Telegram</div>
<div id='datiTelegram'></div>
</div>

<div id='cancellato' class='hidden'>
<div class='success'>✅✅ CANCELLAZIONE AVVENUTA CON SUCCESSO<br>Puoi iscriverti di nuovo da zero</div>
</div>

<hr>
<button class='btn-orange' onclick='mostraCambia()'>📱 CAMBIA NUMERO</button>
<button class='btn-red' onclick='mostraCancella()'>🗑️ CANCELLA I MIEI DATI</button>

<div id='boxCambia' class='hidden'>
<h3>CAMBIA NUMERO</h3>
<input id='vecchioNumero' placeholder='Numero Cellulare VECCHIO con cui ti sei registrato' type='tel'>
<input id='nuovoNumero' placeholder='Numero Cellulare NUOVO' type='tel'>
<button class='btn-orange' onclick='cambiaNumero()'>CAMBIA NUMERO</button>
<div id='msgCambia'></div>
</div>

<div id='boxCancella' class='hidden'>
<h3>CANCELLA I MIEI DATI</h3>
<input id='emailCancella' placeholder='La tua Email con cui ti sei iscritto' type='email'>
<input id='cellCancella' placeholder='Numero Cellulare VECCHIO con cui ti sei registrato' type='tel'>
<button class='btn-red' onclick='cancellaDati()'>CONFERMA CANCELLAZIONE</button>
<div id='msgCancella'></div>
</div>
</div>

<div id='sezioneAbbonamento' class='hidden'>
<div class='blocco'>⏰ PROVA GRATIS FINITA<br>Sei stato BLOCCATO</div>
<br>
<div class='premio'>
<h2>2 CONTATTI A SOLI € 6,50 AL MESE</h2>
<p>Per continuare ad usare la Badante<br>ogni mese</p>
<button class='btn-gold' onclick="abbonati('MESE')">ABBONATI - € 6,50 AL MESE</button>
<p style='font-size:13px'>2 contatti - Pagamento sicuro</p>
</div>
<br>
<div class='premio-verde'>
<h2>2 CONTATTI PER 12 MESI A SOLI € 60,00</h2>
<p>Risparmi tanto<br>Un anno intero</p>
<button class='btn-green' onclick="abbonati('ANNO')" style='font-size:20px;padding:18px'>ABBONATI - € 60,00 PER 12 MESI</button>
<p style='font-size:13px'>2 contatti per 12 mesi - Pagamento sicuro</p>
</div>
</div>

</div>
<script>
let step = 1;
let datiUtente1 = null;
let famiglia_id = localStorage.getItem('famiglia_id') || null;

// CORRETTO: se riapre la pagina, controlla subito se è bloccato
if(famiglia_id){
  // Aspetta che la pagina carichi e controlla
  window.addEventListener('load', ()=>{ controllaStato(); });
}

function indietro(){
  if(step === 2){
    step = 1;
    document.getElementById('titolo').innerText = 'ISCRIZIONE - UTENTE 1';
    document.getElementById('btnAvanti').innerText = 'SALVA UTENTE 1 - AVANTI ➡️';
    document.getElementById('nome').value = datiUtente1.nome;
    document.getElementById('cognome').value = datiUtente1.cognome;
    document.getElementById('email').value = datiUtente1.email;
    document.getElementById('cellulare').value = datiUtente1.cellulare;
    document.getElementById('privacy').checked = datiUtente1.privacy;
    document.getElementById('msg').innerHTML = 'Puoi correggere Nome, Cognome, Email e Numero';
  } else {
    datiUtente1 = null;
    document.getElementById('nome').value='';
    document.getElementById('cognome').value='';
    document.getElementById('email').value='';
    document.getElementById('cellulare').value='';
    document.getElementById('privacy').checked=false;
    document.getElementById('msg').innerHTML = 'Ricomincia da zero';
  }
}

async function avanti(){
  let nome = document.getElementById('nome').value.trim();
  let cognome = document.getElementById('cognome').value.trim();
  let email = document.getElementById('email').value.trim();
  let cellulare = document.getElementById('cellulare').value.trim();
  let privacy = document.getElementById('privacy').checked;
  if(!nome || !cognome || !email || !cellulare){ document.getElementById('msg').innerHTML='Compila tutti i campi'; return; }
  if(!privacy){ document.getElementById('msg').innerHTML='Devi accettare la Privacy'; return; }
  if(step === 1){
    datiUtente1 = {nome, cognome, email, cellulare, privacy:true, ruolo:'UTENTE 1'};
    step = 2;
    document.getElementById('titolo').innerText = 'ISCRIZIONE - UTENTE 2';
    document.getElementById('btnAvanti').innerText = 'SALVA UTENTE 2 - FINE ✅';
    document.getElementById('nome').value=''; document.getElementById('cognome').value=''; document.getElementById('email').value=''; document.getElementById('cellulare').value=''; document.getElementById('privacy').checked=false;
    document.getElementById('msg').innerHTML='Ora inserisci UTENTE 2. Se hai sbagliato UTENTE 1, premi INDIETRO.';
  } else {
    let datiUtente2 = {nome, cognome, email, cellulare, privacy:true, ruolo:'UTENTE 2'};
    let r = await fetch('/iscrivi_coppia', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({utente1: datiUtente1, utente2: datiUtente2})});
    let j = await r.json();
    if(j.ok){
      famiglia_id = j.famiglia_id;
      localStorage.setItem('famiglia_id', famiglia_id);
      document.getElementById('formIscrizione').classList.add('hidden');
      document.getElementById('fatto').classList.remove('hidden');
      document.getElementById('datiTelegram').innerHTML = '<br><b>Codice Link Telegram:</b> ' + j.codice_link + '<br><b>OTP:</b> ' + j.otp + '<br><br>Apri Telegram e premi Condividi Numero';
      controllaStato();
    } else { document.getElementById('msg').innerHTML = j.errore; }
  }
}

function mostraCambia(){ document.getElementById('boxCambia').classList.remove('hidden'); document.getElementById('boxCancella').classList.add('hidden'); }
function mostraCancella(){ document.getElementById('boxCancella').classList.remove('hidden'); document.getElementById('boxCambia').classList.add('hidden'); }

async function cambiaNumero(){
  let vecchio = document.getElementById('vecchioNumero').value.trim();
  let nuovo = document.getElementById('nuovoNumero').value.trim();
  if(!vecchio || !nuovo){ document.getElementById('msgCambia').innerHTML='Metti vecchio e nuovo numero'; return; }
  let r = await fetch('/cambia_numero', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({vecchio, nuovo})});
  let j = await r.json();
  document.getElementById('msgCambia').innerHTML = j.ok ? '✅✅ NUMERO CAMBIATO<br>Nuovo codice Telegram: <b>' + j.codice_link + '</b><br>Nuovo OTP: <b>' + j.otp + '</b><br>Rifai Condividi Numero su Telegram con il numero nuovo.' : j.errore;
}

async function cancellaDati(){
  let email = document.getElementById('emailCancella').value.trim();
  let cellulare = document.getElementById('cellCancella').value.trim();
  if(!email || !cellulare){ document.getElementById('msgCancella').innerHTML='Metti Email + Numero Vecchio'; return; }
  let r = await fetch('/cancella_dati', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email, cellulare})});
  let j = await r.json();
  if(j.ok){
    // CORRETTO: nascondi solo form e box, lascia visibile il messaggio CANCELLAZIONE
    localStorage.removeItem('famiglia_id');
    document.getElementById('boxCancella').classList.add('hidden');
    document.getElementById('boxCambia').classList.add('hidden');
    document.getElementById('formIscrizione').classList.add('hidden');
    document.getElementById('fatto').classList.add('hidden');
    document.getElementById('trialBox').classList.add('hidden');
    document.getElementById('cancellato').classList.remove('hidden');
    setTimeout(()=>{
      document.getElementById('cancellato').classList.add('hidden');
      document.getElementById('formIscrizione').classList.remove('hidden');
      step=1; datiUtente1=null; famiglia_id=null;
      document.getElementById('titolo').innerText='ISCRIZIONE - UTENTE 1';
      document.getElementById('btnAvanti').innerText='SALVA UTENTE 1 - AVANTI ➡️';
      document.getElementById('nome').value=''; document.getElementById('cognome').value=''; document.getElementById('email').value=''; document.getElementById('cellulare').value=''; document.getElementById('privacy').checked=false;
    }, 3000);
  } else { document.getElementById('msgCancella').innerHTML = j.errore; }
}

async function controllaStato(){
  if(!famiglia_id) return;
  let r = await fetch('/stato/' + famiglia_id);
  let j = await r.json();
  if(j.bloccato){
    document.getElementById('sezioneIscrizione').classList.add('hidden');
    document.getElementById('sezioneAbbonamento').classList.remove('hidden');
    document.getElementById('trialBox').classList.add('hidden');
  } else {
    document.getElementById('sezioneAbbonamento').classList.add('hidden');
    if(j.abbonato){
      document.getElementById('trialBox').classList.remove('hidden');
      document.getElementById('trialBox').innerHTML = '✅ ABBONAMENTO ATTIVO - Grazie!';
    } else if(j.giorni_rimasti !== null && j.giorni_rimasti !== undefined){
      document.getElementById('trialBox').classList.remove('hidden');
      document.getElementById('trialBox').innerHTML = '🎁 PROVA GRATIS 7 GIORNI - Ti restano ' + j.giorni_rimasti + ' giorni';
    }
  }
}

async function abbonati(tipo){
  let r = await fetch('/abbonati', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({famiglia_id: famiglia_id, tipo: tipo})});
  let j = await r.json();
  if(j.ok){
    if(tipo === 'MESE'){
      alert('✅✅ ABBONAMENTO ATTIVATO - 2 CONTATTI A € 6,50 AL MESE - Grazie!');
    } else {
      alert('✅✅ ABBONAMENTO ATTIVATO - 2 CONTATTI PER 12 MESI A € 60,00 - Grazie!');
    }
    controllaStato();
    document.getElementById('sezioneIscrizione').classList.remove('hidden');
    document.getElementById('sezioneAbbonamento').classList.add('hidden');
  }
}
</script></body></html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/iscrivi_coppia", methods=["POST"])
def iscrivi_coppia():
    d = request.get_json()
    u1 = d.get("utente1"); u2 = d.get("utente2")
    if not u1 or not u2:
        return jsonify({"ok": False, "errore": "Servono UTENTE 1 e UTENTE 2"})
    for u in [u1, u2]:
        if not u.get("nome") or not u.get("cognome") or not u.get("email") or not u.get("cellulare") or not u.get("privacy"):
            return jsonify({"ok": False, "errore": "Compila tutto e accetta Privacy per entrambi"})
    c = db()
    for u in [u1, u2]:
        ex = c.execute("SELECT id FROM utenti WHERE cellulare=? OR email=?", (u["cellulare"], u["email"])).fetchone()
        if ex:
            c.close(); return jsonify({"ok": False, "errore": "Numero o Email già registrati: " + u["cellulare"]})
    otp = gen_codice(6); codice = gen_codice(6)
    ora = datetime.now()
    trial_fine = ora + timedelta(days=7)
    cur = c.execute("INSERT INTO famiglie (otp, codice_link, data_iscrizione, trial_fine, abbonato) VALUES (?,?,?,?,0)",
                    (otp, codice, ora.isoformat(), trial_fine.isoformat()))
    fid = cur.lastrowid
    for u in [u1, u2]:
        c.execute("INSERT INTO utenti (famiglia_id, ruolo, nome, cognome, email, cellulare, privacy) VALUES (?,?,?,?,?,?,1)",
                  (fid, u["ruolo"], u["nome"], u["cognome"], u["email"], u["cellulare"]))
    c.commit(); c.close()
    return jsonify({"ok": True, "famiglia_id": fid, "otp": otp, "codice_link": codice})

@app.route("/stato/<int:fid>")
def stato(fid):
    c = db()
    f = c.execute("SELECT * FROM famiglie WHERE id=?", (fid,)).fetchone()
    c.close()
    if not f:
        return jsonify({"bloccato": True, "giorni_rimasti": 0})
    if f["abbonato"] == 1:
        return jsonify({"bloccato": False, "giorni_rimasti": None, "abbonato": True})
    try:
        fine = datetime.fromisoformat(f["trial_fine"])
        ora = datetime.now()
        # CORRETTO: arrotonda per eccesso, così il primo giorno dice 7 e non 6
        secondi = (fine - ora).total_seconds()
        if secondi <= 0:
            return jsonify({"bloccato": True, "giorni_rimasti": 0})
        giorni = math.ceil(secondi / 86400)
        if giorni > 7: giorni = 7
        return jsonify({"bloccato": False, "giorni_rimasti": giorni})
    except:
        return jsonify({"bloccato": False, "giorni_rimasti": 7})

@app.route("/abbonati", methods=["POST"])
def abbonati():
    d = request.get_json()
    fid = d.get("famiglia_id")
    tipo = d.get("tipo", "MESE")
    if not fid:
        return jsonify({"ok": False, "errore": "Manca famiglia"})
    c = db()
    c.execute("UPDATE famiglie SET abbonato=1, tipo_abbonamento=? WHERE id=?", (tipo, fid))
    c.commit(); c.close()
    return jsonify({"ok": True, "tipo": tipo})

@app.route("/cambia_numero", methods=["POST"])
def cambia_numero():
    d = request.get_json()
    vecchio = (d.get("vecchio") or "").strip(); nuovo = (d.get("nuovo") or "").strip()
    if not vecchio or not nuovo:
        return jsonify({"ok": False, "errore": "Metti vecchio e nuovo numero"})
    c = db()
    u = c.execute("SELECT * FROM utenti WHERE cellulare=?", (vecchio,)).fetchone()
    if not u:
        c.close(); return jsonify({"ok": False, "errore": "Numero vecchio non trovato. Metti il numero con cui ti sei registrato."})
    ex = c.execute("SELECT id FROM utenti WHERE cellulare=?", (nuovo,)).fetchone()
    if ex:
        c.close(); return jsonify({"ok": False, "errore": "Nuovo numero già usato"})
    c.execute("UPDATE utenti SET cellulare=? WHERE id=?", (nuovo, u["id"]))
    otp = gen_codice(6); codice = gen_codice(6)
    c.execute("UPDATE famiglie SET otp=?, codice_link=?, telegram_id=NULL WHERE id=?", (otp, codice, u["famiglia_id"]))
    c.commit(); c.close()
    return jsonify({"ok": True, "otp": otp, "codice_link": codice})

@app.route("/cancella_dati", methods=["POST"])
def cancella_dati():
    d = request.get_json()
    email = (d.get("email") or "").strip(); cellulare = (d.get("cellulare") or "").strip()
    if not email or not cellulare:
        return jsonify({"ok": False, "errore": "Metti Email + Numero Vecchio"})
    c = db()
    u = c.execute("SELECT * FROM utenti WHERE email=? AND cellulare=?", (email, cellulare)).fetchone()
    if not u:
        c.close(); return jsonify({"ok": False, "errore": "Email o Numero Vecchio sbagliati. Controlla e riprova."})
    fid = u["famiglia_id"]
    c.execute("DELETE FROM utenti WHERE famiglia_id=?", (fid,))
    c.execute("DELETE FROM famiglie WHERE id=?", (fid,))
    c.commit(); c.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
                

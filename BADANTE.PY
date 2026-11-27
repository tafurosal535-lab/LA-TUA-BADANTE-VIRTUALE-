# BADANTE_V4.PY - COMPLETO 100% - FINITO
# Start Command: python BADANTE_V4.PY

import os, sqlite3, secrets, threading, time, datetime, json, requests, smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, render_template_string
 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "METTI_QUI_IL_TOKEN_DEL_BOT")
BOT_NAME = "BadanteVirtualeBot"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "METTI_PASSWORD_SEGRETA")
MIA_EMAIL = "latuabadantevirtuale@libero.it"
EMAIL_USER = os.environ.get("EMAIL_USER", "latuabadantevirtuale@libero.it")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "latuabadantevirtuale@libero.it")

app = Flask(__name__)

def manda_email_a(destinatario, oggetto, testo):
    if not EMAIL_USER or not EMAIL_PASS or not destinatario:
        print("MAIL NON MANDATA - manca EMAIL_USER / EMAIL_PASS")
        return False
    try:
        msg = MIMEText(testo)
        msg["Subject"] = oggetto
        msg["From"] = EMAIL_USER
        msg["To"] = destinatario
        server = smtplib.SMTP_SSL("smtp.libero.it", 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("MAIL MANDATA a:", destinatario)
        return True
    except Exception as e:
        print("Errore manda email:", e)
        return False

def db():
    path = os.environ.get("DATABASE_PATH", "database.db")
    cartella = os.path.dirname(path)
    if cartella:
        os.makedirs(cartella, exist_ok=True)
    c = sqlite3.connect(path, check_same_thread=False)
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
<style>body{font-family:Arial;text-align:center}h1{font-size:22px}.finestra{border:2px solid #333;display:inline-block;width:340px;margin:10px;padding:15px;vertical-align:top}input,select{width:92%;padding:10px;margin:5px;font-size:16px}button{padding:12px 20px;font-size:16px;margin:5px;cursor:pointer}.verde{color:green}.rosso{color:red}.bloccato{opacity:0.5;pointer-events:none}.boxmsg{border:2px solid #333;display:inline-block;width:340px;margin:5px;padding:10px;vertical-align:top}</style></head><body>
<h1>LA TUA BADANTE VIRTUALE è un servizio di promemoria. NON sostituiamo il medico.</h1>
<div id="stato">SBLOCCATO</div>
<div class="finestra" style="border-color:blue;background:#eef6ff"><h2 style="color:blue">SEI GIA' ISCRITTO? TORNI DOPO UN MESE?</h2>
<p><b>Prima volta?</b> Vai a destra in UTENTE - PRIMA VOLTA.<br><b>Già iscritto?</b> Entra da qui sotto.</p>
<p>Metti il tuo numero + il tuo OTP di 6 cifre che ti abbiamo mandato per mail.</p>
<input id="loginCell" placeholder="Tuo numero Cell">
<input id="loginOtp" placeholder="Il tuo OTP di 6 cifre">
<button onclick="accedi()" style="background:blue;color:white">ACCEDI - SONO IO</button>
<div id="rLogin"></div>
<div id="bentornato" style="display:none;color:green;font-weight:bold"></div>
<hr>
<p><b>HAI DIMENTICATO L'OTP? TE LO RIMANDIAMO PER MAIL:</b></p>
<button onclick="apri('boxRecupera')" style="background:orange">HAI DIMENTICATO L'OTP? RECUPERA</button>
<div id="boxRecupera" style="display:none">
<input id="recCell" placeholder="Tuo numero Cell">
<input id="recNome" placeholder="Nome che hai usato per iscriverti">
<input id="recCognome" placeholder="Cognome che hai usato per iscriverti">
<input id="recEmail" placeholder="Email che hai usato per iscriverti">
<button onclick="recuperaOtp()" style="background:orange">MANDAMI OTP PER MAIL</button>
<div id="rRecupera"></div>
</div>
<br><button onclick="esci()" style="font-size:12px">ESCI - DIMENTICAMI SU QUESTO TELEFONO</button>
</div>
<div class="finestra" id="boxIscrizione"><h2>UTENTE - PRIMA VOLTA</h2>
<p><b>SOLO LA PRIMA VOLTA. Se sei già iscritto vai a sinistra in ACCEDI.</b></p>
<p>Utente <span id="numPersona">1</span> di 2</p>
<input id="nome" placeholder="Nome"><input id="cognome" placeholder="Cognome"><input id="email" placeholder="Email"><input id="cell" placeholder="Numero Cell"><br>
<div id="boxPrivacy" style="display:none"><label><input type="checkbox" id="priv1"> Ho letto l'informativa privacy. Autorizzo a mandare messaggi per ricordarmi medicine e appuntamenti. Posso togliere l'autorizzazione quando voglio.</label><br></div>
<button id="btnSalva" onclick="salvaPersona()">SALVA UTENTE</button>
<button onclick="nuovaIscrizione()" style="background:#ffcc00">NUOVA ISCRIZIONE - ALTRA FAMIGLIA</button>
<div id="r1"></div><div id="linkbox"></div>
<div id="spuntaVerde" style="display:none;font-size:30px;color:green">✅ FATTO - ISCRIZIONE FATTA - CONTROLLA LA MAIL</div>
</div>
<br><button onclick="apri('fcont')">CONTATTI</button>
<div id="fcont" style="display:none"><textarea id="msgCont" style="width:80%;height:100px" placeholder="Scrivi qui - Se vuoi cancellare i tuoi dati scrivi CANCELLAMI"></textarea><br><button onclick="inviaContatto()">INVIO</button><div id="rc"></div></div>
<div style="margin-top:15px"><h2>Scrivi Messaggio</h2>
<div id="chiSono" style="font-weight:bold;color:green"></div>
<div class="boxmsg"><p>1 - SCRIVI MESSAGGIO</p><input id="testo" placeholder="Es: Hai preso la medicina delle 9?"></div>
<div class="boxmsg"><p>2 - SCEGLI GIORNO E ORA - CALENDARIO</p><input id="dataora" type="datetime-local"><br><small>Puoi mandare tra 1 minuto o tra 3 mesi</small></div>
<div class="boxmsg"><p>3 - A CHI VA?</p><select id="dest"><option>UTENTE 2</option><option>UTENTE 1</option></select></div>
<div class="boxmsg"><p>4 - INVIA</p><button onclick="salvaMessaggio()">INVIA</button><div id="rm"></div></div>
<div id="lista"></div></div>
<div><h2>🆘 SOS + POSIZIONE</h2><p>Premi SOS e manda la tua posizione all'altro utente.</p><button onclick="mandaSOS()" style="background:red;color:white;font-size:20px;padding:15px 30px">🆘 SOS - MANDA POSIZIONE</button><div id="rSOS"></div></div>
<div class="finestra" id="boxCambioNumero"><h2>CAMBIA NUMERO</h2><input id="nomeCambio" placeholder="Nome"><input id="cognomeCambio" placeholder="Cognome"><input id="emailCambio" placeholder="Email"><input id="vecchioNum" placeholder="Cellulare Vecchio"><input id="nuovoNum" placeholder="Cellulare Nuovo"><button id="btnCambia" onclick="cambiaNumero()">CAMBIA NUMERO</button><div id="rCambio"></div><div id="spuntaCambio" style="display:none;font-size:30px;color:green">✅ FATTO</div></div>
<div><h2>SBLOCCA - PAGA ORA</h2><button onclick="paga('1 MESE')">1 MESE - 9,90 euro</button><button onclick="paga('3 MESI')">3 MESI - 24,90 euro</button><button onclick="paga('12 MESI')">12 MESI - 89,90 euro</button><p>Paga con Carta o PayPal</p></div>
<script>
let FAMIGLIA_ID=null;
let FASE=1;
function apri(id){let e=document.getElementById(id); e.style.display=e.style.display=='none'?'block':'none';}
function aggiornaChiSono(){
  if(FAMIGLIA_ID){ document.getElementById('chiSono').innerText='Stai scrivendo come: Famiglia '+FAMIGLIA_ID+' - Se non sei tu, premi ESCI sopra e fai ACCEDI con il tuo numero.'; }
}
function salvaInTelefono(famiglia_id, otp){
  try{ localStorage.setItem('mia_famiglia', famiglia_id); if(otp) localStorage.setItem('mio_otp', otp); }catch(e){}
}
function esci(){
  try{ localStorage.removeItem('mia_famiglia'); localStorage.removeItem('mio_otp'); }catch(e){}
  FAMIGLIA_ID=null; FASE=1;
  document.getElementById('bentornato').style.display='none';
  document.getElementById('chiSono').innerText='';
  alert('Uscito. Ora puoi fare ACCEDI con un altro numero.');
  location.reload();
}
function nuovaIscrizione(){
  try{ localStorage.removeItem('mia_famiglia'); localStorage.removeItem('mio_otp'); }catch(e){}
  FAMIGLIA_ID=null; FASE=1;
  document.getElementById('numPersona').innerText='1';
  document.getElementById('btnSalva').innerText='SALVA UTENTE';
  document.getElementById('btnSalva').disabled=false;
  document.getElementById('boxIscrizione').classList.remove('bloccato');
  document.getElementById('spuntaVerde').style.display='none';
  document.getElementById('boxPrivacy').style.display='none';
  document.getElementById('nome').disabled=false;
  document.getElementById('cognome').disabled=false;
  document.getElementById('cell').disabled=false;
  document.getElementById('email').disabled=false;
  nome.value=''; cognome.value=''; cell.value=''; email.value='';
  document.getElementById('r1').innerText='Ora puoi iscrivere una NUOVA famiglia da zero.';
  document.getElementById('linkbox').innerHTML='';
}
async function accedi(){
  if(!loginCell.value || !loginOtp.value){ alert('MANCA NUMERO / OTP'); return; }
  let datiLogin = {};
  datiLogin["cell"] = loginCell.value;
  datiLogin["otp"] = loginOtp.value;
  let r=await fetch('/accedi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datiLogin)}).then(x=>x.json());
  document.getElementById('rLogin').innerText=r.msg;
  document.getElementById('rLogin').className=r.ok?'verde':'rosso';
  if(r.ok){
    FAMIGLIA_ID=r.famiglia_id;
    salvaInTelefono(FAMIGLIA_ID, loginOtp.value);
    document.getElementById('bentornato').style.display='block';
    document.getElementById('bentornato').innerText='✅ BENTORNATO! Sei Famiglia '+FAMIGLIA_ID+' - Ora puoi mandare messaggi.';
    document.getElementById('linkbox').innerHTML='Il tuo CODICE: <b>'+r.codice+'</b><br>Il tuo OTP: <b>'+r.otp+'</b>';
    aggiornaChiSono();
    caricaLista();
  }
}
async function recuperaOtp(){
  if(!recCell.value || !recNome.value || !recCognome.value || !recEmail.value){ alert('MANCA CELL / NOME / COGNOME / EMAIL - METTILI TUTTI E 4'); return; }
  let datiRec = {};
  datiRec["cell"] = recCell.value;
  datiRec["nome"] = recNome.value;
  datiRec["cognome"] = recCognome.value;
  datiRec["email"] = recEmail.value;
  let r=await fetch('/recupera_otp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datiRec)}).then(x=>x.json());
  document.getElementById('rRecupera').innerText=r.msg;
  document.getElementById('rRecupera').className=r.ok?'verde':'rosso';
  if(r.ok){
    document.getElementById('rRecupera').innerHTML='✅ TI HO MANDATO OTP PER MAIL A '+recEmail.value+'<br>Controlla la mail, anche nello SPAM. Poi metti OTP sopra e premi ACCEDI.';
  }
}
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
function bloccaCambio(){
  document.getElementById('boxCambioNumero').classList.add('bloccato');
  document.getElementById('spuntaCambio').style.display='block';
  document.getElementById('btnCambia').disabled=true;
  document.getElementById('nomeCambio').disabled=true;
  document.getElementById('cognomeCambio').disabled=true;
  document.getElementById('emailCambio').disabled=true;
  document.getElementById('vecchioNum').disabled=true;
  document.getElementById('nuovoNum').disabled=true;
}
async function salvaPersona(){
 if(FASE==1){
   if(!nome.value || !cognome.value || !cell.value){alert("MANCA NOME / COGNOME / CELL");return;}
   let datiP1 = {};
   datiP1["famiglia_id"] = null;
   datiP1["ruolo"] = 'UTENTE';
   datiP1["nome"] = nome.value;
   datiP1["cognome"] = cognome.value;
   datiP1["cell"] = cell.value;
   datiP1["email"] = email.value;
   let r=await fetch('/salva_persona',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datiP1)}).then(x=>x.json());
   document.getElementById('r1').innerText=r.msg; document.getElementById('r1').className=r.ok?'verde':'rosso';
   if(r.ok){
     FAMIGLIA_ID=r.famiglia_id;
     salvaInTelefono(FAMIGLIA_ID, r.otp);
     document.getElementById('linkbox').innerHTML='<br><a href="'+r.link+'" target="_blank"><b>CLICCA QUI PER ENTRARE SU TELEGRAM</b></a><br>Il tuo CODICE UNICO: <b>'+r.codice+'</b><br>Il tuo OTP UNICO: <b>'+r.otp+'</b><br><b>CONTROLLA ANCHE LA MAIL, TE LO ABBIAMO MANDATO LI.</b>';
     FASE=2;
     document.getElementById('numPersona').innerText='2';
     document.getElementById('r1').innerText='✅ PRIMO UTENTE SALVATO. Ti abbiamo mandato OTP per mail. Ora inserisci il SECONDO UTENTE.';
     nome.value=''; cognome.value=''; cell.value=''; email.value='';
     document.getElementById('boxPrivacy').style.display='block';
     document.getElementById('btnSalva').innerText='SALVA - FINE ISCRIZIONE';
     aggiornaChiSono();
     caricaLista();
   }
   return;
 }
 if(FASE==2){
   if(!nome.value || !cognome.value || !cell.value){alert("MANCA NOME / COGNOME / CELL - INSERISCI UTENTE 2");return;}
   if(!document.getElementById('priv1').checked){alert("DEVI METTERE LA SPUNTA PRIVACY PER FINIRE");return;}
   let datiP2 = {};
   datiP2["famiglia_id"] = FAMIGLIA_ID;
   datiP2["ruolo"] = 'UTENTE';
   datiP2["nome"] = nome.value;
   datiP2["cognome"] = cognome.value;
   datiP2["cell"] = cell.value;
   datiP2["email"] = email.value;
   let r=await fetch('/salva_persona',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datiP2)}).then(x=>x.json());
   document.getElementById('r1').innerText=r.msg; document.getElementById('r1').className=r.ok?'verde':'rosso';
   if(r.ok){
     if(r.quante<2){alert("INSERISCI UTENTE 2");return;}
     document.getElementById('r1').innerText='✅ 2 UTENTI ISCRITTI. Iscrizione chiusa.';
     bloccaIscrizione();
     caricaLista();
   }
   return;
 }
}
async function salvaMessaggio(){
 if(!FAMIGLIA_ID){alert("Prima devi iscriverti con 2 UTENTI, oppure fai ACCEDI sopra con numero + OTP");return;}
 if(!testo.value){alert("SCRIVI IL MESSAGGIO");return;}
 if(!dataora.value){alert("SCEGLI GIORNO E ORA DAL CALENDARIO");return;}
 let parti = dataora.value.split('T');
 let dataScelta = parti[0];
 let oraScelta = parti[1].substring(0,5);
 if(!confirm("HAI SCRITTO: "+testo.value+" - IL GIORNO "+dataScelta+" ALLE "+oraScelta+" - È CORRETTO? SI / NO")) return;
 let datiMsg = {};
 datiMsg["famiglia_id"] = FAMIGLIA_ID;
 datiMsg["utente_id"] = FAMIGLIA_ID;
 datiMsg["testo"] = testo.value;
 datiMsg["data"] = dataScelta;
 datiMsg["ora"] = oraScelta;
 datiMsg["destinatario"] = dest.value;
 let r=await fetch('/salva_messaggio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datiMsg)}).then(x=>x.json());
 document.getElementById('rm').innerText=r.msg; if(r.ok) caricaLista();
}
async function caricaLista(){ if(!FAMIGLIA_ID) return; let l=await fetch('/lista_messaggi/'+FAMIGLIA_ID).then(x=>x.json()); let h=""; l.forEach(m=>{h+="<div>"+m.destinatario+" - "+m.testo+" - "+m.data_invio+" "+m.ora_invio+" - "+m.stato+" <button onclick=\\"cancellaMsg("+m.id+")\\">CANCELLA</button> <button onclick=\\"modificaMsg("+m.id+")\\">CAMBIA</button></div>";}); document.getElementById('lista').innerHTML=h; }
async function cancellaMsg(id){ let d1={}; d1["id"]=id; await fetch('/cancella_messaggio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d1)}); caricaLista(); }
async function modificaMsg(id){
  let t=prompt("Nuovo testo:"); if(!t) return;
  let datiMod = {};
  datiMod["id"] = id;
  datiMod["testo"] = t;
  datiMod["data"] = dataora.value.split('T')[0];
  datiMod["ora"] = dataora.value.split('T')[1].substring(0,5);
  datiMod["destinatario"] = dest.value;
  await fetch('/modifica_messaggio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(datiMod)});
  caricaLista();
}
async function inviaContatto(){
  let dC={}; dC["messaggio"]=msgCont.value;
  let r=await fetch('/contatti',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dC)}).then(x=>x.json());
  document.getElementById('rc').innerText=r.msg;
}
async function cambiaNumero(){
 if(!FAMIGLIA_ID){alert("Prima devi iscriverti o fare ACCEDI");return;}
 if(!nomeCambio.value || !cognomeCambio.value || !emailCambio.value || !vecchioNum.value || !nuovoNum.value){alert("MANCA NOME / COGNOME / EMAIL / CELLULARE VECCHIO / CELLULARE NUOVO");return;}
 let dNum={};
 dNum["utente_id"]=FAMIGLIA_ID;
 dNum["nome"]=nomeCambio.value;
 dNum["cognome"]=cognomeCambio.value;
 dNum["email"]=emailCambio.value;
 dNum["vecchio_numero"]=vecchioNum.value;
 dNum["nuovo_numero"]=nuovoNum.value;
 let r=await fetch('/cambia_numero',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dNum)}).then(x=>x.json());
 document.getElementById('rCambio').innerText=r.msg; document.getElementById('rCambio').className=r.ok?'verde':'rosso';
 if(r.ok){ bloccaCambio(); }
}
async function paga(piano){alert("Paghi "+piano+" con Carta o PayPal. Dopo il pagamento Stripe manda WEBHOOK e ti sblocca in 1-2 minuti.");}
async function mandaSOS(){
 if(!FAMIGLIA_ID){alert("Prima devi iscriverti o fare ACCEDI");return;}
 if(!navigator.geolocation){alert("Questo telefono non manda la posizione");return;}
 document.getElementById('rSOS').innerText="Sto prendendo la posizione...";
 navigator.geolocation.getCurrentPosition(async function(pos){
   let lat=pos.coords.latitude, lon=pos.coords.longitude;
   let dSos={}; dSos["famiglia_id"]=FAMIGLIA_ID; dSos["lat"]=lat; dSos["lon"]=lon;
   let r=await fetch('/sos_posizione',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dSos)}).then(x=>x.json());
   document.getElementById('rSOS').innerText=r.msg;
 }, function(){ document.getElementById('rSOS').innerText="Devi premere CONSENTI alla posizione"; });
}
window.onload=function(){
  try{
    let salvato = localStorage.getItem('mia_famiglia');
    if(salvato){
      FAMIGLIA_ID = parseInt(salvato);
      document.getElementById('bentornato').style.display='block';
      document.getElementById('bentornato').innerText='✅ BENTORNATO! Ti ho riconosciuto, sei Famiglia '+FAMIGLIA_ID;
      aggiornaChiSono();
      caricaLista();
    }
  }catch(e){}
}
</script></body></html>
"""

@app.route("/")
def home(): return render_template_string(HTML)

@app.route("/health")
def health(): return "OK", 200

@app.route("/test_mail")
def test_mail():
    ok = manda_email_a(EMAIL_TO, "PROVA MAIL BADANTE", "Se leggi questa mail, la mail funziona.")
    if ok:
        return "<h1 style='color:green'>✅ FATTO - MAIL MANDATA - Controlla la posta di latuabadantevirtuale@libero.it</h1>"
    else:
        return "<h1 style='color:red'>⛔ MAIL NON MANDATA - Manca EMAIL_PASS su Render o Libero la blocca - Guarda i LOG su Render</h1>"

@app.route("/accedi", methods=["POST"])
def accedi():
    d = request.json or {}
    cell = (d.get("cell") or "").strip()
    otp = (d.get("otp") or "").strip()
    if not cell or not otp:
        return jsonify({"ok": False, "msg": "MANCA NUMERO / OTP"})
    con = db()
    p = con.execute("SELECT * FROM persone WHERE TRIM(cell)=?", (cell,)).fetchone()
    if not p:
        con.close()
        return jsonify({"ok": False, "msg": "NUMERO NON TROVATO - DEVI ISCRIVERTI PRIMA"})
    fam = con.execute("SELECT * FROM famiglie WHERE id=? AND otp=?", (p["famiglia_id"], otp)).fetchone()
    if not fam:
        con.close()
        return jsonify({"ok": False, "msg": "OTP SBAGLIATO - CONTROLLA IL CODICE DI 6 CIFRE"})
    out = {"ok": True, "msg": "BENTORNATO - TI HO RICONOSCIUTO", "famiglia_id": fam["id"], "codice": fam["codice_link"], "otp": fam["otp"]}
    con.close()
    return jsonify(out)

@app.route("/recupera_otp", methods=["POST"])
def recupera_otp():
    d = request.json or {}
    cell = (d.get("cell") or "").strip()
    nome = (d.get("nome") or "").strip().lower()
    cognome = (d.get("cognome") or "").strip().lower()
    email = (d.get("email") or "").strip().lower()
    if not cell or not nome or not cognome or not email:
        return jsonify({"ok": False, "msg": "MANCA CELL / NOME / COGNOME / EMAIL - METTILI TUTTI E 4"})
    con = db()
    p = con.execute("SELECT * FROM persone WHERE TRIM(cell)=? AND LOWER(TRIM(nome))=? AND LOWER(TRIM(cognome))=? AND LOWER(TRIM(email))=?", (cell, nome, cognome, email)).fetchone()
    if not p:
        con.close()
        return jsonify({"ok": False, "msg": "DATI SBAGLIATI - NOME / COGNOME / EMAIL / CELL NON COMBACIANO CON QUELLI DELL'ISCRIZIONE"})
    fam = con.execute("SELECT * FROM famiglie WHERE id=?", (p["famiglia_id"],)).fetchone()
    con.close()
    if not fam:
        return jsonify({"ok": False, "msg": "FAMIGLIA NON TROVATA"})
    manda_email_a(email, "LA TUA BADANTE VIRTUALE - IL TUO OTP", f"Ciao {p['nome']},\n\nIl tuo OTP è: {fam['otp']}\nIl tuo CODICE è: {fam['codice_link']}\n\nMettilo in ACCEDI sul sito.\n\nLa Tua Badante Virtuale")
    return jsonify({"ok": True, "msg": "OTP MANDATO PER MAIL - CONTROLLA LA MAIL, ANCHE SPAM", "otp": fam["otp"], "codice": fam["codice_link"], "famiglia_id": fam["id"]})

@app.route("/salva_persona", methods=["POST"])
def salva_persona():
    d = request.json
    if not all([d.get("nome"), d.get("cognome"), d.get("cell")]): return jsonify({"ok": False, "msg": "MANCA QUALCOSA, CONTROLLA"})
    con = db()
    fam_id = d.get("famiglia_id")
    if not fam_id:
        gia = con.execute("SELECT * FROM persone WHERE TRIM(cell)=?", (d["cell"].strip(),)).fetchone()
        if gia:
            con.close()
            return jsonify({"ok": False, "msg": "QUESTO NUMERO E' GIA' ISCRITTO! NON ISCRIVERTI DI NUOVO - FAI ACCEDI SOPRA CON NUMERO + OTP"})
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
    if d.get("email"):
        manda_email_a(d.get("email"), "LA TUA BADANTE VIRTUALE - BENVENUTO - IL TUO OTP", f"Ciao {d['nome']},\n\nBenvenuto! Iscrizione fatta.\n\nIl tuo CODICE UNICO è: {codice}\nIl tuo OTP UNICO è: {otp}\n\nSCRIVILO! Ti serve per fare ACCEDI tra un mese.\nEntra su Telegram qui: https://t.me/{BOT_NAME}?start={codice}\n\nLa Tua Badante Virtuale")
    link = f"https://t.me/{BOT_NAME}?start={codice}"
    return jsonify({"ok": True, "msg": "SALVATO ✓ CONTROLLA LA MAIL - TI ABBIAMO MANDATO OTP" if quante==1 else "SECONDO UTENTE SALVATO ✓", "famiglia_id": fam_id, "quante": quante, "link": link, "codice": codice, "otp": otp})

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
    if cnt >= 10: return jsonify({"ok": False, "msg": "HAI GIÀ 10 MESSAGGI PER OGGI PER QUESTO UTENTE"})
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
    nome = (d.get("nome") or "").strip().lower()
    cognome = (d.get("cognome") or "").strip().lower()
    email = (d.get("email") or "").strip().lower()
    vecchio = (d.get("vecchio_numero") or "").strip()
    nuovo = (d.get("nuovo_numero") or "").strip()
    fam_id = d.get("utente_id")
    if not nome or not cognome or not email or not vecchio or not nuovo or not fam_id:
        con.close(); return jsonify({"ok": False, "msg": "MANCA NOME / COGNOME / EMAIL / CELLULARE VECCHIO / CELLULARE NUOVO"})
    pers = con.execute("SELECT * FROM persone WHERE famiglia_id=? AND LOWER(TRIM(nome))=? AND LOWER(TRIM(cognome))=? AND LOWER(TRIM(email))=? AND TRIM(cell)=?", (fam_id, nome, cognome, email, vecchio)).fetchone()
    if not pers:
        con.close(); return jsonify({"ok": False, "msg": "DATI SBAGLIATI - NOME / COGNOME / EMAIL / CELLULARE VECCHIO NON COMBACIANO - SI BLOCCA TUTTO"})
    con.execute("UPDATE persone SET cell=?, telegram_id=NULL WHERE id=?", (nuovo, pers["id"]))
    con.commit(); con.close(); return jsonify({"ok": True, "msg": "NUMERO CAMBIATO ✓ DEVE FARE DI NUOVO CONDIVIDI NUMERO"})
@app.route("/contatti", methods=["POST"])
def contatti():
    d = request.json; con = db(); con.execute("INSERT INTO contatti(email,messaggio,creato_il) VALUES(?,?,?)", (MIA_EMAIL, d["messaggio"], datetime.datetime.now().isoformat())); con.commit(); con.close()
    manda_email_a(EMAIL_TO, "NUOVO CONTATTO - LA TUA BADANTE VIRTUALE", f"Nuovo messaggio da CONTATTI:\n\n{d['messaggio']}\n\nData: {datetime.datetime.now().isoformat()}")
    return jsonify({"ok": True, "msg": "MESSAGGIO INVIATO ✓ Grazie, ti rispondiamo presto."})
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
    tot = con.execute("SELECT COUNT(*) c FROM famiglie").fetchone()["c"]
    prova = con.execute("SELECT COUNT(*) c FROM famiglie WHERE stato='PROVA'").fetchone()["c"]
    pagato = con.execute("SELECT COUNT(*) c FROM famiglie WHERE stato LIKE 'SBLOCCATO%'").fetchone()["c"]
    bloccato = con.execute("SELECT COUNT(*) c FROM famiglie WHERE stato='BLOCCATO'").fetchone()["c"]
    mandati = con.execute("SELECT COUNT(*) c FROM messaggi WHERE stato='MANDATO'").fetchone()["c"]
    si = con.execute("SELECT COUNT(*) c FROM messaggi WHERE risposta='SI'").fetchone()["c"]
    no = con.execute("SELECT COUNT(*) c FROM messaggi WHERE risposta='NO'").fetchone()["c"]
    non_risp = con.execute("SELECT COUNT(*) c FROM messaggi WHERE risposta IS NULL AND stato='MANDATO'").fetchone()["c"]
    con.close()
    return f"<h1>ADMIN</h1><p>TOTALE COPPIE: <b>{tot}</b></p><p>IN PROVA: <b>{prova}</b></p><p>PAGATO: <b>{pagato}</b></p><p>BLOCCATO: <b>{bloccato}</b></p><p>MESSAGGI MANDATI: <b>{mandati}</b></p><p>SI: <b>{si}</b> NO: <b>{no}</b> NON HANNO RISPOSTO: <b>{non_risp}</b></p><br><a href='/pannello?password={ADMIN_PASSWORD}'><b>VAI AL PANNELLO BLOCCA / SBLOCCA</b></a>"

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
                    if testo.strip().upper() in ["AVVIA", "AVVIA_START", "START", "CIAO", "HI", "INIZIA"]:
                        manda_telegram(chat_id, "Ciao! Sono il tuo Badante Virtuale ❤️\n\nVuoi configurare il Badante?", {"inline_keyboard": [[{"text": "✅ SI - Configura", "callback_data": "CONFIG_SI"}, {"text": "❌ NO - Salta", "callback_data": "CONFIG_NO"}], [{"text": "🆘 SOS", "callback_data": "HELP_AVVIA"}]]})
                    elif testo.startswith("/start"):
                        parti = testo.split(); codice = parti[1] if len(parti) > 1 else ""
                        fam = con.execute("SELECT * FROM famiglie WHERE codice_link=?", (codice,)).fetchone() if codice else None
                        if fam:
                            manda_telegram(chat_id, f"Ciao UTENTE, il tuo codice unico è {fam['otp']}. Scrivilo qui per firmare ed entrare.", {"inline_keyboard": [[{"text": "✅ HO CAPITO - SCRIVO IL CODICE", "callback_data": "AVVIA_START"}]]})
                        else:
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
                        if testo.strip() != "":
                            manda_telegram(chat_id, "Scrivi AVVIA per vedere il menu ❤️")
                if "callback_query" in upd:
                    cb = upd["callback_query"]; chat_id = cb["message"]["chat"]["id"]; data = cb["data"]
                    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": cb["id"]}, timeout=5)
                    except: pass
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

@app.route("/pannello/blocca/<int:fid>")
def pannello_blocca(fid):
    if request.args.get("password") != ADMIN_PASSWORD:
        return "PASSWORD SBAGLIATA", 403
    con = db()
    con.execute("UPDATE famiglie SET stato='BLOCCATO' WHERE id=?", (fid,))
    con.commit(); con.close()
    return f"<h1 style='color:red'>⛔ BLOCCATO</h1><div style='font-size:40px;color:green'>✅ FATTO - FAMIGLIA {fid} BLOCCATA</div><br><br><a href='/pannello?password={ADMIN_PASSWORD}'><b>TORNA AL PANNELLO</b></a>"

@app.route("/pannello/sblocca/<int:fid>")
def pannello_sblocca(fid):
    if request.args.get("password") != ADMIN_PASSWORD:
        return "PASSWORD SBAGLIATA", 403
    con = db()
    con.execute("UPDATE famiglie SET stato='SBLOCCATO - PAGATO' WHERE id=?", (fid,))
    con.commit(); con.close()
    return f"<h1 style='color:green'>✅ SBLOCCATO</h1><div style='font-size:40px;color:green'>✅ FATTO - FAMIGLIA {fid} SBLOCCATA</div><br><br><a href='/pannello?password={ADMIN_PASSWORD}'><b>TORNA AL PANNELLO</b></a>"

@app.route("/pannello")
def pannello():
    if request.args.get("password") != ADMIN_PASSWORD:
        return "PASSWORD SBAGLIATA", 403
    con = db()
    fams = con.execute("SELECT * FROM famiglie ORDER BY id DESC").fetchall()
    html = "<h1>PANNELLO - ISCRITTI ACCOPPIATI</h1>"
    if not fams:
        html += "<h2>NESSUN ISCRITTO ANCORA - Quando si iscrive la prima coppia, qui vedi BLOCCA e SBLOCCA</h2>"
        con.close()
        return html
    html += "<table border='1' cellpadding='6'><tr><th>FAMIGLIA ID</th><th>UTENTE 1 - ID</th><th>UTENTE 1 - NOME</th><th>UTENTE 1 - COGNOME</th><th>UTENTE 1 - CELL</th><th>UTENTE 1 - MAIL</th><th>UTENTE 1 - OTP</th><th>UTENTE 2 - ID</th><th>UTENTE 2 - NOME</th><th>UTENTE 2 - COGNOME</th><th>UTENTE 2 - CELL</th><th>UTENTE 2 - MAIL</th><th>UTENTE 2 - OTP</th><th>STATO</th><th>BLOCCA</th><th>SBLOCCA</th></tr>"
    for f in fams:
        pers = con.execute("SELECT * FROM persone WHERE famiglia_id=? ORDER BY id", (f["id"],)).fetchall()
        u1 = pers[0] if len(pers) > 0 else None
        u2 = pers[1] if len(pers) > 1 else None
        id1 = u1["id"] if u1 else "-"
        nome1 = u1["nome"] if u1 else "MANCA"
        cog1 = u1["cognome"] if u1 else "-"
        cell1 = u1["cell"] if u1 else "-"
        mail1 = u1["email"] if u1 else "-"
        otp1 = f["otp"] if u1 else "-"
        id2 = u2["id"] if u2 else "-"
        nome2 = u2["nome"] if u2 else "MANCA - SOLO 1 ISCRITTO"
        cog2 = u2["cognome"] if u2 else "-"
        cell2 = u2["cell"] if u2 else "-"
        mail2 = u2["email"] if u2 else "-"
        otp2 = f["otp"] if u2 else "-"
        fid = f["id"]
        html += f"<tr><td>{fid}</td><td>{id1}</td><td>{nome1}</td><td>{cog1}</td><td>{cell1}</td><td>{mail1}</td><td>{otp1}</td><td>{id2}</td><td>{nome2}</td><td>{cog2}</td><td>{cell2}</td><td>{mail2}</td><td>{otp2}</td><td>{f['stato']}</td><td><a href='/pannello/blocca/{fid}?password={ADMIN_PASSWORD}'><b>BLOCCA</b></a></td><td><a href='/pannello/sblocca/{fid}?password={ADMIN_PASSWORD}'><b>SBLOCCA</b></a></td></tr>"
    html += "</table>"
    con.close()
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"LA TUA BADANTE VIRTUALE ACCESO - Porta {port}")
    app.run(host="0.0.0.0", port=port)

"""Probador local del agente de voz: hablale por el microfono, sin llamadas.

Abrir http://localhost:8000/dev/voz y hablar. Usa el mismo modelo, la misma voz
y las mismas instrucciones que la llamada real por telefono.
"""
from fastapi import APIRouter, WebSocket
from fastapi.responses import HTMLResponse

from ..agent import realtime
from ..config import AGENT_NAME, OPENAI_REALTIME_MODEL, REALTIME_VOICE

router = APIRouter(prefix="/dev", tags=["dev"])

SESSION = {"reason": "arrival_check",
           "ctx": {"name": "Tomas Schattmann", "port": "Puerto Buenos Aires - Terminal 4",
                   "container": "MSCU-4471820", "detail": "estas detenido hace 7 minutos"}}

PAGINA = """<!doctype html><meta charset=utf-8><title>Probar la voz</title>
<style>
 body{font:16px system-ui;background:#0f1115;color:#e6e6e6;margin:0;padding:40px;display:flex;
      flex-direction:column;align-items:center;gap:18px}
 h1{font-size:19px;font-weight:600;margin:0}
 .meta{color:#8b93a7;font-size:13px}
 button{font:600 16px system-ui;padding:14px 30px;border:0;border-radius:999px;cursor:pointer;
        background:#3b82f6;color:#fff}
 button.on{background:#ef4444}
 #estado{color:#8b93a7;font-size:13px;min-height:20px}
 #log{width:min(620px,92vw);background:#161a22;border-radius:10px;padding:14px 16px;
      max-height:52vh;overflow:auto;line-height:1.65;font-size:14px}
 .AGENTE{color:#7dd3a0}.VOS{color:#fbbf24}.err{color:#f87171}
 .voz{color:#8b93a7;font-size:12.5px}.bostezo{color:#f59e0b;font-weight:600}
 b{font-weight:600;margin-right:6px}
</style>
<h1>Probar la voz del agente</h1>
<div class=meta>modelo <b>__MODELO__</b> · voz <b>__VOZ__</b> · agente <b>__AGENTE__</b></div>
<button id=b>Hablar</button>
<div class=meta>proba bostezar cerca del microfono</div>
<div id=estado>permiti el microfono cuando lo pida</div>
<div id=log></div>
<script>
const DESTINO = 24000;            // unico sample rate que acepta OpenAI Realtime
const SR = 24000;                 // el audio que llega del agente
let ctx, ws, stream, node, on = false;
let frames = 0, enviados = 0;
const descartados = {ws: 0, agente: 0};
let cola = [], siguiente = 0, sonando = [];
const log = document.getElementById('log');
const estado = document.getElementById('estado');

function escribir(quien, texto, cls) {
  const d = document.createElement('div');
  d.className = cls || quien;
  d.innerHTML = '<b>' + quien + ':</b>' + texto;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
}

function reproducir(b64) {
  const bin = atob(b64), n = bin.length / 2;
  const buf = ctx.createBuffer(1, n, SR), ch = buf.getChannelData(0);
  for (let i = 0; i < n; i++) {
    const lo = bin.charCodeAt(i*2), hi = bin.charCodeAt(i*2+1);
    let v = (hi << 8) | lo; if (v >= 32768) v -= 65536;
    ch[i] = v / 32768;
  }
  const src = ctx.createBufferSource();
  src.buffer = buf; src.connect(ctx.destination);
  // encadenar los chunks para que no se escuchen cortes entre uno y otro
  siguiente = Math.max(siguiente, ctx.currentTime);
  src.start(siguiente); siguiente += buf.duration;
  sonando.push(src);
  src.onended = () => sonando = sonando.filter(s => s !== src);
}

// El microfono se pausa mientras suena el agente, si no el parlante entra por
// el mic y OpenAI cree que lo estas interrumpiendo. Lo calculamos con el reloj
// del audio y no con un flag del servidor: si un mensaje se pierde, el flag
// queda trabado y el microfono no vuelve nunca.
// OpenAI solo acepta 24 kHz. Chrome suele capturar a 48 kHz aunque le pidamos
// otra cosa, asi que bajamos el sample rate nosotros antes de enviar. Sin esto
// el audio le llega al doble de velocidad y no transcribe nada.
function a24k(f, rateOrigen) {
  if (rateOrigen === DESTINO) return f;
  const ratio = rateOrigen / DESTINO;
  const n = Math.floor(f.length / ratio);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const i1 = Math.min(i0 + 1, f.length - 1);
    const t = pos - i0;
    out[i] = f[i0] * (1 - t) + f[i1] * t;   // interpolacion lineal
  }
  return out;
}

function agenteSonando() {
  return !!ctx && siguiente > ctx.currentTime + 0.05;
}

function cortar() {           // el usuario interrumpio: tirar lo que quedaba sonando
  sonando.forEach(s => { try { s.stop(); } catch (e) {} });
  sonando = []; siguiente = 0;
}

async function arrancar() {
  ctx = new AudioContext({sampleRate: SR});
  stream = await navigator.mediaDevices.getUserMedia({audio:{
    echoCancellation:true, noiseSuppression:true, autoGainControl:true}});
  ws = new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/dev/voz/ws');
  ws.onerror = e => console.error('[ws] error', e);
  ws.onclose = e => console.warn('[ws] cerrado', e.code, e.reason);
  ws.onopen = () => {
    // Chrome suele ignorar el sampleRate pedido y usar el nativo (48k). Si le
    // decimos a OpenAI un rate que no es, el audio le llega acelerado y no
    // transcribe nada. Le mandamos el real.
    ws.send(JSON.stringify({type: 'init', rate: ctx.sampleRate}));
    estado.textContent = 'conectado · micrófono ' + ctx.sampleRate +
      ' Hz → 24000 Hz · hablá cuando quieras';
  };
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.type !== 'audio') console.log('[<- server]', m.type, m);
    if (m.type === 'audio') reproducir(m.audio);
    else if (m.type === 'clear') cortar();
    else if (m.type === 'dijo' && m.texto) escribir(m.quien, ' ' + m.texto);
    else if (m.type === 'error') escribir('ERROR', ' ' + m.text, 'err');
    else if (m.type === 'info') escribir('', m.text, 'voz');
    else if (m.type === 'estado') escribir('', '· ' + m.texto, 'voz');
    else if (m.type === 'hablando') {
      estado.textContent = m.v
        ? 'el agente esta hablando (micrófono en pausa)'
        : 'te escucho, hablá cuando quieras';
    }
    else if (m.type === 'ambiente') estado.textContent =
        'ambiente: piso ' + m.piso + ' · umbral ' + m.umbral +
        (m.voz_pct !== undefined ? ' · ultimo tramo ' + m.voz_pct + '% voz' : '');
    else if (m.type === 'voz') {
      const a = m.analisis;
      escribir('BOSTEZO', ' detectado (score ' + a.score + ', ' +
          a.duracion_voz_s + 's, ' + a.centroide_hz + ' Hz)', 'bostezo');
    }
  };
  console.log('[audio] ctx.sampleRate =', ctx.sampleRate,
              '| pista:', stream.getAudioTracks()[0]?.label,
              '| settings:', stream.getAudioTracks()[0]?.getSettings());
  const src = ctx.createMediaStreamSource(stream);
  node = ctx.createScriptProcessor(2048, 1, 1);
  node.onaudioprocess = ev => {
    const crudo = ev.inputBuffer.getChannelData(0);
    // nivel del microfono: si esto es ~0 el audio no llega al procesador
    let suma = 0;
    for (let i = 0; i < crudo.length; i++) suma += crudo[i] * crudo[i];
    const rms = Math.sqrt(suma / crudo.length);
    frames++;
    if (frames % 20 === 0) {
      console.log('[mic] frame', frames, 'rms', rms.toFixed(4),
                  '| enviados', enviados, '| agenteSonando', agenteSonando(),
                  '| ws', ws && ws.readyState);
    }
    if (!ws || ws.readyState !== 1) { descartados.ws++; return; }
    if (agenteSonando()) { descartados.agente++; return; }
    const f = a24k(crudo, ctx.sampleRate);
    let s = '';
    for (let i = 0; i < f.length; i++) {           // Float32 -> PCM16 little endian
      let v = Math.max(-1, Math.min(1, f[i])) * 32767;
      v = v < 0 ? v + 65536 : v;
      s += String.fromCharCode(v & 255, (v >> 8) & 255);
    }
    const b64 = btoa(s);
    enviados++;
    if (enviados === 1 || enviados % 40 === 0) {
      console.log('[-> openai] chunk', enviados, 'muestras', f.length,
                  'bytes b64', b64.length, '| descartados', JSON.stringify(descartados));
    }
    ws.send(JSON.stringify({type:'audio', audio: b64}));
  };
  src.connect(node); node.connect(ctx.destination);
}

function parar() {
  cortar();
  if (node) node.disconnect();
  if (stream) stream.getTracks().forEach(t => t.stop());
  if (ws) ws.close();
  if (ctx) ctx.close();
  estado.textContent = 'cortado';
}

document.getElementById('b').onclick = async e => {
  on = !on;
  e.target.textContent = on ? 'Cortar' : 'Hablar';
  e.target.className = on ? 'on' : '';
  if (on) { log.innerHTML=''; await arrancar(); } else parar();
};
</script>"""


@router.get("/voz", response_class=HTMLResponse, summary="Probar la voz por microfono")
def voz():
    """Pagina para hablarle al agente desde la PC, sin gastar llamadas."""
    return (PAGINA.replace("__MODELO__", OPENAI_REALTIME_MODEL)
            .replace("__VOZ__", REALTIME_VOICE).replace("__AGENTE__", AGENT_NAME))


@router.websocket("/voz/ws")
async def voz_ws(websocket: WebSocket):
    await websocket.accept()
    await realtime.bridge_browser(websocket, SESSION)

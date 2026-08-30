"""Deteccion de bostezos en la voz del conductor, sin pasar por OpenAI.

Corre sobre el mismo audio que ya viaja por la llamada. La idea es no depender
del LLM para una senal de fatiga: esto es medible.

Un bostezo, acusticamente, es bastante reconocible incluso en audio telefonico:

- una vocalizacion sostenida y larga (~1 a 4 segundos sin cortes)
- energia con una sola joroba: sube, se mantiene, baja suave
- sonido oscuro, casi sin agudos (centroide espectral bajo)
- pocos cruces por cero, porque es una vocal abierta y no consonantes
- tono que cae hacia el final

El audio del telefono es de 8kHz, asi que arriba de 4kHz no hay nada. Alcanza
para el bostezo, que vive en frecuencias bajas.
"""
import audioop
import logging
import math

import numpy as np

log = logging.getLogger("voz")

# Umbrales. Estan sueltos a proposito para poder tunearlos en la demo, igual
# que los del detector de eventos.
MIN_SEG = 0.9          # un bostezo dura al menos esto
MAX_SEG = 5.0          # mas que esto ya no es un bostezo
MAX_CENTROIDE = 900.0  # Hz: por encima suena "brillante", no un bostezo
MAX_ZCR = 0.12         # cruces por cero por muestra
MIN_ENERGIA = 0.015    # debajo de esto es silencio o ruido de fondo

VENTANA = 0.032        # 32 ms por frame


def ulaw_a_pcm16(datos: bytes) -> bytes:
    """Twilio manda g711 ulaw; audioop lo pasa a PCM16 sin dependencias."""
    return audioop.ulaw2lin(datos, 2)


def _frames(x, rate):
    n = max(1, int(rate * VENTANA))
    total = len(x) // n
    return x[:total * n].reshape(total, n) if total else np.empty((0, n))


def _centroide(frame, rate):
    """Frecuencia media del frame: cuanto mas bajo, mas oscuro el sonido."""
    esp = np.abs(np.fft.rfft(frame))
    if esp.sum() < 1e-9:
        return 0.0
    freqs = np.fft.rfftfreq(len(frame), 1 / rate)
    return float((freqs * esp).sum() / esp.sum())


def _una_sola_joroba(energia):
    """True si la energia sube y baja una vez sola, como en un bostezo.

    Si hay varios picos son palabras, no una vocalizacion sostenida.
    """
    if len(energia) < 5:
        return False
    suave = np.convolve(energia, np.ones(3) / 3, mode="same")
    pico = int(np.argmax(suave))
    # el pico no puede estar pegado a los bordes
    if pico < 1 or pico > len(suave) - 2:
        return False
    subida = np.diff(suave[:pico + 1])
    bajada = np.diff(suave[pico:])
    # tolerante: la mayoria del tramo sube antes del pico y baja despues
    return (subida >= 0).mean() > 0.6 and (bajada <= 0).mean() > 0.6


def analizar(pcm16: bytes, rate: int = 8000) -> dict:
    """Analiza un segmento de habla. Devuelve el diagnostico y por que.

    `pcm16` es audio PCM 16 bits mono. Para Twilio hay que pasarlo antes por
    `ulaw_a_pcm16`.
    """
    x = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
    dur = len(x) / rate
    vacio = {"bostezo": False, "score": 0.0, "duracion_s": round(dur, 2)}
    if dur < MIN_SEG:
        return {**vacio, "motivo": "muy corto"}

    fr = _frames(x, rate)
    if not len(fr):
        return {**vacio, "motivo": "sin frames"}

    energia = np.sqrt((fr ** 2).mean(axis=1))
    con_voz = energia > MIN_ENERGIA
    if not con_voz.any():
        return {**vacio, "motivo": "silencio"}

    # la racha continua de voz mas larga del segmento
    mejor = actual = 0
    fin = 0
    for i, v in enumerate(con_voz):
        actual = actual + 1 if v else 0
        if actual > mejor:
            mejor, fin = actual, i
    dur_voz = mejor * VENTANA
    if not (MIN_SEG <= dur_voz <= MAX_SEG):
        return {**vacio, "duracion_voz_s": round(dur_voz, 2),
                "motivo": "la vocalizacion no dura lo de un bostezo"}

    tramo = fr[fin - mejor + 1: fin + 1]
    energia_tramo = energia[fin - mejor + 1: fin + 1]
    centroide = float(np.mean([_centroide(f, rate) for f in tramo]))
    zcr = float(np.mean([(np.diff(np.sign(f)) != 0).mean() for f in tramo]))
    joroba = _una_sola_joroba(energia_tramo)

    # cada senal aporta; el score es explicable a proposito
    señales = {
        "duracion_ok": True,
        "sonido_oscuro": centroide < MAX_CENTROIDE,
        "pocas_consonantes": zcr < MAX_ZCR,
        "una_sola_joroba": joroba,
    }
    score = sum(señales.values()) / len(señales)
    return {
        "bostezo": score >= 0.75,
        "score": round(score, 2),
        "duracion_s": round(dur, 2),
        "duracion_voz_s": round(dur_voz, 2),
        "centroide_hz": round(centroide),
        "zcr": round(zcr, 3),
        "señales": señales,
        "motivo": "compatible con bostezo" if score >= 0.75 else "no da el perfil",
    }


def resumen(bostezos: int, minutos: float) -> dict:
    """Traduce la cuenta de bostezos a una senal de fatiga para el reporte."""
    por_minuto = bostezos / max(minutos, 0.1)
    nivel = "alta" if por_minuto >= 2 else "media" if por_minuto >= 1 else "baja"
    return {"bostezos": bostezos, "por_minuto": round(por_minuto, 2),
            "fatiga_por_bostezos": nivel,
            "score": round(min(1.0, por_minuto / 3), 2)}


def es_ruido(pcm16: bytes, umbral: float) -> bool:
    """True si el tramo parece ruido de fondo y no voz.

    Mira dos cosas: que haya poca energia, y que los cruces por cero sean muy
    altos (siseo del motor, viento, estatica) o muy bajos (zumbido constante).
    La voz humana se queda en el medio.
    """
    if not pcm16:
        return True
    x = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < 32:
        return True
    rms = float(np.sqrt((x ** 2).mean()))
    if rms < umbral:
        return True
    zcr = float((np.diff(np.sign(x)) != 0).mean())
    return zcr > 0.35 or zcr < 0.005


class PisoDeRuido:
    """Umbral adaptativo de voz: se calibra solo al ambiente de cada llamada.

    Un camion en ruta con la ventanilla baja y una cabina detenida tienen pisos
    de ruido completamente distintos, asi que un umbral fijo o deja pasar todo
    o se come la voz. Aca el piso se estima solo, mirando el percentil bajo de
    los ultimos segundos de audio: eso es "como suena el silencio aca".

    Hay dos cosas mas que importan para no cortar voz:

    - histeresis: una vez que arranco a hablar, seguimos dejando pasar unos
      frames aunque baje la energia, porque entre silabas hay huecos.
    - piso minimo: si el ambiente esta MUY callado, no queremos que cualquier
      respiracion cuente como voz.
    """

    def __init__(self, factor=2.5, hangover=12, historia=120, minimo=0.004):
        self.factor = factor        # cuantas veces el piso hay que superar
        self.hangover = hangover    # frames que seguimos dejando pasar
        self.minimo = minimo        # piso absoluto de seguridad
        self.historia = historia
        self._rms = []
        self._restantes = 0
        self.piso = 0.0

    def _rms_de(self, pcm16):
        x = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        return float(np.sqrt((x ** 2).mean())) if len(x) else 0.0

    def es_voz(self, pcm16: bytes) -> bool:
        rms = self._rms_de(pcm16)
        self._rms.append(rms)
        if len(self._rms) > self.historia:
            self._rms.pop(0)

        # hasta tener con que calibrar, dejamos pasar todo: preferimos ruido
        # de mas antes que perder las primeras palabras del conductor
        if len(self._rms) < 20:
            return True

        self.piso = float(np.percentile(self._rms, 20))
        umbral = max(self.piso * self.factor, self.minimo)

        if rms > umbral:
            self._restantes = self.hangover
            return True
        if self._restantes > 0:      # veniamos hablando: no cortar entre silabas
            self._restantes -= 1
            return True
        return False

    def estado(self):
        return {"piso": round(self.piso, 4),
                "umbral": round(max(self.piso * self.factor, self.minimo), 4)}

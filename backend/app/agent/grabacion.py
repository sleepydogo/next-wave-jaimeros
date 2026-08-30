"""Graba la llamada a un WAV mezclando las dos voces.

No usamos la grabacion de Twilio: cuesta aparte y solo cubre el telefono. Como
el audio de los dos lados ya pasa por nuestro puente, lo escribimos nosotros y
sirve igual para el probador del navegador.

La mezcla es simple pero correcta en el tiempo: el conductor manda audio de
forma continua, asi que su pista es la linea de tiempo. Cuando habla el agente,
su audio se escribe en la posicion que corresponde a ese instante.
"""
import logging
import os
import wave

import numpy as np

from ..config import AUDIO_DIR

log = logging.getLogger("grabacion")


class Grabador:
    def __init__(self, rate=8000):
        self.rate = rate
        self.conductor = bytearray()
        self.agente = bytearray()

    def del_conductor(self, pcm16: bytes):
        self.conductor.extend(pcm16)

    def del_agente(self, pcm16: bytes):
        # rellenar con silencio hasta donde va el conductor, asi las dos voces
        # quedan alineadas en el tiempo y no una detras de la otra
        faltan = len(self.conductor) - len(self.agente)
        if faltan > 0:
            self.agente.extend(b"\x00" * faltan)
        self.agente.extend(pcm16)

    def guardar(self, call_id: str):
        if not self.conductor and not self.agente:
            return None
        n = max(len(self.conductor), len(self.agente)) // 2
        if n == 0:
            return None

        def pista(b):
            x = np.frombuffer(bytes(b), dtype=np.int16).astype(np.float32)
            return np.pad(x, (0, n - len(x))) if len(x) < n else x[:n]

        # se suman a media escala para que la mezcla no sature
        mezcla = np.clip(pista(self.conductor) * 0.6 + pista(self.agente) * 0.6,
                         -32768, 32767).astype(np.int16)

        os.makedirs(AUDIO_DIR, exist_ok=True)
        ruta = os.path.join(AUDIO_DIR, f"{call_id}.wav")
        with wave.open(ruta, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(mezcla.tobytes())
        log.info("grabacion guardada %s (%.1fs)", ruta, n / self.rate)
        return ruta

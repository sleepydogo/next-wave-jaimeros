"""Nombres de eventos del bus. Un solo lugar para no equivocarse."""

TRUCK_ARRIVED = "truck.arrived"          # el camion entro al geofence del puerto
TRUCK_STOPPED = "truck.stopped"          # parada no planificada en ruta
TRUCK_SLOWDOWN = "truck.slowdown"        # caida abrupta de velocidad
TRUCK_HARSH = "truck.harsh_event"        # frenada / aceleracion brusca
PORT_READY = "port.ready"                # el puerto habilito la carga
CALL_FINISHED = "call.finished"          # el agente termino una llamada
ALERT_RAISED = "alert.raised"            # emergencia -> dispatcher

ALL = [
    TRUCK_ARRIVED, TRUCK_STOPPED, TRUCK_SLOWDOWN, TRUCK_HARSH,
    PORT_READY, CALL_FINISHED, ALERT_RAISED,
]

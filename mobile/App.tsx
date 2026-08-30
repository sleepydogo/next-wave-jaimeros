import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import * as Location from "expo-location";
import { API_URL, driverApi, type DriverTrip } from "./api";

// Los mismos ids que expone GET /driver/triggers. Se dejan fijos para que la
// pantalla no dependa de una request al abrir.
const HITOS = [
  { id: "llegada", titulo: "Llegué al puerto", emoji: "📍" },
  { id: "desvio", titulo: "Me desvié de la ruta", emoji: "↩️" },
  { id: "parada", titulo: "Estoy detenido", emoji: "🛑" },
  { id: "frenada", titulo: "Bajé la velocidad", emoji: "🐢" },
] as const;
import { TripMap } from "./components/trip-map";
import { TripDetailModal } from "./components/trip-detail-modal";

type TripState = "en_ruta" | "en_puerto" | "resuelto";

// Design System tokens (autonomous-logistics-design-system.md)
const DRIVER_ID = "driver_01";

const colors = {
  background: "#F5F5F5",   // --color-surface-muted
  surface:    "#FFFFFF",   // --color-white
  ink:        "#231F20",   // --color-ink
  muted:      "#6B6B6B",   // --color-text-muted
  border:     "#E8E8E8",   // --color-border
  primary:    "#0077FC",   // --color-primary
  primary100: "#E5F1FE",   // --color-primary-100
  waiting:    "#D97706",   // alert amber
  error:      "#C22E2E",   // error red
};

export default function App() {
  const [tripState, setTripState] = useState<TripState>("en_ruta");
  // Arranca con un placeholder para que la pantalla no parpadee, pero se
  // reemplaza por el viaje real apenas responde el backend: los botones mandan
  // trip.id y con "demo-trip" el backend devolvia 404.
  const [trip, setTrip] = useState<DriverTrip>({
    id: "demo-trip",
    container: "MSCU-4471820",
    port_name: "Puerto Buenos Aires - Terminal 4",
    status: "en_ruta",
    driver_id: DRIVER_ID,
    port_lat: -34.5745,
    port_lon: -58.366,
  });
  const [error, setError] = useState<string | null>(null);
  // el saludo usa el nombre real que devuelve el backend
  const nombrePila = (trip.driver_name ?? "").split(" ")[0] || "conductor";

  useEffect(() => {
    let vivo = true;
    const traer = async () => {
      try {
        const r = await driverApi.trip(DRIVER_ID);
        if (vivo && r.trip) setTrip(r.trip);
      } catch {
        // sin backend seguimos con el placeholder; el header ya avisa
      }
    };
    traer();
    const id = setInterval(traer, 10000);
    return () => {
      vivo = false;
      clearInterval(id);
    };
  }, []);
  const [apiConnected, setApiConnected] = useState(false);
  const [sending, setSending] = useState(false);
  const [disparando, setDisparando] = useState<string | null>(null);
  const [ultimoHito, setUltimoHito] = useState<string | null>(null);
  // los disparadores manuales son para la demo, no para el conductor:
  // por eso arrancan escondidos detras de "Debug"
  const [debugAbierto, setDebugAbierto] = useState(false);
  const [location, setLocation] = useState<Location.LocationObject | null>(
    null,
  );
  const [alertVisible, setAlertVisible] = useState(false);

  useEffect(() => {
    if (tripState !== "resuelto") return;

    const timeout = setTimeout(() => setTripState("en_ruta"), 4500);
    return () => clearTimeout(timeout);
  }, [tripState]);

  useEffect(() => {
    driverApi
      .health()
      .then(({ ok }) => setApiConnected(ok))
      .catch((requestError: Error) => setError(requestError.message));
  }, []);

  useEffect(() => {
    let subscription: Location.LocationSubscription | undefined;
    let cancelled = false;

    Location.requestForegroundPermissionsAsync()
      .then(async ({ status }) => {
        if (status !== Location.PermissionStatus.GRANTED || cancelled) return;
        subscription = await Location.watchPositionAsync(
          {
            accuracy: Location.Accuracy.Balanced,
            timeInterval: 15000,
            distanceInterval: 50,
          },
          (nextLocation) => {
            setLocation(nextLocation);
            if (trip) {
              driverApi
                .ping({
                  trip_id: trip.id,
                  lat: nextLocation.coords.latitude,
                  lon: nextLocation.coords.longitude,
                  speed: Math.max(0, (nextLocation.coords.speed ?? 0) * 3.6),
                })
                .catch(() => undefined);
            }
          },
        );
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
      subscription?.remove();
    };
  }, [trip]);

  const isWaiting = tripState === "en_puerto";
  const isResolved = tripState === "resuelto";

  return (
    <SafeAreaView style={styles.pantalla}>
      <ScrollView
        style={styles.scroll}
        contentInsetAdjustmentBehavior="automatic"
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>21AGENTS</Text>
          <Text style={styles.greeting}>Buen viaje, {nombrePila}</Text>
        </View>
        <Pressable
          accessibilityLabel="Abrir ajustes"
          accessibilityRole="button"
          hitSlop={12}
          style={({ pressed }) => [styles.settings, pressed && styles.pressed]}
        >
          <Text style={styles.settingsText}>...</Text>
        </Pressable>
      </View>

      <View style={styles.tripCard}>
        <View style={styles.tripTopline}>
          <Text style={styles.label}>VIAJE ACTIVO</Text>
          <View style={[styles.status, isResolved && styles.statusSuccess]}>
            <View
              style={[styles.statusDot, isResolved && styles.statusDotSuccess]}
            />
            <Text
              style={[
                styles.statusText,
                isResolved && styles.statusTextSuccess,
              ]}
            >
              {isResolved ? "LISTO" : isWaiting ? "EN PUERTO" : "EN RUTA"}
            </Text>
          </View>
        </View>

        <Text style={styles.destination}>
          {isResolved ? "Carga habilitada" : "Puerto de Buenos Aires"}
        </Text>
        <Text style={styles.containerNumber}>
          Contenedor MSCU 482019 · Turno 14:30
        </Text>

        {trip && (
          <TripMap
            destination={{ latitude: trip.port_lat, longitude: trip.port_lon }}
            currentLocation={location?.coords}
            destinationLabel={trip.port_name}
            onMapPress={() => setAlertVisible(true)}
          />
        )}

        <View style={styles.route}>
          <View style={styles.routePoint}>
            <View style={styles.routeDot} />
            <Text style={styles.routeText}>Base operativa</Text>
          </View>
          <View style={styles.routeLine} />
          <View style={styles.routePoint}>
            <View style={[styles.routeDot, styles.routeDotDestination]} />
            <Text style={styles.routeText}>Puerto</Text>
          </View>
        </View>
      </View>

      <View style={styles.messageBlock}>
        <View
          style={[styles.messageMark, isResolved && styles.messageMarkSuccess]}
        />
        <Text style={styles.messageTitle}>
          {isResolved
            ? "Ya puedes cargar"
            : isWaiting
              ? "Esperando habilitación de carga"
              : "En camino al puerto"}
        </Text>
        <Text style={styles.messageBody}>
          {isResolved
            ? "El puerto confirmó tu turno. Dirígete a la zona de carga."
            : isWaiting
              ? "Te avisaremos cuando el puerto habilite tu turno."
              : "Mantén la app abierta. Actualizamos tu posición automáticamente."}
        </Text>
      </View>

      <View style={styles.hitos}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={debugAbierto ? "Cerrar debug" : "Abrir debug"}
          onPress={() => setDebugAbierto((v) => !v)}
          style={styles.debugHeader}
        >
          <View>
            <Text style={styles.hitosTitulo}>Debug</Text>
            {debugAbierto && (
              <Text style={styles.hitosAyuda}>
                Cada botón dispara una llamada del agente.
              </Text>
            )}
          </View>
          <Text style={styles.debugChevron}>{debugAbierto ? "▲" : "▼"}</Text>
        </Pressable>

        {debugAbierto &&
          HITOS.map((h) => (
          <Pressable
            key={h.id}
            accessibilityRole="button"
            accessibilityLabel={h.titulo}
            disabled={disparando !== null || !trip}
            onPress={async () => {
              if (!trip) return;
              setDisparando(h.id);
              setUltimoHito(null);
              try {
                const r = await driverApi.trigger(trip.id, h.id);
                setUltimoHito(`${r.titulo} · el agente te está llamando`);
                setError(null);
              } catch (requestError) {
                setError((requestError as Error).message);
              } finally {
                setDisparando(null);
              }
            }}
            style={({ pressed }) => [
              styles.hito,
              pressed && styles.actionPressed,
              disparando !== null && styles.hitoDeshabilitado,
              disparando === h.id && styles.hitoActivo,
            ]}
          >
            {disparando === h.id ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Text style={styles.hitoEmoji}>{h.emoji}</Text>
            )}
            <Text
              style={[
                styles.hitoTexto,
                disparando === h.id && styles.hitoTextoActivo,
              ]}
            >
              {disparando === h.id ? "Avisando al agente..." : h.titulo}
            </Text>
          </Pressable>
        ))}
        {ultimoHito ? <Text style={styles.hitoOk}>{ultimoHito}</Text> : null}
      </View>

      <View style={styles.footer}>
        {isWaiting ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Avisar que ya estoy listo para cargar"
            disabled={sending || !trip}
            onPress={async () => {
              if (!trip) return;
              setSending(true);
              try {
                await driverApi.ack(trip.id);
                setTripState("resuelto");
                setError(null);
              } catch (requestError) {
                setError((requestError as Error).message);
              } finally {
                setSending(false);
              }
            }}
            style={({ pressed }) => [
              styles.action,
              pressed && styles.actionPressed,
            ]}
          >
            <Text style={styles.actionText}>
              {sending ? "Enviando..." : "Ya estoy listo"}
            </Text>
          </Pressable>
        ) : (
          <Text style={styles.footerHint}>
            {isResolved
              ? "Estado actualizado"
              : "Posición actualizada hace un momento"}
          </Text>
        )}
        <Text style={styles.tripId}>
          VIAJE {trip.id.toUpperCase()} ·{" "}
          {apiConnected ? "BACKEND CONECTADO" : "BACKEND SIN CONEXIÓN"}
        </Text>
        {/* visible a proposito: si falla la conexion, lo primero que hay que
            saber es contra que url esta pegando la app */}
        <Text style={styles.apiUrl}>{API_URL}</Text>
        {error && <Text style={styles.error}>{error}</Text>}
      </View>

      <StatusBar style="auto" />
      <TripDetailModal
        visible={alertVisible}
        onClose={() => setAlertVisible(false)}
        trip={{
          container: trip.container,
          destination: trip.port_name,
          status: "Alerta operativa",
          speed: location?.coords.speed ? location.coords.speed * 3.6 : 0,
          updatedAt: "ahora",
        }}
      />
      </ScrollView>
    </SafeAreaView>
  );
}

const sombra = {
  shadowColor: "#231F20",
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.06,
  shadowRadius: 10,
  elevation: 2,
};

const styles = StyleSheet.create({
  // El color va en la pantalla, no en el contenido: si esta solo en el
  // contentContainer, se corta donde termina el contenido.
  pantalla: {
    flex: 1,
    backgroundColor: colors.background,
    // en Android SafeAreaView no cubre la barra de estado
    paddingTop: Platform.OS === "android" ? 28 : 0,
  },
  scroll: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    // flexGrow, NO flex: con flex:1 el contenido queda clavado a la altura de
    // la pantalla y el ScrollView deja de scrollear
    flexGrow: 1,
    padding: 24,
    // aire abajo para que el ultimo boton no quede pegado al borde
    paddingBottom: 48,
    gap: 28,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 12,
  },
  eyebrow: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 1.4,
  },
  greeting: {
    color: colors.ink,
    fontSize: 20,
    fontWeight: "600",
    marginTop: 6,
  },
  settings: {
    alignItems: "center",
    borderColor: colors.border,
    borderRadius: 20,
    borderWidth: 1,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  settingsText: {
    color: colors.muted,
    fontSize: 16,
    fontWeight: "600",
    letterSpacing: 2,
  },
  tripCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderCurve: "continuous",
    borderRadius: 18,
    borderWidth: 1,
    gap: 14,
    padding: 20,
    ...sombra,
  },
  tripTopline: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  label: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 1.1,
  },
  status: {
    alignItems: "center",
    backgroundColor: "#FFF8EC",
    borderRadius: 20,
    flexDirection: "row",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  statusSuccess: {
    backgroundColor: colors.primary100,
  },
  statusDot: {
    backgroundColor: colors.waiting,
    borderRadius: 4,
    height: 7,
    width: 7,
  },
  statusDotSuccess: {
    backgroundColor: colors.primary,
  },
  statusText: {
    color: colors.waiting,
    fontSize: 10,
    fontWeight: "600",
    letterSpacing: 0.5,
  },
  statusTextSuccess: {
    color: colors.primary,
  },
  destination: {
    color: colors.ink,
    fontSize: 24,
    fontWeight: "600",
    lineHeight: 30,
  },
  containerNumber: {
    color: colors.muted,
    fontSize: 13,
  },
  route: {
    gap: 0,
    marginTop: 12,
  },
  routePoint: {
    alignItems: "center",
    flexDirection: "row",
    gap: 10,
  },
  routeDot: {
    backgroundColor: colors.primary,
    borderColor: colors.surface,
    borderRadius: 6,
    borderWidth: 2,
    height: 12,
    width: 12,
  },
  routeDotDestination: {
    backgroundColor: colors.waiting,
  },
  routeLine: {
    backgroundColor: colors.border,
    height: 18,
    marginLeft: 5,
    width: 2,
  },
  routeText: {
    color: colors.muted,
    fontSize: 13,
  },
  messageBlock: {
    gap: 10,
    paddingHorizontal: 4,
  },
  messageMark: {
    backgroundColor: colors.waiting,
    borderRadius: 3,
    height: 6,
    width: 34,
  },
  messageMarkSuccess: {
    backgroundColor: colors.primary,
  },
  messageTitle: {
    color: colors.ink,
    fontSize: 28,
    fontWeight: "600",
    lineHeight: 34,
  },
  messageBody: {
    color: colors.muted,
    fontSize: 16,
    lineHeight: 23,
    maxWidth: 340,
  },
  footer: {
    alignItems: "center",
    gap: 16,
    paddingTop: 8,
  },
  action: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderCurve: "continuous",
    borderRadius: 999,
    minHeight: 56,
    justifyContent: "center",
    paddingHorizontal: 24,
    width: "100%",
  },
  hitos: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 18,
    borderWidth: 1,
    gap: 9,
    padding: 18,
    ...sombra,
  },
  debugHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  debugChevron: {
    color: colors.muted,
    fontSize: 12,
  },
  hitosTitulo: {
    color: colors.ink,
    fontSize: 15,
    fontWeight: "600",
  },
  hitosAyuda: {
    color: colors.muted,
    fontSize: 12.5,
    marginBottom: 4,
  },
  hito: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 15,
    paddingHorizontal: 16,
  },
  hitoDeshabilitado: {
    opacity: 0.45,
  },
  // el que se toco se mantiene legible y marcado mientras espera
  hitoActivo: {
    opacity: 1,
    backgroundColor: colors.primary100,
    borderColor: colors.primary,
  },
  hitoEmoji: {
    fontSize: 17,
  },
  hitoTextoActivo: {
    color: colors.primary,
    fontWeight: "600",
  },
  hitoTexto: {
    color: colors.ink,
    fontSize: 14.5,
    fontWeight: "500",
  },
  hitoOk: {
    color: colors.primary,
    backgroundColor: colors.primary100,
    borderRadius: 10,
    fontSize: 12.5,
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  actionPressed: {
    opacity: 0.82,
  },
  actionText: {
    color: colors.surface,
    fontSize: 17,
    fontWeight: "600",
  },
  footerHint: {
    color: colors.muted,
    fontSize: 13,
  },
  tripId: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 1,
  },
  pressed: {
    opacity: 0.65,
  },
  apiUrl: {
    color: colors.muted,
    fontSize: 10,
    marginTop: 2,
    textAlign: "center",
  },
  error: {
    color: "#C22E2E",
    fontSize: 13,
    textAlign: "center",
  },
});

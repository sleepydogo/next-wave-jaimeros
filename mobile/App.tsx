import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import * as Location from "expo-location";
import { driverApi, type DriverTrip } from "./api";
import { TripMap } from "./components/trip-map";
import { TripDetailModal } from "./components/trip-detail-modal";

type TripState = "en_ruta" | "en_puerto" | "resuelto";

const colors = {
  background: "#FAFAFA",
  surface: "#FFFFFF",
  ink: "#111111",
  muted: "#6B6B6B",
  border: "#E5E5E5",
  accent: "#0A5C8C",
  success: "#1E8E5A",
  waiting: "#B87A0A",
};

export default function App() {
  const [tripState, setTripState] = useState<TripState>("en_ruta");
  const [trip] = useState<DriverTrip>({
    id: "demo-trip",
    container: "MSCU-4471820",
    port_name: "Puerto Buenos Aires - Terminal 4",
    status: "en_ruta",
    driver_id: "d1",
    port_lat: -34.5745,
    port_lon: -58.366,
  });
  const [error, setError] = useState<string | null>(null);
  const [apiConnected, setApiConnected] = useState(false);
  const [sending, setSending] = useState(false);
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
    <ScrollView
      contentInsetAdjustmentBehavior="automatic"
      contentContainerStyle={styles.content}
    >
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>NEXTWAVE</Text>
          <Text style={styles.greeting}>Buen viaje, Carlos</Text>
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
            route={[
              { latitude: -34.62, longitude: -58.48 },
              { latitude: -34.6, longitude: -58.43 },
              { latitude: trip.port_lat, longitude: trip.port_lon },
            ]}
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
          VIAJE NW-2048 ·{" "}
          {apiConnected ? "BACKEND CONECTADO" : "BACKEND SIN CONEXIÓN"}
        </Text>
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
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
    backgroundColor: colors.background,
    padding: 24,
    gap: 28,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 12,
  },
  eyebrow: {
    color: colors.accent,
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
    borderRadius: 16,
    borderWidth: 1,
    gap: 14,
    padding: 20,
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
    backgroundColor: "#FFF6E5",
    borderRadius: 20,
    flexDirection: "row",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  statusSuccess: {
    backgroundColor: "#E9F6EF",
  },
  statusDot: {
    backgroundColor: colors.waiting,
    borderRadius: 4,
    height: 7,
    width: 7,
  },
  statusDotSuccess: {
    backgroundColor: colors.success,
  },
  statusText: {
    color: colors.waiting,
    fontSize: 10,
    fontWeight: "600",
    letterSpacing: 0.5,
  },
  statusTextSuccess: {
    color: colors.success,
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
  map: {
    borderRadius: 12,
    height: 180,
    marginTop: 4,
    overflow: "hidden",
    width: "100%",
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
    backgroundColor: colors.accent,
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
    backgroundColor: colors.success,
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
    marginTop: "auto",
    paddingBottom: 8,
  },
  action: {
    alignItems: "center",
    backgroundColor: colors.accent,
    borderCurve: "continuous",
    borderRadius: 12,
    minHeight: 56,
    justifyContent: "center",
    paddingHorizontal: 24,
    width: "100%",
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
  error: {
    color: "#C22E2E",
    fontSize: 13,
    textAlign: "center",
  },
});

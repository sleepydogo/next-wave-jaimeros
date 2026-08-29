import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

export interface TripDetail {
  container: string;
  destination: string;
  status: string;
  speed?: number;
  updatedAt?: string;
}

interface TripDetailModalProps {
  visible: boolean;
  trip: TripDetail | null;
  onClose: () => void;
}

export function TripDetailModal({
  visible,
  trip,
  onClose,
}: TripDetailModalProps) {
  if (!trip) return null;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.handle} />
          <View style={styles.header}>
            <Text style={styles.title}>Detalle del viaje</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Cerrar detalle"
              onPress={onClose}
            >
              <Text style={styles.close}>Cerrar</Text>
            </Pressable>
          </View>
          <Text style={styles.destination}>{trip.destination}</Text>
          <Text style={styles.muted}>{trip.container}</Text>
          <View style={styles.stats}>
            <Stat label="Estado" value={trip.status} />
            <Stat label="Velocidad" value={`${trip.speed ?? 0} km/h`} />
          </View>
          {trip.updatedAt && (
            <Text style={styles.muted}>Actualizado {trip.updatedAt}</Text>
          )}
        </View>
      </View>
    </Modal>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    backgroundColor: "rgba(17,17,17,0.35)",
    flex: 1,
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#FFFFFF",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    gap: 16,
    padding: 24,
    paddingBottom: 36,
  },
  handle: {
    alignSelf: "center",
    backgroundColor: "#E5E5E5",
    borderRadius: 4,
    height: 5,
    width: 36,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  title: { color: "#111111", fontSize: 20, fontWeight: "600" },
  close: { color: "#0A5C8C", fontSize: 15, fontWeight: "600" },
  destination: { color: "#111111", fontSize: 24, fontWeight: "600" },
  muted: { color: "#6B6B6B", fontSize: 14 },
  stats: {
    borderColor: "#E5E5E5",
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-around",
    padding: 16,
  },
  label: { color: "#6B6B6B", fontSize: 12 },
  value: { color: "#111111", fontSize: 16, fontWeight: "600", marginTop: 4 },
});

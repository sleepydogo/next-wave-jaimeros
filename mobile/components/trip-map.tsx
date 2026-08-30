import MapView, {
  Circle,
  Marker,
  Polyline,
  type Region,
} from "react-native-maps";
import { StyleSheet, View } from "react-native";

export interface MapCoordinate {
  latitude: number;
  longitude: number;
}

export interface TripMapProps {
  currentLocation?: MapCoordinate;
  destination: MapCoordinate;
  route?: MapCoordinate[];
  destinationLabel?: string;
  followUser?: boolean;
  onMapPress?: () => void;
  height?: number;
}

// mismos tokens que la app, para que el mapa no parezca de otra aplicacion
const PRIMARY = "#0077FC";
const INK = "#231F20";

/** Encuadre que entra el camion y el puerto, con aire alrededor. */
function encuadre(a: MapCoordinate, b?: MapCoordinate): Region {
  if (!b) return { ...a, latitudeDelta: 0.06, longitudeDelta: 0.06 };
  const latitude = (a.latitude + b.latitude) / 2;
  const longitude = (a.longitude + b.longitude) / 2;
  const dLat = Math.abs(a.latitude - b.latitude) * 1.8;
  const dLon = Math.abs(a.longitude - b.longitude) * 1.8;
  return {
    latitude,
    longitude,
    latitudeDelta: Math.max(dLat, 0.03),
    longitudeDelta: Math.max(dLon, 0.03),
  };
}

export function TripMap({
  currentLocation,
  destination,
  route = [],
  destinationLabel = "Destino",
  followUser = false,
  onMapPress,
  height = 220,
}: TripMapProps) {
  const path =
    route.length > 1
      ? route
      : currentLocation
        ? [currentLocation, destination]
        : [];

  return (
    <View style={[styles.marco, { height }]}>
      <MapView
        style={StyleSheet.absoluteFill}
        initialRegion={encuadre(destination, currentLocation)}
        showsUserLocation
        showsMyLocationButton={false}
        showsCompass={false}
        followsUserLocation={followUser}
        toolbarEnabled={false}
        onPress={onMapPress}
      >
        {/* el geofence de 800 m: es el que dispara la llamada de llegada */}
        <Circle
          center={destination}
          radius={800}
          fillColor="rgba(0,119,252,0.10)"
          strokeColor="rgba(0,119,252,0.45)"
          strokeWidth={1.5}
        />
        <Marker
          coordinate={destination}
          title={destinationLabel}
          pinColor={PRIMARY}
        />
        {currentLocation && (
          <Marker coordinate={currentLocation} title="Tu ubicación" pinColor={INK} />
        )}
        {path.length > 1 && (
          <Polyline
            coordinates={path}
            strokeColor={PRIMARY}
            strokeWidth={4}
            lineCap="round"
            lineDashPattern={[1, 8]}
          />
        )}
      </MapView>
    </View>
  );
}

const styles = StyleSheet.create({
  marco: {
    borderRadius: 16,
    overflow: "hidden",
    width: "100%",
    borderWidth: 1,
    borderColor: "#E8E8E8",
    backgroundColor: "#EDEDED",
  },
});

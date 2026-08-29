import MapView, {
  Circle,
  Marker,
  Polyline,
  type Region,
} from "react-native-maps";
import { StyleSheet } from "react-native";

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
}

const DEFAULT_DELTA = { latitudeDelta: 0.08, longitudeDelta: 0.08 };

export function TripMap({
  currentLocation,
  destination,
  route = [],
  destinationLabel = "Destino",
  followUser = false,
  onMapPress,
}: TripMapProps) {
  const initialRegion: Region = {
    ...destination,
    ...DEFAULT_DELTA,
  };
  const path =
    route.length > 1
      ? route
      : currentLocation
        ? [currentLocation, destination]
        : [];

  return (
    <MapView
      style={styles.map}
      initialRegion={initialRegion}
      showsUserLocation
      showsMyLocationButton
      followsUserLocation={followUser}
      toolbarEnabled={false}
      onPress={onMapPress}
    >
      <Marker coordinate={destination} title={destinationLabel} />
      <Circle
        center={destination}
        radius={800}
        fillColor="rgba(10,92,140,0.08)"
        strokeColor="rgba(10,92,140,0.35)"
      />
      {currentLocation && (
        <Marker
          coordinate={currentLocation}
          pinColor="#0A5C8C"
          title="Tu ubicación"
        />
      )}
      {path.length > 1 && (
        <Polyline
          coordinates={path}
          strokeColor="#0A5C8C"
          strokeWidth={4}
          lineCap="round"
        />
      )}
    </MapView>
  );
}

const styles = StyleSheet.create({ map: { height: 240, width: "100%" } });

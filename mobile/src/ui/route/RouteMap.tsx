import { useRef, useState } from "react";
import { Pressable, View } from "react-native";
import type { PlanStop } from "../../domain/models";
import { useTheme } from "../theme/ThemeProvider";
import { Copy } from "../components/Typography";

export function RouteMap({
  stops,
  onPin,
}: {
  stops: readonly PlanStop[];
  onPin?: (x: number, y: number) => void;
}) {
  const { theme, isDark } = useTheme();
  const mapRef = useRef<View>(null);
  const [width, setWidth] = useState(342);
  const points = stops
    .map((stop, index) => ({ ...stop, index }))
    .filter((stop) => stop.x !== null && stop.y !== null);
  const height = onPin ? 220 : 155;
  return (
    <View
      style={{
        borderRadius: 20,
        overflow: "hidden",
        borderWidth: 1,
        borderColor: theme.line,
        backgroundColor: isDark ? "#293e36" : "#e8eae0",
      }}
    >
      <Pressable
        disabled={!onPin}
        accessibilityRole={onPin ? "button" : "image"}
        accessibilityLabel={
          onPin
            ? "Illustrative map. Tap to drop a pin"
            : `Illustrative Indiranagar map with ${points.length} places`
        }
        onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
        ref={mapRef}
        onPress={(event) => {
          const { pageX, pageY } = event.nativeEvent;
          mapRef.current?.measureInWindow(
            (left, top, measuredWidth, measuredHeight) => {
              onPin?.(
                Math.max(
                  12,
                  Math.min(330, ((pageX - left) / measuredWidth) * 342),
                ),
                Math.max(
                  12,
                  Math.min(248, ((pageY - top) / measuredHeight) * 260),
                ),
              );
            },
          );
        }}
        style={{ height }}
      >
        <View pointerEvents="none" style={{ flex: 1 }}>
          {[15, 95, 188, 278].map((x, i) => (
            <View
              key={x}
              style={{
                position: "absolute",
                left: `${(x / 342) * 100}%`,
                top: 10 + (i % 2) * 35,
                width: "16%",
                height: "75%",
                borderRadius: 9,
                backgroundColor: isDark ? "#344b3e" : "#d9e2d1",
              }}
            />
          ))}
          {[80, 170, 260].map((x) => (
            <View
              key={x}
              style={{
                position: "absolute",
                left: `${(x / 342) * 100}%`,
                width: 10,
                height: "100%",
                backgroundColor: isDark ? "#506157" : "#fffdf5",
              }}
            />
          ))}
          {[78, 160, 241].map((y) => (
            <View
              key={y}
              style={{
                position: "absolute",
                top: `${(y / 260) * 100}%`,
                height: 9,
                width: "100%",
                backgroundColor: isDark ? "#506157" : "#fffdf5",
              }}
            />
          ))}
          <Copy
            size={8}
            color={isDark ? "#9fb2a3" : "#7d8b7b"}
            style={{
              position: "absolute",
              left: "30%",
              top: "10%",
              letterSpacing: 1,
            }}
          >
            INDIRANAGAR
          </Copy>
          <Copy
            size={8}
            color={isDark ? "#9fb2a3" : "#7d8b7b"}
            style={{ position: "absolute", left: "30%", top: "23%" }}
          >
            CMH ROAD
          </Copy>
          <Copy
            size={8}
            color={isDark ? "#9fb2a3" : "#7d8b7b"}
            style={{ position: "absolute", left: "57%", top: "70%" }}
          >
            DEFENCE COLONY
          </Copy>
          {points.slice(1).map((point, i) => {
            const prev = points[i];
            const x = (prev.x! / 342) * width,
              y = (prev.y! / 260) * height;
            const dx = (point.x! / 342) * width - x,
              dy = (point.y! / 260) * height - y;
            const length = Math.hypot(dx, dy);
            return (
              <View
                key={`line-${point.id}`}
                style={{
                  position: "absolute",
                  left: x + dx / 2 - length / 2,
                  top: y + dy / 2 - 1,
                  width: length,
                  height: 2,
                  backgroundColor: "#bb7152",
                  transform: [{ rotate: `${Math.atan2(dy, dx)}rad` }],
                }}
              />
            );
          })}
          {points.map((point) => (
            <View
              key={point.id}
              style={{
                position: "absolute",
                left: (point.x! / 342) * width - 12,
                top: (point.y! / 260) * height - 12,
                width: 24,
                height: 24,
                borderRadius: 12,
                backgroundColor: "#ad644a",
                borderWidth: 2,
                borderColor: "white",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Copy size={10} color="white">
                {onPin || stops.length === 1 ? "•" : point.index + 1}
              </Copy>
            </View>
          ))}
        </View>
      </Pressable>
      <View style={{ padding: 10 }}>
        <Copy size={10} color={isDark ? "#c9dacd" : "#40544b"}>
          {onPin
            ? "Tap anywhere to drop a pin"
            : points.length
              ? `${points.length} ${points.length === 1 ? "meeting place" : "places · route preview"}`
              : "Your places will appear here"}{" "}
          · illustrative map
        </Copy>
      </View>
    </View>
  );
}

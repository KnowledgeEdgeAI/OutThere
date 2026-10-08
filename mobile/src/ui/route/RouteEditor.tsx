import { useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  View,
} from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { PlanStop } from "../../domain/models";
import { samplePlaces } from "../../data/places";
import { useTheme } from "../theme/ThemeProvider";
import { Action, Chip, Field, SmallButton } from "../components/Controls";
import { Row, styles } from "../components/Layout";
import { Copy } from "../components/Typography";
import { Icon } from "../components/Icon";
import { RouteMap } from "./RouteMap";

let stopId = 0;
export function emptyStop(): PlanStop {
  return {
    id: `stop-${Date.now()}-${stopId++}`,
    place: "",
    address: "",
    startsAt: "",
    x: null,
    y: null,
  };
}
const dateText = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const timeText = (date: Date) =>
  `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;

export function RouteEditor({
  stops,
  onChange,
}: {
  stops: PlanStop[];
  onChange: (stops: PlanStop[]) => void;
}) {
  const { theme, isDark } = useTheme();
  const insets = useSafeAreaInsets();
  const [sheet, setSheet] = useState<{
    kind: "place" | "time";
    index: number;
  } | null>(null);
  const [selected, setSelected] = useState<PlanStop | null>(null);
  const [query, setQuery] = useState("");
  const [pinMode, setPinMode] = useState(false);
  const [pinName, setPinName] = useState("Pinned place");
  const [day, setDay] = useState("");
  const [clock, setClock] = useState("");
  const [picker, setPicker] = useState<"date" | "time" | null>(null);
  const [error, setError] = useState("");
  function open(kind: "place" | "time", index: number, route = stops) {
    const stop = route[index];
    setSelected(stop.place ? { ...stop } : null);
    setQuery("");
    setPinMode(false);
    setPinName(
      stop.address.startsWith("Custom pin") ? stop.place : "Pinned place",
    );
    setError("");
    setPicker(null);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(17, 0, 0, 0);
    const initial = new Date(
      stop.startsAt ||
        (route[index - 1]?.startsAt
          ? Date.parse(route[index - 1].startsAt) + 3600000
          : tomorrow.getTime()),
    );
    setDay(dateText(initial));
    setClock(timeText(initial));
    setSheet({ kind, index });
  }
  function save() {
    if (!sheet) return;
    const stop = stops[sheet.index];
    let next: PlanStop;
    if (sheet.kind === "place") {
      if (!selected) return;
      next = {
        ...stop,
        place: selected.address.startsWith("Custom pin")
          ? pinName.trim() || "Pinned place"
          : selected.place,
        address: selected.address,
        x: selected.x,
        y: selected.y,
      };
    } else {
      const date = new Date(`${day}T${clock}:00`),
        time = date.getTime();
      const prev = stops[sheet.index - 1],
        following = stops[sheet.index + 1];
      const message =
        !/^\d{4}-\d{2}-\d{2}$/.test(day) ||
        !/^\d{2}:\d{2}$/.test(clock) ||
        !Number.isFinite(time) ||
        dateText(date) !== day ||
        timeText(date) !== clock
          ? "Choose a valid date and arrival time."
          : time <= Date.now()
            ? "Choose an arrival time in the future."
            : prev?.startsAt && time <= Date.parse(prev.startsAt)
              ? "Choose a time after the previous stop."
              : following?.startsAt && time >= Date.parse(following.startsAt)
                ? "Choose a time before the next stop, or change its time first."
                : "";
      if (message) {
        setError(message);
        return;
      }
      next = { ...stop, startsAt: date.toISOString() };
    }
    onChange(stops.map((item, index) => (index === sheet.index ? next : item)));
    setSheet(null);
  }
  const results = samplePlaces.filter((place) =>
    `${place.place} ${place.address}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  const pickerDate = new Date(`${day}T${clock}:00`);
  return (
    <>
      <Copy size={18} style={{ marginTop: 10, fontWeight: "500" }}>
        When & where
      </Copy>
      <View>
        <View>
          {stops.map((stop, index) => (
            <View
              key={stop.id}
              style={{
                borderBottomWidth: index < stops.length - 1 ? 1 : 0,
                borderColor: theme.line,
                paddingTop: 8,
                paddingBottom: index < stops.length - 1 ? 8 : 0,
              }}
            >
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Choose place for stop ${index + 1}`}
                onPress={() => open("place", index)}
                style={{ paddingVertical: 12, minHeight: 44 }}
              >
                <Row>
                  <Icon name="pin" size={19} color={theme.muted} />
                  <View style={{ flex: 1 }}>
                    <Copy muted={!stop.place}>
                      {stop.place || "Search a place or drop a pin"}
                    </Copy>
                    {!!stop.address && (
                      <Copy size={11} muted>
                        {stop.address}
                      </Copy>
                    )}
                  </View>
                </Row>
              </Pressable>
              <Row>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Choose arrival time for stop ${index + 1}`}
                  onPress={() => open("time", index)}
                  style={{ flex: 1, paddingVertical: 12, minHeight: 44 }}
                >
                  <Row>
                    <Icon name="clock" size={19} color={theme.muted} />
                    <Copy size={14} muted={!stop.startsAt}>
                      {stop.startsAt
                        ? new Date(stop.startsAt).toLocaleString(undefined, {
                            month: "short",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          })
                        : "Choose date & time"}
                    </Copy>
                  </Row>
                </Pressable>
                {stops.length > 1 && (
                  <SmallButton
                    title={`Remove stop ${index + 1}`}
                    ghost
                    onPress={() =>
                      onChange(stops.filter((item) => item.id !== stop.id))
                    }
                  />
                )}
              </Row>
            </View>
          ))}
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Add another stop"
          onPress={() => {
            const next = [...stops, emptyStop()];
            onChange(next);
            open("place", next.length - 1, next);
          }}
          style={{
            minHeight: 44,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Row>
            <View style={{ flex: 1, height: 1, backgroundColor: theme.line }} />
            <Icon name="add" color={theme.accent} />
            <View style={{ flex: 1, height: 1, backgroundColor: theme.line }} />
          </Row>
        </Pressable>
      </View>
      <RouteMap stops={stops} />
      {sheet && (
        <Modal
          visible={!!sheet}
          transparent
          animationType="slide"
          onRequestClose={() => setSheet(null)}
        >
          <KeyboardAvoidingView
            behavior={Platform.OS === "ios" ? "padding" : "height"}
            style={{
              flex: 1,
              justifyContent: "flex-end",
              backgroundColor: "#10171488",
              paddingTop: insets.top + 24,
            }}
          >
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Dismiss picker"
              onPress={() => setSheet(null)}
              style={{ flex: 1 }}
            />
            <View
              accessibilityViewIsModal
              style={{
                maxHeight: "88%",
                width: "100%",
                maxWidth: 520,
                alignSelf: "center",
                backgroundColor: theme.background,
                borderTopLeftRadius: 28,
                borderTopRightRadius: 28,
                paddingBottom: insets.bottom,
              }}
            >
              <ScrollView
                keyboardShouldPersistTaps="handled"
                contentContainerStyle={{ padding: 22, gap: 14 }}
              >
                <View
                  style={{
                    width: 35,
                    height: 4,
                    backgroundColor: theme.line,
                    borderRadius: 5,
                    alignSelf: "center",
                  }}
                />
                <Row>
                  <Copy
                    size={24}
                    style={{ flex: 1, fontWeight: "500", letterSpacing: -0.8 }}
                  >
                    {sheet?.kind === "place"
                      ? sheet.index
                        ? "Find your next stop"
                        : "Find your place"
                      : "When to arrive?"}
                  </Copy>
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Close picker"
                    onPress={() => setSheet(null)}
                    style={{
                      minWidth: 44,
                      minHeight: 44,
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Icon name="close" />
                  </Pressable>
                </Row>
                <Copy size={11} muted>
                  Stop {(sheet?.index ?? 0) + 1} ·{" "}
                  {sheet?.kind === "place"
                    ? "Bengaluru"
                    : stops[sheet?.index ?? 0]?.place || "Your meeting place"}
                </Copy>
                {sheet?.kind === "place" ? (
                  <>
                    <Field
                      accessibilityLabel="Search sample places"
                      placeholder="Search places, cafés, parks…"
                      value={query}
                      onChangeText={setQuery}
                    />
                    {!pinMode && (
                      <>
                        <Copy size={11} muted>
                          Sample places · Indiranagar
                        </Copy>
                        {results.map((place) => (
                          <Pressable
                            key={place.place}
                            accessibilityRole="button"
                            accessibilityState={{
                              selected: selected?.place === place.place,
                            }}
                            onPress={() =>
                              setSelected({ ...stops[sheet.index], ...place })
                            }
                            style={{
                              paddingVertical: 13,
                              borderBottomWidth: 1,
                              borderColor: theme.line,
                            }}
                          >
                            <Row>
                              <Icon name="pin" color={theme.accent} />
                              <View style={{ flex: 1 }}>
                                <Copy size={13} bold>
                                  {place.place}
                                </Copy>
                                <Copy size={10} muted>
                                  {place.address}
                                </Copy>
                              </View>
                              {selected?.place === place.place && (
                                <Icon name="check" />
                              )}
                            </Row>
                          </Pressable>
                        ))}
                        {!results.length && (
                          <Copy size={12} muted>
                            No sample places found. Try “coffee” or drop a pin.
                          </Copy>
                        )}
                      </>
                    )}
                    <SmallButton
                      title={
                        pinMode ? "Back to place search" : "Drop a pin instead"
                      }
                      ghost
                      onPress={() => setPinMode(!pinMode)}
                    />
                    {pinMode && (
                      <>
                        <RouteMap
                          stops={selected ? [selected] : []}
                          onPin={(x, y) =>
                            setSelected({
                              ...stops[sheet.index],
                              place: pinName.trim() || "Pinned place",
                              address: "Custom pin · Indiranagar demo map",
                              x,
                              y,
                            })
                          }
                        />
                        <Field
                          accessibilityLabel="Pin name"
                          placeholder="e.g. Meet at the park gate"
                          value={pinName}
                          onChangeText={setPinName}
                          maxLength={120}
                        />
                      </>
                    )}
                    <Copy size={12} muted>
                      {selected
                        ? `Selected: ${selected.address.startsWith("Custom pin") ? pinName : selected.place}`
                        : "Choose a sample place or tap the map."}
                    </Copy>
                    <Action
                      title="Use this place"
                      disabled={!selected}
                      onPress={save}
                    />
                    <Copy size={10} muted>
                      Illustrative map · sample search results
                    </Copy>
                  </>
                ) : (
                  <>
                    <View style={styles.wrap}>
                      {[0, 1, 2].map((offset) => {
                        const date = new Date();
                        date.setDate(date.getDate() + offset);
                        return (
                          <Chip
                            key={offset}
                            title={
                              offset === 0
                                ? "Today"
                                : offset === 1
                                  ? "Tomorrow"
                                  : date.toLocaleDateString(undefined, {
                                      weekday: "short",
                                    })
                            }
                            active={day === dateText(date)}
                            onPress={() => {
                              setDay(dateText(date));
                              setError("");
                            }}
                          />
                        );
                      })}
                    </View>
                    {Platform.OS === "web" ? (
                      <>
                        <Copy size={12} muted>
                          Another date · YYYY-MM-DD
                        </Copy>
                        <Field
                          accessibilityLabel="Arrival date"
                          value={day}
                          onChangeText={setDay}
                          placeholder="YYYY-MM-DD"
                        />
                        <Copy size={12} muted>
                          Arrival time · HH:mm
                        </Copy>
                        <Field
                          accessibilityLabel="Arrival time"
                          value={clock}
                          onChangeText={setClock}
                          placeholder="HH:mm"
                        />
                      </>
                    ) : (
                      <>
                        <Chip title={day} onPress={() => setPicker("date")} />
                        <Chip title={clock} onPress={() => setPicker("time")} />
                        {picker && (
                          <DateTimePicker
                            value={
                              Number.isFinite(pickerDate.getTime())
                                ? pickerDate
                                : new Date()
                            }
                            mode={picker}
                            display={
                              Platform.OS === "ios" ? "spinner" : "default"
                            }
                            minimumDate={
                              picker === "date" ? new Date() : undefined
                            }
                            themeVariant={isDark ? "dark" : "light"}
                            onChange={(_, next) => {
                              if (Platform.OS === "android") setPicker(null);
                              if (next) {
                                if (picker === "date") setDay(dateText(next));
                                else setClock(timeText(next));
                                setError("");
                              }
                            }}
                          />
                        )}
                      </>
                    )}
                    <View style={styles.wrap}>
                      {[
                        "16:00",
                        "17:00",
                        "17:30",
                        "18:00",
                        "18:30",
                        "19:00",
                      ].map((time) => (
                        <Chip
                          key={time}
                          title={time}
                          active={clock === time}
                          onPress={() => {
                            setClock(time);
                            setError("");
                          }}
                        />
                      ))}
                    </View>
                    {!!error && (
                      <Copy color={theme.coral} size={12}>
                        {error}
                      </Copy>
                    )}
                    <Copy size={11} muted>
                      Times follow this device’s time zone. Each stop must
                      arrive after the previous one.
                    </Copy>
                    <Action title="Set arrival time" onPress={save} />
                  </>
                )}
              </ScrollView>
            </View>
          </KeyboardAvoidingView>
        </Modal>
      )}
    </>
  );
}

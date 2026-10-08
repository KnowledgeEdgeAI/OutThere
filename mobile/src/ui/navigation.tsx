import type { IconName } from "./components/Icon";
import { useTheme } from "./theme/ThemeProvider";
import { useAppState } from "../state/AppState";
import { useEffect, useRef, useState, type ComponentProps } from "react";
import { Tabs, router } from "expo-router";
import { Animated, Platform, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Copy } from "./components/Typography";
import { Icon } from "./components/Icon";
import { useReducedMotion } from "./useReducedMotion";
import { themeForMood, type Mood } from "./theme/tokens";
export type RoomTab = "Live" | "Chat" | "Album" | "Money";

type TabBarProps = Parameters<
  NonNullable<ComponentProps<typeof Tabs>["tabBar"]>
>[0];
const items: Record<string, { title: string; icon: IconName }> = {
  index: { title: "Plans", icon: "moon" },
  circles: { title: "Circles", icon: "people" },
  "create-tab": { title: "New", icon: "add" },
  inbox: { title: "Inbox", icon: "inbox" },
  you: { title: "You", icon: "person" },
};
export const planTabItems: Record<
  RoomTab,
  { title: string; icon: IconName; mood: Mood }
> = {
  Live: { title: "Live", icon: "pin", mood: "warm" },
  Chat: { title: "Chat", icon: "chat", mood: "blue" },
  Album: { title: "Album", icon: "album", mood: "gold" },
  Money: { title: "Money", icon: "money", mood: "teal" },
};
const spring = {
  stiffness: 380,
  damping: 30,
  mass: 0.7,
  useNativeDriver: Platform.OS !== "web",
};

function NavItem({
  name,
  selected,
  onPress,
  onLayout,
  item = items[name],
  tint,
  isPlanTab = false,
  reduced,
}: {
  name: string;
  selected: boolean;
  onPress: () => void;
  onLayout: ComponentProps<typeof Pressable>["onLayout"];
  item?: { title: string; icon: IconName };
  tint?: string;
  isPlanTab?: boolean;
  reduced: boolean;
}) {
  const { rippleReply } = useAppState();
  const { theme } = useTheme();
  const [focus] = useState(() => new Animated.Value(selected ? 1 : 0));
  const [press] = useState(() => new Animated.Value(1));
  const create = name === "create-tab";
  useEffect(() => {
    if (reduced) {
      focus.stopAnimation();
      focus.setValue(selected ? 1 : 0);
      return;
    }
    const animation = Animated.spring(focus, {
      ...spring,
      toValue: selected ? 1 : 0,
    });
    animation.start();
    return () => animation.stop();
  }, [selected, reduced, focus]);
  const pressTo = (value: number) => {
    if (reduced) return;
    Animated.spring(press, { ...spring, toValue: value }).start();
  };
  return (
    <Pressable
      accessibilityRole={isPlanTab ? "tab" : "button"}
      accessibilityLabel={item.title}
      accessibilityState={{ selected: !create && selected }}
      aria-selected={isPlanTab ? selected : undefined}
      onLayout={onLayout}
      onPress={onPress}
      onPressIn={() => pressTo(0.92)}
      onPressOut={() => pressTo(1)}
      style={{
        flex: 1,
        minHeight: 54,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: 23,
      }}
    >
      <Animated.View
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: 2,
          transform: [
            {
              scale: Animated.multiply(
                press,
                focus.interpolate({
                  inputRange: [0, 1],
                  outputRange: [1, reduced ? 1 : 1.06],
                }),
              ),
            },
            {
              translateY: focus.interpolate({
                inputRange: [0, 1],
                outputRange: [0, reduced ? 0 : -1],
              }),
            },
          ],
        }}
      >
        {create ? (
          <>
            <View
              style={{
                backgroundColor: theme.accent,
                width: 29,
                height: 29,
                borderRadius: 15,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon name="add" color={theme.background} size={22} />
            </View>
            <Copy size={10} muted>
              New
            </Copy>
          </>
        ) : (
          <>
            <View
              style={{
                height: 29,
                justifyContent: "center",
                opacity: isPlanTab && !selected ? 0.65 : 1,
              }}
            >
              <Icon
                name={item.icon}
                color={tint ?? (selected ? theme.accent : theme.muted)}
              />
            </View>
            <Copy
              size={isPlanTab ? 11 : 10}
              color={selected ? (tint ?? theme.accent) : theme.muted}
            >
              {item.title}
            </Copy>
          </>
        )}
      </Animated.View>
      {name === "inbox" && (
        <View
          style={{
            position: "absolute",
            right: 8,
            top: 0,
            height: 18,
            minWidth: 18,
            borderRadius: 9,
            borderWidth: 2,
            borderColor: theme.background,
            backgroundColor: theme.coral,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Copy size={9} bold color="#fff">
            {rippleReply ? "1" : "2"}
          </Copy>
        </View>
      )}
    </Pressable>
  );
}

function useSlidingSelection(selectedName: string, reduced: boolean) {
  const [frames, setFrames] = useState<
    Record<string, { x: number; width: number }>
  >({});
  const [position] = useState(() => new Animated.Value(0));
  const initialized = useRef(false);
  const frame = frames[selectedName];
  useEffect(() => {
    if (!frame) return;
    if (reduced || !initialized.current) {
      position.stopAnimation();
      position.setValue(frame.x);
      initialized.current = true;
      return;
    }
    const animation = Animated.spring(position, {
      ...spring,
      toValue: frame.x,
    });
    animation.start();
    return () => animation.stop();
  }, [frame, position, reduced]);
  const onLayout =
    (name: string): ComponentProps<typeof Pressable>["onLayout"] =>
    (event) => {
      const { x, width } = event.nativeEvent.layout;
      setFrames((previous) =>
        previous[name]?.x === x && previous[name]?.width === width
          ? previous
          : { ...previous, [name]: { x, width } },
      );
    };
  return { frame, position, onLayout };
}

export function PlanTabBar({
  selected,
  onSelect,
}: {
  selected: RoomTab;
  onSelect: (tab: RoomTab) => void;
}) {
  const { theme, isDark } = useTheme();
  const reduced = useReducedMotion();
  const { frame, position, onLayout } = useSlidingSelection(selected, reduced);
  return (
    <View
      style={{
        width: "100%",
        maxWidth: 520,
        alignSelf: "center",
        paddingHorizontal: 18,
        marginTop: 8,
      }}
    >
      <View
        accessibilityRole="tablist"
        accessibilityLabel="Plan sections"
        style={{
          flexDirection: "row",
          alignItems: "center",
          height: 72,
          padding: 7,
          gap: 2,
          borderRadius: 30,
          backgroundColor: theme.glass,
          borderWidth: 1,
          borderColor: theme.glassEdge,
          boxShadow: "0 10px 30px rgba(37,57,50,.08)",
        }}
      >
        {frame && (
          <Animated.View
            pointerEvents="none"
            style={{
              position: "absolute",
              left: 0,
              top: 8,
              height: 54,
              width: frame.width,
              borderRadius: 23,
              backgroundColor: theme.selected,
              transform: [{ translateX: position }],
            }}
          />
        )}
        {(Object.keys(planTabItems) as RoomTab[]).map((name) => (
          <NavItem
            key={name}
            reduced={reduced}
            name={name}
            item={planTabItems[name]}
            isPlanTab
            tint={themeForMood(isDark, planTabItems[name].mood).accent}
            selected={name === selected}
            onLayout={onLayout(name)}
            onPress={() => onSelect(name)}
          />
        ))}
      </View>
    </View>
  );
}

export function AnimatedTabBar({ state, navigation }: TabBarProps) {
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const selectedName = state.routes[state.index].name;
  const reduced = useReducedMotion();
  const { frame, position, onLayout } = useSlidingSelection(
    selectedName,
    reduced,
  );
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        position: "absolute",
        left: 12,
        right: 12,
        bottom: Math.max(insets.bottom, 18),
        height: 72,
        borderRadius: 30,
        padding: 7,
        gap: 2,
        backgroundColor: theme.glass,
        borderWidth: 1,
        borderColor: theme.glassEdge,
        boxShadow: "0 10px 30px rgba(37,57,50,.08)",
      }}
    >
      {frame && selectedName !== "create-tab" && (
        <Animated.View
          pointerEvents="none"
          style={{
            position: "absolute",
            left: 0,
            top: 8,
            height: 54,
            width: frame.width,
            borderRadius: 23,
            backgroundColor: theme.selected,
            transform: [{ translateX: position }],
          }}
        />
      )}
      {state.routes.map((route, index) => (
        <NavItem
          key={route.key}
          reduced={reduced}
          name={route.name}
          selected={state.index === index && route.name !== "create-tab"}
          onLayout={onLayout(route.name)}
          onPress={() => {
            if (route.name === "create-tab") {
              router.push("/create");
              return;
            }
            const event = navigation.emit({
              type: "tabPress",
              target: route.key,
              canPreventDefault: true,
            });
            if (state.index !== index && !event.defaultPrevented)
              navigation.navigate(route.name);
          }}
        />
      ))}
    </View>
  );
}

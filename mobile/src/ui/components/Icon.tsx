import type { ActivityIcon } from "../../domain/models";
import Ionicons from "@expo/vector-icons/Ionicons";
import type { ComponentProps } from "react";
import { useTheme } from "../theme/ThemeProvider";

export type IconName =
  | ActivityIcon
  | "moon"
  | "people"
  | "add"
  | "inbox"
  | "person"
  | "arrow"
  | "back"
  | "close"
  | "clock"
  | "pin"
  | "chat"
  | "album"
  | "money"
  | "check"
  | "send"
  | "lock"
  | "active"
  | "settings"
  | "ripple"
  | "open";
const icons: Record<IconName, ComponentProps<typeof Ionicons>["name"]> = {
  active: "flash-outline",
  settings: "options-outline",
  ripple: "water-outline",
  open: "sunny-outline",
  moon: "moon-outline",
  people: "people-outline",
  add: "add",
  inbox: "file-tray-outline",
  person: "person-outline",
  arrow: "arrow-forward",
  back: "chevron-back",
  close: "close",
  clock: "time-outline",
  pin: "location-outline",
  coffee: "cafe-outline",
  racket: "tennisball-outline",
  home: "home-outline",
  sun: "sunny-outline",
  leaf: "leaf-outline",
  work: "briefcase-outline",
  chat: "chatbubble-outline",
  album: "images-outline",
  money: "wallet-outline",
  check: "checkmark",
  sparkles: "sparkles-outline",
  send: "arrow-up",
  heart: "heart-outline",
  lock: "lock-closed-outline",
};
export function Icon({
  name,
  size = 22,
  color,
}: {
  name: IconName;
  size?: number;
  color?: string;
}) {
  const { theme } = useTheme();
  return (
    <Ionicons name={icons[name]} size={size} color={color ?? theme.text} />
  );
}

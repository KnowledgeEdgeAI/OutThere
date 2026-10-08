export type ActivityIcon =
  "home" | "sun" | "work" | "leaf" | "racket" | "coffee" | "sparkles" | "heart";

export interface PlanStop {
  id: string;
  place: string;
  address: string;
  startsAt: string;
  // Coordinates on the illustrative map, not geographic coordinates.
  x: number | null;
  y: number | null;
}

export interface Plan {
  id: string;
  title: string;
  place: string;
  startsAt: string;
  stops?: PlanStop[];
  circleId: string | null;
  icon: ActivityIcon;
  people: string[];
  rsvp: "In" | "Maybe" | "Out";
}
export interface Circle {
  id: string;
  name: string;
  icon: ActivityIcon;
  people: string[];
  sleeping?: boolean;
}
export interface Message {
  id: string;
  sender: string;
  body: string;
}

export interface Ripple {
  id: string;
  title: string;
  circleId: string;
  slot: string;
  closesAt: string;
}
export interface OpenAvailability {
  interests: string[];
  slot: string;
  distance: number;
  expiresAt: string;
}

import type { Circle, Message, Plan } from "../domain/models";

export const circles: Circle[] = [
  {
    id: "flat",
    name: "Flat 402",
    icon: "home",
    people: ["Divya", "Sara", "Rohan", "Maya"],
  },
  {
    id: "sunday",
    name: "Sunday people",
    icon: "sun",
    people: ["Divya", "Sara", "Aarav"],
  },
  {
    id: "office",
    name: "Office crew",
    icon: "work",
    people: ["Divya", "Rina", "Kabir"],
  },
  {
    id: "birds",
    name: "Early birds",
    icon: "leaf",
    people: ["Divya", "Maya", "Rohan"],
    sleeping: true,
  },
];
export function initialPlans(): Plan[] {
  const today = new Date();
  today.setHours(18, 30, 0, 0);

  const coffeeDay = new Date(today);
  coffeeDay.setDate(coffeeDay.getDate() + 2);
  coffeeDay.setHours(11, 0);
  const badmintonDay = new Date(today);
  badmintonDay.setDate(badmintonDay.getDate() + 1);
  badmintonDay.setHours(17, 0);
  return [
    {
      id: "dinner",
      title: "Office dinner",
      place: "Toit, Indiranagar",
      startsAt: today.toISOString(),
      circleId: "office",
      icon: "work",
      people: ["Divya", "Rina", "Kabir"],
      rsvp: "In",
    },
    {
      id: "badminton",
      title: "Sunset badminton",
      place: "Cubbon Park · Gate 2",
      startsAt: badmintonDay.toISOString(),
      circleId: "flat",
      icon: "racket",
      people: ["Divya", "Sara", "Rohan", "Maya"],
      rsvp: "In",
    },
    {
      id: "clay",
      title: "Clay and coffee",
      place: "Clay Station, Indiranagar",
      startsAt: coffeeDay.toISOString(),
      circleId: "sunday",
      icon: "coffee",
      people: ["Divya", "Sara", "Aarav"],
      rsvp: "Maybe",
    },
  ];
}
export const initialMessages: Message[] = [
  { id: "1", sender: "Sara", body: "Gate 2? It’s quieter on that side." },
  { id: "2", sender: "Rohan", body: "Perfect. Bringing the extra rackets 🏸" },
];
export const people = ["Sara", "Rohan", "Maya", "Aarav", "Rina", "Kabir"];

export const overlapExamples = [
  {
    id: "coffee-walk",
    title: "Coffee & a slow walk",
    slot: "Tomorrow · 5–7 PM",
    distance: "Within 2 km",
  },
  {
    id: "weekend-badminton",
    title: "A casual game of badminton",
    slot: "Saturday · 4–6 PM",
    distance: "Within 5 km",
  },
];

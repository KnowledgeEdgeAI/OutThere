import type { Circle, Plan, PlanStop } from "./models";

export function sortPlans(plans: readonly Plan[]) {
  return [...plans].sort((a, b) => a.startsAt.localeCompare(b.startsAt));
}

export function plansForCircle(plans: readonly Plan[], circleId: string) {
  return sortPlans(plans.filter((plan) => plan.circleId === circleId));
}

export function agendaForDay(plans: readonly Plan[], day = new Date()) {
  const sorted = sortPlans(plans);
  const live = sorted.find(
    (plan) => new Date(plan.startsAt).toDateString() === day.toDateString(),
  );
  return { live, next: sorted.filter((plan) => plan.id !== live?.id) };
}

export function createPlanDraft(
  input: {
    title: string;
    place: string;
    date: Date;
    circleId: string | null;
    stops?: PlanStop[];
  },
  circles: readonly Circle[],
  now = Date.now(),
): { ok: false; error: string } | { ok: true; plan: Omit<Plan, "id"> } {
  const title = input.title.trim();
  if (!title) return { ok: false, error: "Give your plan a name." };
  if (!Number.isFinite(input.date.getTime()) || input.date.getTime() <= now) {
    return { ok: false, error: "Choose a time in the future." };
  }
  if (input.stops) {
    const error = validateRoute(input.stops, now);
    if (error) return { ok: false, error };
  }
  return {
    ok: true,
    plan: {
      title,
      ...(input.stops
        ? {
            stops: input.stops.map((stop) => ({
              ...stop,
              place: stop.place.trim(),
            })),
          }
        : {}),
      place:
        input.stops?.[0]?.place.trim() ||
        input.place.trim() ||
        "Place to be decided",
      startsAt: input.stops?.[0]?.startsAt ?? input.date.toISOString(),
      circleId: input.circleId,
      icon: "sparkles",
      people: [
        ...(circles.find((circle) => circle.id === input.circleId)?.people ?? [
          "Divya",
        ]),
      ],
      rsvp: "In",
    },
  };
}

export function validateRoute(stops: readonly PlanStop[], now = Date.now()) {
  if (!stops.length) return "Add a meeting place and arrival time.";
  for (let i = 0; i < stops.length; i++) {
    const stop = stops[i];
    if (!stop.place.trim()) return `Choose a place for stop ${i + 1}.`;
    const time = Date.parse(stop.startsAt);
    if (!Number.isFinite(time) || time <= now)
      return `Choose an arrival time in the future for stop ${i + 1}.`;
    if (i && time <= Date.parse(stops[i - 1].startsAt))
      return `Stop ${i + 1} must arrive after the previous stop.`;
  }
  return "";
}

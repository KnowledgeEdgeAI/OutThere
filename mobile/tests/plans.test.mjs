import assert from "node:assert/strict";
import test from "node:test";
import {
  agendaForDay,
  createPlanDraft,
  plansForCircle,
} from "../src/domain/plans.ts";

const plan = (id, startsAt, circleId = "friends") => ({
  id,
  startsAt,
  circleId,
  title: id,
  place: "Park",
  icon: "leaf",
  people: ["Divya"],
  rsvp: "In",
});

test("agenda selects the earliest plan on the device's local day without mutating state", () => {
  const today = new Date(2026, 9, 5, 12);
  const late = plan("late", new Date(2026, 9, 5, 18).toISOString());
  const early = plan("early", new Date(2026, 9, 5, 9).toISOString());
  const tomorrow = plan("tomorrow", new Date(2026, 9, 6, 9).toISOString());
  const input = Object.freeze([tomorrow, late, early]);
  assert.deepEqual(agendaForDay(input, today), {
    live: early,
    next: [late, tomorrow],
  });
  assert.deepEqual(input, [tomorrow, late, early]);
});

test("empty days retain the sorted plans, and circle lists exclude other audiences", () => {
  const first = plan("first", "2026-10-06T09:00:00.000Z");
  const second = plan("second", "2026-10-07T09:00:00.000Z");
  const solo = plan("solo", "2026-10-08T09:00:00.000Z", null);
  const input = [solo, second, first];
  assert.deepEqual(agendaForDay(input, new Date(2026, 9, 1)), {
    live: undefined,
    next: [first, second, solo],
  });
  assert.deepEqual(plansForCircle(input, "friends"), [first, second]);
  assert.deepEqual(plansForCircle(input, "missing"), []);
  assert.deepEqual(agendaForDay([]), { live: undefined, next: [] });
});

const now = Date.parse("2026-10-05T12:00:00Z");
const draft = {
  title: "  Coffee  ",
  place: "  ",
  date: new Date(now + 3600000),
  circleId: "friends",
};
const circle = {
  id: "friends",
  name: "Friends",
  icon: "heart",
  people: ["Divya", "Sara"],
};

test("plan creation trims fields, supplies a place, and snapshots the circle audience", () => {
  const result = createPlanDraft(draft, [circle], now);
  assert.equal(result.ok, true);
  assert.deepEqual(result.plan, {
    title: "Coffee",
    place: "Place to be decided",
    startsAt: "2026-10-05T13:00:00.000Z",
    circleId: "friends",
    icon: "sparkles",
    people: ["Divya", "Sara"],
    rsvp: "In",
  });
  assert.notEqual(result.plan.people, circle.people);
  const solo = createPlanDraft(
    { ...draft, circleId: null, place: " Park " },
    [circle],
    now,
  );
  assert.deepEqual(solo.plan.people, ["Divya"]);
  assert.equal(solo.plan.place, "Park");
});

test("blank names and invalid, current, or past times cannot produce plans", () => {
  assert.equal(createPlanDraft({ ...draft, title: "  " }, [], now).ok, false);
  for (const date of [new Date(NaN), new Date(now), new Date(now - 1)]) {
    assert.deepEqual(createPlanDraft({ ...draft, date }, [], now), {
      ok: false,
      error: "Choose a time in the future.",
    });
  }
});

const route = [
  {
    id: "coffee",
    place: " Third Wave Coffee ",
    address: "100 Feet Road",
    startsAt: new Date(now + 3600000).toISOString(),
    x: 82,
    y: 145,
  },
  {
    id: "park",
    place: "Defence Colony Park",
    address: "Defence Colony",
    startsAt: new Date(now + 7200000).toISOString(),
    x: 224,
    y: 183,
  },
];

test("route plans retain each place, pin and arrival, with the first stop used by the agenda", () => {
  const result = createPlanDraft({ ...draft, stops: route }, [circle], now);
  assert.equal(result.ok, true);
  assert.equal(result.plan.place, "Third Wave Coffee");
  assert.equal(result.plan.startsAt, route[0].startsAt);
  assert.equal(result.plan.stops.length, 2);
  assert.deepEqual(result.plan.stops[1], route[1]);
  assert.notEqual(result.plan.stops, route);
  assert.notEqual(result.plan.stops[0], route[0]);
  assert.equal(route[0].place, " Third Wave Coffee ");
});

test("route creation rejects missing places, missing times and non-chronological arrivals", () => {
  for (const stops of [
    [],
    [{ ...route[0], place: " " }],
    [{ ...route[0], startsAt: "" }],
    [route[0], { ...route[1], startsAt: route[0].startsAt }],
    [route[1], route[0]],
    [route[0], { ...route[1], startsAt: new Date(now - 1).toISOString() }],
  ]) {
    assert.equal(createPlanDraft({ ...draft, stops }, [], now).ok, false);
  }
});

test("a custom pin remains a named meeting place and route data is isolated from later draft changes", () => {
  const stops = [
    {
      ...route[0],
      place: "Park gate",
      address: "Custom pin · Indiranagar demo map",
      x: 100,
      y: 200,
    },
  ];
  const result = createPlanDraft({ ...draft, stops }, [], now);
  assert.equal(result.ok, true);
  stops[0].place = "Changed draft";
  assert.equal(result.plan.stops[0].place, "Park gate");
  assert.equal(result.plan.stops[0].x, 100);
  assert.equal(result.plan.stops[0].y, 200);
});

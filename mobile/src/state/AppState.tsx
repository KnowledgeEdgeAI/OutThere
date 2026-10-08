import React, { createContext, useContext, useState } from "react";
import {
  circles as sampleCircles,
  initialMessages,
  initialPlans,
  overlapExamples,
} from "../data/fixtures";
import type {
  Circle,
  Message,
  Plan,
  Ripple,
  OpenAvailability,
} from "../domain/models";
let nextId = 0;
function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${nextId++}`;
}

function useAppStateValue() {
  const [plans, setPlans] = useState(initialPlans);
  const [circles, setCircles] = useState(sampleCircles);
  const [messages, setMessages] = useState<Record<string, Message[]>>({});
  const [rippleReply, setRippleReply] = useState<string | null>(null);
  const [arrived, setArrived] = useState<string[]>([]);
  const [settled, setSettled] = useState<string[]>([]);
  const [coffeeVotes, setCoffeeVotes] = useState<string[]>([]);
  const [appearance, setAppearance] = useState<"System" | "Light" | "Dark">(
    "System",
  );
  const [overlapResponses, setOverlapResponses] = useState<
    Record<string, "hi" | "passed">
  >({});
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const [openAvailability, setOpenAvailability] =
    useState<OpenAvailability | null>(null);
  const [digest, setDigest] = useState(true);
  return {
    plans,
    circles,
    overlaps: overlapExamples,
    overlapResponses,
    respondToOverlap: (id: string, response: "hi" | "passed" | null) =>
      setOverlapResponses((current) => {
        const next = { ...current };
        if (response === null) delete next[id];
        else next[id] = response;
        return next;
      }),
    rippleReply,
    ripples,
    addRipple: (ripple: Omit<Ripple, "id">) => {
      const id = createId("ripple");
      setRipples((current) => [...current, { ...ripple, id }]);
      return id;
    },
    openAvailability,
    setOpenAvailability,
    arrived,
    settled,
    coffeeVotes,
    appearance,
    digest,
    setRippleReply,
    setAppearance,
    setDigest,
    addPlan: (plan: Omit<Plan, "id">) => {
      const id = createId("plan");
      setPlans((p) => [...p, { ...plan, id }]);
      return id;
    },
    updatePlan: (
      id: string,
      details: Pick<Plan, "title" | "place" | "startsAt"> & Pick<Plan, "stops">,
    ) =>
      setPlans((plans) =>
        plans.map((plan) => (plan.id === id ? { ...plan, ...details } : plan)),
      ),
    addCircle: (circle: Omit<Circle, "id">) => {
      const id = createId("circle");
      setCircles((c) => [...c, { ...circle, id }]);
      return id;
    },
    rsvp: (id: string, rsvp: Plan["rsvp"]) =>
      setPlans((p) =>
        p.map((plan) => (plan.id === id ? { ...plan, rsvp } : plan)),
      ),
    wake: (id: string) =>
      setCircles((c) =>
        c.map((circle) =>
          circle.id === id ? { ...circle, sleeping: false } : circle,
        ),
      ),
    markArrived: (id: string) =>
      setArrived((a) => (a.includes(id) ? a : [...a, id])),
    markSettled: (id: string) =>
      setSettled((a) => (a.includes(id) ? a : [...a, id])),
    vote: (id: string) =>
      setCoffeeVotes((a) =>
        a.includes(id) ? a.filter((x) => x !== id) : [...a, id],
      ),
    chat: (id: string) => messages[id] ?? initialMessages,
    send: (id: string, body: string) =>
      setMessages((m) => ({
        ...m,
        [id]: [
          ...(m[id] ?? initialMessages),
          { id: createId("message"), sender: "Divya", body },
        ],
      })),
  };
}
const Context = createContext<ReturnType<typeof useAppStateValue> | null>(null);
export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const state = useAppStateValue();
  return <Context.Provider value={state}>{children}</Context.Provider>;
}
export function useAppState() {
  const value = useContext(Context);
  if (!value) throw new Error("AppStateProvider is missing");
  return value;
}

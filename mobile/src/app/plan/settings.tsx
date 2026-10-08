import { useState } from "react";
import type { PlanStop } from "../../domain/models";
import { validateRoute } from "../../domain/plans";
import { RouteEditor } from "../../ui/route/RouteEditor";
import { router, useLocalSearchParams } from "expo-router";
import { useAppState } from "../../state/AppState";
import { useTheme } from "../../ui/theme/ThemeProvider";
import { Action, Field } from "../../ui/components/Controls";
import { Page } from "../../ui/components/Page";
import { Copy, Eyebrow } from "../../ui/components/Typography";

export default function PlanSettings() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { plans, updatePlan } = useAppState();
  const { theme } = useTheme();
  const plan = plans.find((plan) => plan.id === id);
  const [title, setTitle] = useState(plan?.title ?? "");
  const [stops, setStops] = useState<PlanStop[]>(
    () =>
      plan?.stops?.map((stop) => ({ ...stop })) ?? [
        {
          id: "meeting",
          place: plan?.place ?? "",
          address: "",
          startsAt: plan?.startsAt ?? "",
          x: null,
          y: null,
        },
      ],
  );
  const [error, setError] = useState("");
  if (!plan) return <Page back title="Plan not found" />;

  return (
    <Page back keyboard title="Plan settings">
      <Eyebrow>Plan name</Eyebrow>
      <Field
        accessibilityLabel="Plan name"
        value={title}
        onChangeText={setTitle}
        maxLength={160}
      />
      <RouteEditor
        stops={stops}
        onChange={(next) => {
          setStops(next);
          setError("");
        }}
      />
      {!!error && (
        <Copy size={12} color={theme.coral}>
          {error}
        </Copy>
      )}
      <Action
        title="Save changes"
        icon="check"
        disabled={!title.trim()}
        onPress={() => {
          const routeError = validateRoute(stops);
          if (routeError) {
            setError(routeError);
            return;
          }
          updatePlan(id, {
            title: title.trim(),
            place: stops[0].place.trim(),
            startsAt: stops[0].startsAt,
            stops: stops.map((stop) => ({ ...stop, place: stop.place.trim() })),
          });
          if (router.canGoBack()) router.back();
          else router.replace({ pathname: "/plan/[id]", params: { id } });
        }}
      />
    </Page>
  );
}

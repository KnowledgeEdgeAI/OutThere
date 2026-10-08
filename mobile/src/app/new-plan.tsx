import { createPlanDraft } from "../domain/plans";
import { useTheme } from "../ui/theme/ThemeProvider";
import { useAppState } from "../state/AppState";
import { useState } from "react";
import { View } from "react-native";
import { RouteEditor, emptyStop } from "../ui/route/RouteEditor";
import type { PlanStop } from "../domain/models";
import { router } from "expo-router";

import { Action, Chip, Field } from "../ui/components/Controls";
import { styles } from "../ui/components/Layout";
import { Copy, Eyebrow } from "../ui/components/Typography";
import { Page } from "../ui/components/Page";
export default function NewPlan() {
  const { circles, addPlan } = useAppState();
  const { theme } = useTheme();
  const [title, setTitle] = useState("");
  const [stops, setStops] = useState<PlanStop[]>(() => [emptyStop()]);
  const [circleId, setCircleId] = useState<string | null>(null);
  const [error, setError] = useState("");
  function submit() {
    const result = createPlanDraft(
      {
        title,
        place: stops[0]?.place ?? "",
        date: new Date(stops[0]?.startsAt ?? ""),
        circleId,
        stops,
      },
      circles,
    );
    if (!result.ok) {
      setError(result.error);
      return;
    }
    const id = addPlan(result.plan);
    router.replace({ pathname: "/plan/[id]", params: { id } });
  }
  return (
    <Page back keyboard title="New plan">
      <Eyebrow>Plan name</Eyebrow>
      <Field
        accessibilityLabel="Plan name"
        placeholder="e.g. Coffee & a little exploring"
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
      <Eyebrow>Who’s coming?</Eyebrow>
      <View style={styles.wrap}>
        <Chip
          title="Just me"
          active={circleId === null}
          onPress={() => setCircleId(null)}
        />
        {circles
          .filter((c) => !c.sleeping)
          .map((circle) => (
            <Chip
              key={circle.id}
              title={circle.name}
              active={circle.id === circleId}
              onPress={() => setCircleId(circle.id)}
            />
          ))}
      </View>
      <Copy size={13} muted>
        {circleId
          ? "Everyone in this circle can RSVP."
          : "A little time for yourself."}
      </Copy>
      {!!error && <Copy color={theme.coral}>{error}</Copy>}
      <Action
        title="Create plan"
        icon="check"
        disabled={!title.trim()}
        onPress={submit}
      />
    </Page>
  );
}

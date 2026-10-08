import { useCurrentTime } from "../ui/useCurrentTime";
import { useState } from "react";
import { View } from "react-native";
import { router } from "expo-router";
import { useAppState } from "../state/AppState";
import { Action, Chip, Field } from "../ui/components/Controls";
import { styles } from "../ui/components/Layout";
import { Page } from "../ui/components/Page";
import { Copy, Eyebrow } from "../ui/components/Typography";

export default function NewRipple() {
  const { circles, ripples, addRipple } = useAppState();
  const activeCircles = circles.filter((circle) => !circle.sleeping);
  const [title, setTitle] = useState("");
  const [slot, setSlot] = useState("");
  const [circleId, setCircleId] = useState(activeCircles[0]?.id ?? "");
  const now = useCurrentTime();
  const atLimit =
    ripples.filter((ripple) => new Date(ripple.closesAt).getTime() > now)
      .length >= 2;
  return (
    <Page
      back
      keyboard
      title="Toss a ripple"
      subtitle="A little idea. See who’s up for it."
    >
      <Eyebrow>What are you feeling?</Eyebrow>
      <Field
        accessibilityLabel="Ripple idea"
        placeholder="Anyone up for coffee and a slow walk?"
        value={title}
        onChangeText={setTitle}
        maxLength={160}
        multiline
      />
      <Eyebrow>A rough time · optional</Eyebrow>
      <Field
        accessibilityLabel="Ripple time"
        placeholder="Saturday afternoon, maybe?"
        value={slot}
        onChangeText={setSlot}
        maxLength={120}
      />
      <Eyebrow>Your people</Eyebrow>
      <View style={styles.wrap}>
        {activeCircles.map((circle) => (
          <Chip
            key={circle.id}
            title={circle.name}
            active={circleId === circle.id}
            onPress={() => setCircleId(circle.id)}
          />
        ))}
      </View>
      <Copy size={12} muted>
        {atLimit
          ? "You already have two active ripples. Let one close before starting another."
          : "Replies stay open for 48 hours. Nothing is locked in yet."}
      </Copy>
      <Action
        title="Toss a ripple"
        icon="ripple"
        disabled={!title.trim() || !circleId || atLimit}
        onPress={() => {
          addRipple({
            title: title.trim(),
            slot: slot.trim(),
            circleId,
            closesAt: new Date(Date.now() + 48 * 3600000).toISOString(),
          });
          router.replace("/inbox");
        }}
      />
    </Page>
  );
}

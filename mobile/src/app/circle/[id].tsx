import { plansForCircle } from "../../domain/plans";
import { useTheme } from "../../ui/theme/ThemeProvider";
import { useAppState } from "../../state/AppState";
import { router, useLocalSearchParams } from "expo-router";
import { View } from "react-native";

import { Avatars } from "../../ui/components/Avatars";
import { Chip, SmallButton } from "../../ui/components/Controls";
import { Copy, Eyebrow } from "../../ui/components/Typography";
import { ListItem } from "../../ui/components/Lists";
import { Page } from "../../ui/components/Page";
import { PlanCard } from "../../ui/components/PlanCard";
import { Row } from "../../ui/components/Layout";
export default function CircleDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { circles, plans, rsvp, rippleReply } = useAppState();
  const { theme } = useTheme();
  const circle = circles.find((c) => c.id === id);
  if (!circle) return <Page back title="Circle not found" />;
  const next = plansForCircle(plans, id);
  return (
    <Page
      back
      title={circle.name}
      subtitle={`${circle.people.length} people · invite-only`}
    >
      <Avatars people={circle.people} />
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Next up</Eyebrow>
      </View>
      {next.length ? (
        next.map((plan) => (
          <View key={plan.id} style={{ gap: 12, paddingBottom: 16 }}>
            <PlanCard plan={plan} />
            <Row style={{ gap: 4 }}>
              {(["In", "Maybe", "Out"] as const).map((choice) => (
                <View style={{ flex: 1 }} key={choice}>
                  <Chip
                    title={choice === "In" ? "In ✓" : choice}
                    active={plan.rsvp === choice}
                    onPress={() => rsvp(plan.id, choice)}
                  />
                </View>
              ))}
            </Row>
          </View>
        ))
      ) : (
        <Copy size={13} muted>
          No upcoming plans.
        </Copy>
      )}
      <View style={{ marginTop: 8 }}>
        <Eyebrow>Circle board · open loops</Eyebrow>
      </View>
      <View>
        <ListItem
          open
          title="Pottery on Sunday · ripple"
          detail={
            rippleReply
              ? `You replied: ${rippleReply}`
              : "Sara’s soft ask · waiting on you"
          }
          icon="sparkles"
          onPress={() => router.push("/inbox")}
        />
        {next[0] && (
          <ListItem
            open
            title="Filter coffee after?"
            detail="Poll · see it in the plan room"
            icon="coffee"
            onPress={() =>
              router.push({
                pathname: "/plan/[id]",
                params: { id: next[0].id },
              })
            }
          />
        )}
      </View>
      <View style={{ marginTop: 8 }}>
        <Eyebrow>People</Eyebrow>
      </View>
      {circle.people.map((name) => (
        <Row key={name} style={{ paddingVertical: 8 }}>
          <View
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              backgroundColor: theme.washStrong,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Copy size={11} bold>
              {name[0]}
            </Copy>
          </View>
          <Copy size={14} style={{ flex: 1 }}>
            {name}
          </Copy>
          {name === "Divya" && (
            <Copy size={12} muted>
              You · host
            </Copy>
          )}
        </Row>
      ))}
      <SmallButton
        title="Make a plan"
        onPress={() => router.push("/new-plan")}
      />
    </Page>
  );
}

import { useTheme } from "../ui/theme/ThemeProvider";
import { useAppState } from "../state/AppState";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { router } from "expo-router";
import { people } from "../data/fixtures";

import { Action, Field } from "../ui/components/Controls";
import { Card, Row } from "../ui/components/Layout";
import { Copy, Eyebrow } from "../ui/components/Typography";
import { Icon } from "../ui/components/Icon";
import { Page } from "../ui/components/Page";
export default function NewCircle() {
  const { addCircle } = useAppState();
  const { theme } = useTheme();
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  return (
    <Page back keyboard title="New circle" subtitle="Small stays warm.">
      <Eyebrow>Give it a name</Eyebrow>
      <Field
        accessibilityLabel="Circle name"
        placeholder="Sunday people"
        value={name}
        onChangeText={setName}
        maxLength={100}
      />
      <Eyebrow>Bring your people</Eyebrow>
      <Card>
        {people.map((person) => (
          <Pressable
            key={person}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: chosen.includes(person) }}
            onPress={() =>
              setChosen((p) =>
                p.includes(person)
                  ? p.filter((x) => x !== person)
                  : [...p, person],
              )
            }
          >
            <Row style={{ minHeight: 48 }}>
              <View
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 19,
                  backgroundColor: theme.lilacSoft,
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Copy bold>{person[0]}</Copy>
              </View>
              <Copy style={{ flex: 1 }}>{person}</Copy>
              <Icon
                name={chosen.includes(person) ? "check" : "add"}
                color={theme.accent}
              />
            </Row>
          </Pressable>
        ))}
      </Card>
      <Copy muted size={12}>
        Pick at least two people. Sample invitations are accepted instantly in
        this preview.
      </Copy>
      <Action
        title="Start this circle"
        icon="people"
        disabled={!name.trim() || chosen.length < 2}
        onPress={() => {
          const id = addCircle({
            name: name.trim(),
            icon: "heart",
            people: ["Divya", ...chosen],
          });
          router.replace({ pathname: "/circle/[id]", params: { id } });
        }}
      />
    </Page>
  );
}

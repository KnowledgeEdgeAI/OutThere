import { useTheme } from "../ui/theme/ThemeProvider";
import { useAppState } from "../state/AppState";
import { Switch, View } from "react-native";

import { Card, Row, styles } from "../ui/components/Layout";
import { Chip } from "../ui/components/Controls";
import { Copy, Eyebrow } from "../ui/components/Typography";
import { Page } from "../ui/components/Page";
export default function Device() {
  const { appearance, setAppearance, digest, setDigest } = useAppState();
  const { theme } = useTheme();
  return (
    <Page back title="Appearance & device">
      <Eyebrow>Appearance</Eyebrow>
      <Card>
        <View style={styles.wrap}>
          {(["System", "Light", "Dark"] as const).map((choice) => (
            <Chip
              key={choice}
              title={choice}
              active={appearance === choice}
              onPress={() => setAppearance(choice)}
            />
          ))}
        </View>
      </Card>
      <Eyebrow>Notifications</Eyebrow>
      <Card>
        <Row>
          <View style={{ flex: 1, gap: 4 }}>
            <Copy bold>Daily digest</Copy>
            <Copy size={12} muted>
              One quiet catch-up from your people.
            </Copy>
          </View>
          <Switch
            accessibilityLabel="Daily digest"
            value={digest}
            onValueChange={setDigest}
            trackColor={{ true: theme.accent, false: theme.soft }}
          />
        </Row>
      </Card>
      <Copy size={12} muted>
        Dates and times follow your device’s local formats.
      </Copy>
    </Page>
  );
}

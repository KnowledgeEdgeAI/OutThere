import { Alert, View } from "react-native";
import { useTheme } from "../theme/ThemeProvider";
import { Action } from "../components/Controls";
import { Card, Row } from "../components/Layout";
import { Copy } from "../components/Typography";
import { Icon } from "../components/Icon";

export function Album() {
  const { theme } = useTheme();
  return (
    <>
      <Card color={theme.mintSoft}>
        <Copy size={23} bold>
          The good bits belong here.
        </Copy>
        <Copy muted>Drop the moments. Keep the memories.</Copy>
        <Action
          title="Add a moment"
          icon="add"
          onPress={() =>
            Alert.alert(
              "Album preview",
              "These are illustrated sample moments. Photo uploads will be added in a later build.",
            )
          }
        />
      </Card>
      <View style={{ gap: 12 }}>
        {(
          [
            ["sun", "racket"],
            ["coffee", "leaf"],
          ] as const
        ).map((pair, row) => (
          <Row key={row} style={{ alignItems: "stretch", gap: 12 }}>
            {pair.map((icon, column) => (
              <View
                key={icon}
                style={{
                  flex: 1,
                  minHeight: 160,
                  borderRadius: 22,
                  backgroundColor: [
                    theme.sunSoft,
                    theme.lilacSoft,
                    theme.peach,
                    theme.mintSoft,
                  ][row * 2 + column],
                  justifyContent: "center",
                  alignItems: "center",
                  gap: 15,
                }}
              >
                <Icon name={icon} size={48} />
                <Copy size={11} bold>
                  {
                    [
                      "Golden hour",
                      "Round two",
                      "Coffee after",
                      "Slow Sundays",
                    ][row * 2 + column]
                  }
                </Copy>
              </View>
            ))}
          </Row>
        ))}
      </View>
      <Copy size={12} muted>
        Illustrated sample moments
      </Copy>
    </>
  );
}

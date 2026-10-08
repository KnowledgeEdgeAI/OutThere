import { View } from "react-native";
import { Copy } from "./Typography";
import { Row } from "./Layout";
import { useTheme } from "../theme/ThemeProvider";

export function Avatars({ people }: { people: string[] }) {
  const { theme } = useTheme();
  return (
    <Row style={{ gap: 0 }}>
      <Row style={{ gap: 0 }}>
        {people.slice(0, 4).map((name, i) => (
          <View
            key={name}
            accessible
            accessibilityLabel={name}
            style={{
              width: 28,
              height: 28,
              borderRadius: 14,
              alignItems: "center",
              justifyContent: "center",
              marginLeft: i ? -8 : 0,
              backgroundColor: [
                theme.coral,
                theme.lilac,
                theme.sun,
                theme.peach,
              ][i],
              borderWidth: 2,
              borderColor: theme.surface,
            }}
          >
            <Copy bold size={8} color={i < 2 ? "#fff" : theme.text}>
              {(
                {
                  Divya: "DG",
                  Sara: "SG",
                  Rohan: "RN",
                  Maya: "MJ",
                  Aarav: "AK",
                  Rina: "RI",
                  Kabir: "KA",
                } as Record<string, string>
              )[name] ?? name.slice(0, 2).toUpperCase()}
            </Copy>
          </View>
        ))}
      </Row>
      <Copy size={12} muted style={{ marginLeft: 12 }}>
        {people.length} people
      </Copy>
    </Row>
  );
}

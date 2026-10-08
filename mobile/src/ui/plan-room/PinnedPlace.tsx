import { View } from "react-native";
import { useTheme } from "../theme/ThemeProvider";
import { Card, Row } from "../components/Layout";
import { Copy } from "../components/Typography";
import { Icon } from "../components/Icon";

export function PinnedPlace({
  place,
  iconSize,
  gap = 3,
}: {
  place: string;
  iconSize: number;
  gap?: number;
}) {
  const { theme } = useTheme();
  return (
    <Card color={theme.lilacSoft} style={{ borderWidth: 0 }}>
      <Row>
        <Icon name="pin" size={iconSize} />
        <View style={{ flex: 1, gap }}>
          <Copy size={14} bold>
            {place}
          </Copy>
          <Copy size={12} muted>
            Pinned meeting point
          </Copy>
        </View>
      </Row>
    </Card>
  );
}

import { useAppState } from "../../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { Action } from "../components/Controls";
import { Card, Row } from "../components/Layout";
import { Copy, Eyebrow } from "../components/Typography";

export function Money({ planId: id }: { planId: string }) {
  const demo = useAppState();
  const { theme } = useTheme();
  const isSettled = demo.settled.includes(id);
  return (
    <>
      <Card color={theme.mintSoft}>
        <Eyebrow>Your share · sample expense</Eyebrow>
        <Copy size={40}>{isSettled ? "All settled." : "₹180"}</Copy>
        <Copy muted>Court + coffee. Good times, easy maths.</Copy>
      </Card>
      <Card>
        {[
          ["Court booking", "₹480"],
          ["Coffee after", "₹240"],
          ["Split equally · 4 people", "₹180 each"],
        ].map(([label, value]) => (
          <Row key={label}>
            <Copy style={{ flex: 1 }}>{label}</Copy>
            <Copy bold>{value}</Copy>
          </Row>
        ))}
      </Card>
      <Action
        title={isSettled ? "Settled in this preview" : "Mark as settled"}
        icon="check"
        disabled={isSettled}
        onPress={() => demo.markSettled(id)}
      />
      <Copy size={12} muted>
        Sample balances only. No payments are made.
      </Copy>
    </>
  );
}

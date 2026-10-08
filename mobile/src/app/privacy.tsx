import { Card, Row } from "../ui/components/Layout";
import { Copy } from "../ui/components/Typography";
import { Icon } from "../ui/components/Icon";
import { Page } from "../ui/components/Page";
export default function Privacy() {
  return (
    <Page
      back
      title="Safety & privacy"
      subtitle="Your time. Your people. Your choice."
    >
      {[
        "Circles are invite only",
        "No public profiles",
        "Location sharing is off",
      ].map((label) => (
        <Card key={label}>
          <Row>
            <Icon name="lock" />
            <Copy bold style={{ flex: 1 }}>
              {label}
            </Copy>
          </Row>
        </Card>
      ))}
      <Copy muted size={13}>
        This is a UI preview. No contacts, location or photos are collected.
      </Copy>
    </Page>
  );
}

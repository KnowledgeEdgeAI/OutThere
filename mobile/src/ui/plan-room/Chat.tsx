import { useState } from "react";
import { Pressable, View } from "react-native";
import type { Plan } from "../../domain/models";
import { useAppState } from "../../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { Field } from "../components/Controls";
import { Card, Row } from "../components/Layout";
import { Copy } from "../components/Typography";
import { Icon } from "../components/Icon";
import { PinnedPlace } from "./PinnedPlace";

export function Chat({ plan }: { plan: Plan }) {
  const { chat: messagesForPlan } = useAppState();
  const { theme } = useTheme();
  const chat = messagesForPlan(plan.id);
  return (
    <>
      <Copy muted size={12} style={{ textAlign: "center" }}>
        Sara pinned the meeting point
      </Copy>
      <PinnedPlace place={plan.place} iconSize={18} gap={0} />
      {chat.map((item) => (
        <View
          key={item.id}
          style={{
            alignItems: item.sender === "Divya" ? "flex-end" : "flex-start",
          }}
        >
          <Card
            color={item.sender === "Divya" ? theme.peach : theme.surface}
            style={{
              maxWidth: "88%",
              borderRadius: 22,
              gap: 6,
              padding: 16,
            }}
          >
            <Copy size={11} muted bold>
              {item.sender === "Divya" ? "You" : item.sender}
            </Copy>
            <Copy>{item.body}</Copy>
          </Card>
        </View>
      ))}
    </>
  );
}

export function ChatComposer({
  planId,
  active,
}: {
  planId: string;
  active: boolean;
}) {
  const { send: sendMessage } = useAppState();
  const { theme } = useTheme();
  const [message, setMessage] = useState("");
  function send() {
    const body = message.trim();
    if (!body) return;
    sendMessage(planId, body);
    setMessage("");
  }
  if (!active) return null;
  return (
    <Row
      style={{
        padding: 16,
        alignItems: "flex-end",
        borderTopWidth: 1,
        borderColor: theme.line,
      }}
    >
      <Field
        accessibilityLabel="Message"
        placeholder="A quick note for your people…"
        value={message}
        onChangeText={setMessage}
        maxLength={2000}
        multiline
        style={{ flex: 1, maxHeight: 120 }}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Send message"
        disabled={!message.trim()}
        onPress={send}
        style={{
          width: 46,
          height: 46,
          borderRadius: 23,
          backgroundColor: theme.accent,
          alignItems: "center",
          justifyContent: "center",
          opacity: message.trim() ? 1 : 0.4,
        }}
      >
        <Icon name="send" color="#fff" />
      </Pressable>
    </Row>
  );
}

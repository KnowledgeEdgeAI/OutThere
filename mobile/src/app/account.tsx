import { useState } from "react";
import { Platform, View } from "react-native";
import { useAccount } from "../state/AccountState";
import { Page } from "../ui/components/Page";
import { Card } from "../ui/components/Layout";
import { Action, Field, SmallButton } from "../ui/components/Controls";
import { Copy, Eyebrow } from "../ui/components/Typography";

export default function Account() {
  const { client, status, data, devices, error } = useAccount();
  const [phone, setPhone] = useState("");
  const [draftName, setName] = useState<string | null>(null);
  const name = draftName ?? data?.profile.name ?? "";
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  async function perform(action: () => Promise<unknown>) {
    setWorking(true);
    setNotice(null);
    try {
      await action();
      setName(null);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Please try again");
    } finally {
      setWorking(false);
    }
  }
  if (!client)
    return (
      <Page back title="Account" subtitle="You're viewing sample plans.">
        <Copy muted>
          Connected accounts are available in the development build with a
          server configured.
        </Copy>
      </Page>
    );
  const pending = data?.outbox[0];
  return (
    <Page
      back
      title="Account"
      subtitle={
        data ? "Your profile and connected devices" : "Start with your people"
      }
    >
      <Copy muted size={13} accessibilityLiveRegion="polite">
        {status === "ready"
          ? "Connected"
          : status === "connecting"
            ? "Connecting…"
            : status === "offline"
              ? "Offline · edits stay on this device"
              : "Sign in to continue"}
      </Copy>
      {(notice || error) && (
        <Copy size={13} accessibilityLiveRegion="polite">
          {notice || error}
        </Copy>
      )}
      {!data ? (
        <>
          <Field
            accessibilityLabel="Phone number"
            placeholder="Phone number with country code"
            keyboardType="phone-pad"
            autoComplete="tel"
            value={phone}
            onChangeText={setPhone}
          />
          <Field
            accessibilityLabel="Your name"
            placeholder="Your name (for a new account)"
            autoComplete="name"
            maxLength={80}
            value={name}
            onChangeText={setName}
          />
          <Action
            title={working ? "Signing in…" : "Continue"}
            disabled={working || status === "connecting" || !phone.trim()}
            onPress={() => void perform(() => client.login(phone, name))}
          />
          <Copy muted size={12}>
            Prototype sign-in uses your phone number without verification.
            Anyone who knows the number can enter this account.
          </Copy>
          {Platform.OS === "web" && (
            <Copy muted size={12}>
              Browser sessions end on reload. Your local pending edits remain
              saved.
            </Copy>
          )}
        </>
      ) : (
        <>
          <Eyebrow>Profile</Eyebrow>
          <Copy muted size={13}>
            {data.profile.phone}
          </Copy>
          <Field
            accessibilityLabel="Your name"
            value={name}
            onChangeText={setName}
            maxLength={80}
          />
          <Action
            title={
              working
                ? "Saving…"
                : status === "ready"
                  ? "Save name"
                  : "Save for later"
            }
            disabled={
              working ||
              !!pending ||
              !name.trim() ||
              name.trim() === data.profile.name
            }
            onPress={() => void perform(() => client.editName(name))}
          />
          {pending && (
            <Card>
              <Copy bold>
                {pending.state === "queued"
                  ? "Waiting for confirmation"
                  : "Review your edit"}
              </Copy>
              <Copy size={13}>{pending.payload.name}</Copy>
              <Copy muted size={12}>
                {pending.error ??
                  "Your edit is saved locally and will retry when connected."}
              </Copy>
              {pending.state !== "queued" && (
                <SmallButton
                  title="Discard edit"
                  ghost
                  disabled={working}
                  onPress={() => void perform(() => client.discardEdit())}
                />
              )}
            </Card>
          )}
          {status !== "ready" && (
            <SmallButton
              title="Reconnect"
              ghost
              disabled={working || status === "connecting"}
              onPress={() => void perform(() => client.connect())}
            />
          )}
          <Eyebrow>Devices</Eyebrow>
          {devices
            .filter((device) => device.revoked_at === null)
            .map((device) => (
              <Card key={device.id}>
                <View style={{ gap: 8 }}>
                  <Copy bold>
                    {device.platform === "ios"
                      ? "iPhone"
                      : device.platform === "android"
                        ? "Android"
                        : "Browser"}
                    {device.current ? " · this device" : ""}
                  </Copy>
                  <Copy muted size={12}>
                    Last active{" "}
                    {new Date(device.last_seen_at * 1000).toLocaleString()}
                  </Copy>
                  {!device.current && (
                    <SmallButton
                      title="Sign out this device"
                      ghost
                      disabled={working || status !== "ready"}
                      onPress={() =>
                        void perform(() => client.revoke(device.id))
                      }
                    />
                  )}
                </View>
              </Card>
            ))}
          <SmallButton
            title="Sign out"
            ghost
            disabled={working || status !== "ready"}
            onPress={() => void perform(() => client.signOut())}
          />
          <Copy muted size={12}>
            Plans and conversations elsewhere in this preview use sample data.
            This account page is connected to the server.
          </Copy>
        </>
      )}
    </Page>
  );
}

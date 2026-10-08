import { useCurrentTime } from "../ui/useCurrentTime";
import { useState } from "react";
import { View } from "react-native";
import { router } from "expo-router";
import { useAppState } from "../state/AppState";
import { Action, Chip, SmallButton } from "../ui/components/Controls";
import { styles } from "../ui/components/Layout";
import { Page } from "../ui/components/Page";
import { Copy, Eyebrow } from "../ui/components/Typography";

export default function GoOpen() {
  const { openAvailability, setOpenAvailability } = useAppState();
  const now = useCurrentTime();
  const activeOpen =
    openAvailability && new Date(openAvailability.expiresAt).getTime() > now
      ? openAvailability
      : null;
  const [interests, setInterests] = useState(
    activeOpen?.interests ?? ["Coffee"],
  );
  const [slot, setSlot] = useState(activeOpen?.slot ?? "Tomorrow evening");
  const [distance, setDistance] = useState(activeOpen?.distance ?? 2);
  return (
    <Page
      back
      title="Go Open"
      subtitle="Free soon? Make a little room for something new."
    >
      <Eyebrow>Up for</Eyebrow>
      <View style={styles.wrap}>
        {["Coffee", "A walk", "Badminton", "Art & pottery"].map((interest) => (
          <Chip
            key={interest}
            title={interest}
            active={interests.includes(interest)}
            onPress={() =>
              setInterests((current) =>
                current.includes(interest)
                  ? current.filter((item) => item !== interest)
                  : [...current, interest],
              )
            }
          />
        ))}
      </View>
      <Eyebrow>When you’re free</Eyebrow>
      <View style={styles.wrap}>
        {["Tomorrow evening", "Saturday afternoon", "Sunday morning"].map(
          (time) => (
            <Chip
              key={time}
              title={time}
              active={slot === time}
              onPress={() => setSlot(time)}
            />
          ),
        )}
      </View>
      <Eyebrow>How nearby?</Eyebrow>
      <View style={styles.wrap}>
        {[2, 5, 10].map((km) => (
          <Chip
            key={km}
            title={`Within ${km} km`}
            active={distance === km}
            onPress={() => setDistance(km)}
          />
        ))}
      </View>
      <Copy size={12} muted>
        Your availability stays private. Say hi to an overlap; a Hello opens
        when it’s mutual.
      </Copy>
      <Copy size={12} muted>
        This preview uses example overlaps. Your Open stays active for 24 hours.
      </Copy>
      <Action
        title={activeOpen ? "Update Open" : "Go Open"}
        icon="open"
        disabled={interests.length === 0}
        onPress={() => {
          setOpenAvailability({
            interests,
            slot,
            distance,
            expiresAt:
              activeOpen?.expiresAt ??
              new Date(Date.now() + 24 * 3600000).toISOString(),
          });
          router.replace("/inbox");
        }}
      />
      {activeOpen && (
        <SmallButton
          title="End Open"
          ghost
          onPress={() => {
            setOpenAvailability(null);
            router.replace("/inbox");
          }}
        />
      )}
    </Page>
  );
}

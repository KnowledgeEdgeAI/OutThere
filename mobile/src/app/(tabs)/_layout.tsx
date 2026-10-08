import { Tabs } from "expo-router";
import { Easing } from "react-native";
import { AnimatedTabBar } from "../../ui/navigation";
import { useReducedMotion } from "../../ui/useReducedMotion";
export default function TabLayout() {
  const reduced = useReducedMotion();
  return (
    <Tabs
      tabBar={(props) => <AnimatedTabBar {...props} />}
      screenOptions={{
        headerShown: false,
        animation: reduced ? "none" : "fade",
        transitionSpec: {
          animation: "timing",
          config: { duration: 190, easing: Easing.out(Easing.cubic) },
        },
      }}
    >
      <Tabs.Screen name="index" />
      <Tabs.Screen name="circles" />
      <Tabs.Screen name="create-tab" />
      <Tabs.Screen name="inbox" />
      <Tabs.Screen name="you" />
    </Tabs>
  );
}

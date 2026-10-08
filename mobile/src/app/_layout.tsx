import { useTheme, AppThemeProvider } from "../ui/theme/ThemeProvider";
import { AppStateProvider } from "../state/AppState";
import { AccountProvider } from "../state/AccountState";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";

function Navigator() {
  const { theme, isDark } = useTheme();
  return (
    <>
      <StatusBar style={isDark ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: theme.background },
        }}
      >
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="create"
          options={{
            presentation: "transparentModal",
            animation: "slide_from_bottom",
            contentStyle: { backgroundColor: "transparent" },
          }}
        />
        <Stack.Screen name="new-plan" options={{ presentation: "modal" }} />
        <Stack.Screen name="new-circle" options={{ presentation: "modal" }} />
      </Stack>
    </>
  );
}
export default function Layout() {
  const [loaded, error] = useFonts({
    "DM Sans": require("../../assets/DM-Sans-Regular.ttf"),
    "DM Sans Medium": require("../../assets/DM-Sans-Medium.ttf"),
    "DM Sans SemiBold": require("../../assets/DM-Sans-SemiBold.ttf"),
  });
  if (!loaded && !error) return null;
  return (
    <SafeAreaProvider>
      <AppStateProvider>
        <AppThemeProvider>
          <AccountProvider>
            <Navigator />
          </AccountProvider>
        </AppThemeProvider>
      </AppStateProvider>
    </SafeAreaProvider>
  );
}

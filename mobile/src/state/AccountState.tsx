import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";
import { AppState, Platform } from "react-native";
import { randomUUID } from "expo-crypto";
import { AccountClient, type AccountView } from "../data/account/client";
import { AccountSocket } from "../data/account/socket";
import { AccountStore } from "../data/account/store";
import { cache, secrets } from "../data/account/storage";
import { socketUrl } from "../data/account/contracts";

const url = process.env.EXPO_PUBLIC_API_WS_URL;
const Context = createContext<AccountClient | null>(null);
export function AccountProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(() =>
    url
      ? new AccountClient(
          new AccountSocket(
            socketUrl(url),
            (endpoint) => new WebSocket(endpoint),
            randomUUID,
          ),
          new AccountStore(cache),
          secrets,
          randomUUID,
          Platform.OS === "ios"
            ? "ios"
            : Platform.OS === "android"
              ? "android"
              : "web",
        )
      : null,
  );
  useEffect(() => {
    if (!client) return;
    void client.initialize();
    const subscription = AppState.addEventListener("change", (state) =>
      client.setActive(state === "active"),
    );
    const online = () => client.setActive(true);
    const offline = () => client.setActive(false);
    if (Platform.OS === "web") {
      window.addEventListener("online", online);
      window.addEventListener("offline", offline);
    }
    return () => {
      subscription.remove();
      client.dispose();
      if (Platform.OS === "web") {
        window.removeEventListener("online", online);
        window.removeEventListener("offline", offline);
      }
    };
  }, [client]);
  return <Context.Provider value={client}>{children}</Context.Provider>;
}
const empty: AccountView = {
  status: "signed_out",
  data: null,
  devices: [],
  error: null,
};
const noSubscription = () => () => {};
export function useAccount() {
  const client = useContext(Context);
  const view = useSyncExternalStore(
    client?.subscribe ?? noSubscription,
    client?.getSnapshot ?? (() => empty),
  );
  return { client, ...view };
}

export type Mood = "warm" | "sage" | "blue" | "plum" | "teal" | "gold";
const moods = {
  warm: { accent: "#A64D36", darkAccent: "#EFAC91", wash: "226,181,150" },
  sage: { accent: "#3E705B", darkAccent: "#A5CEB1", wash: "151,193,163" },
  blue: { accent: "#436D9E", darkAccent: "#A6C9EF", wash: "157,187,219" },
  plum: { accent: "#806184", darkAccent: "#D3B2DA", wash: "198,169,201" },
  teal: { accent: "#317574", darkAccent: "#99D4CD", wash: "151,202,195" },
  gold: { accent: "#87632B", darkAccent: "#E2C48E", wash: "222,198,145" },
};
const light = {
  background: "#FBFAF7",
  surface: "#FFFFFF",
  soft: "#F0F1ED",
  line: "#DFE3DF",
  text: "#272C2C",
  muted: "#626C6B",
  coral: "#FF6B4A",
  lilac: "#8B8CF0",
  lilacSoft: "#ECECFC",
  sun: "#FFC24B",
  sunSoft: "#FFF3D9",
  mintSoft: "#DFF4EC",
  peach: "#FFE9E2",
  accent: "#A64D36",
  wash: "rgba(226,181,150,.14)",
  washStrong: "rgba(226,181,150,.27)",
  washEdge: "rgba(166,77,54,.13)",
  glow: "rgba(226,181,150,.24)",
  selected: "rgba(166,77,54,.1)",
  glass: "rgba(255,255,255,.94)",
  glassEdge: "rgba(38,48,45,.1)",
  positive: "#1F8F6E",
};
const dark: typeof light = {
  ...light,
  background: "#202629",
  surface: "#1F212B",
  soft: "#2C3437",
  line: "#3B4547",
  text: "#F1F3EF",
  muted: "#B0BBB9",
  lilacSoft: "#2C2D4A",
  sunSoft: "#3E3421",
  mintSoft: "#1D332C",
  peach: "#3D2B25",
  glass: "rgba(41,49,53,.96)",
  glassEdge: "rgba(255,255,255,.13)",
  positive: "#5BC9A8",
};
export function themeForMood(isDark: boolean, mood: Mood = "warm"): Theme {
  const tone = moods[mood];
  const accent = isDark ? tone.darkAccent : tone.accent;
  const rgb = accent
    .match(/\w\w/g)!
    .map((v) => parseInt(v, 16))
    .join(",");
  return {
    ...(isDark ? dark : light),
    accent,
    wash: `rgba(${tone.wash},.14)`,
    washStrong: `rgba(${tone.wash},.27)`,
    glow: `rgba(${tone.wash},.24)`,
    washEdge: `rgba(${rgb},.13)`,
    selected: `rgba(${rgb},.1)`,
  };
}
export function moodForPath(path: string): Mood {
  if (path.includes("circle")) return "sage";
  if (path.includes("inbox")) return "blue";
  if (path.includes("you") || path.includes("device")) return "plum";
  if (path.includes("scrapbook")) return "gold";
  if (path.includes("splits")) return "teal";
  if (path.includes("privacy")) return "sage";
  return "warm";
}
export type Theme = typeof light;

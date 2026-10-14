export const THEMES = [
  { id: "neutral", name: "Neutral", detail: "Solid paper & slate · default", colors: ["#f7f7f4", "#f0f1ed", "#3d4e58"] },
  { id: "lavender", name: "Lavender", detail: "Soft violet · light", colors: ["#f8f7fc", "#eee9ff", "#67578f"] },
  { id: "sage", name: "Sage", detail: "Fresh green · light", colors: ["#f5f8f5", "#e2eee4", "#3e6654"] },
  { id: "ocean", name: "Ocean", detail: "Clear blue · light", colors: ["#f4f8fc", "#e2effb", "#365e8c"] },
  { id: "sand", name: "Sand", detail: "Warm paper · light", colors: ["#faf7f1", "#f3e9d8", "#805b3c"] },
  { id: "midnight", name: "Midnight", detail: "Low-light focus · dark", colors: ["#151b29", "#242d42", "#c5b5ef"] },
  { id: "charcoal", name: "Charcoal", detail: "Graphite & teal · dark", colors: ["#181c1e", "#252c2e", "#9bd5c5"] },
];
export function isDarkTheme(value) { return value === "midnight" || value === "charcoal"; }
export function themeId(value) { return THEMES.some(theme => theme.id === value) ? value : "neutral"; }

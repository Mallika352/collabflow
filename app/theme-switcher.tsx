"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { readThemePreference, subscribeThemePreference, updateThemePreference, type ThemePreference } from "./theme-preference";
const options: { value: ThemePreference; label: string; icon: string; description: string }[] = [
  { value: "system", label: "System", icon: "\u25d0", description: "Follow your device" },
  { value: "light", label: "Light", icon: "\u2600", description: "Bright workspace" },
  { value: "dark", label: "Dark", icon: "\u263e", description: "Low-light workspace" },
];

export default function ThemeSwitcher() {
  const preference = useSyncExternalStore(subscribeThemePreference, readThemePreference, () => "system");
  const detailsRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (detailsRef.current && !detailsRef.current.contains(event.target as Node)) detailsRef.current.open = false;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && detailsRef.current?.open) {
        detailsRef.current.open = false;
        detailsRef.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  function choose(value: ThemePreference) {
    updateThemePreference(value);
    if (detailsRef.current) detailsRef.current.open = false;
  }

  const current = options.find(option => option.value === preference)!;
  return <details className="theme-menu" ref={detailsRef}>
    <summary className="theme-trigger" aria-label={`Theme: ${current.label}`} title={`Theme: ${current.label}`}>
      <span aria-hidden="true">{current.icon}</span><span className="theme-trigger-label">{current.label}</span><span className="theme-chevron" aria-hidden="true">{"\u2304"}</span>
    </summary>
    <fieldset className="theme-popover">
      <legend>Appearance</legend>
      <p>Choose how CollabFlow looks on this device.</p>
      {options.map(option => <label className={`theme-option${preference === option.value ? " selected" : ""}`} key={option.value}>
        <input type="radio" name="collabflow-theme" value={option.value} checked={preference === option.value} onChange={() => choose(option.value)} />
        <span className="theme-option-icon" aria-hidden="true">{option.icon}</span>
        <span className="theme-option-copy"><b>{option.label}</b><small>{option.description}</small></span>
        <span className="theme-option-check" aria-hidden="true">{preference === option.value ? "\u2713" : ""}</span>
      </label>)}
    </fieldset>
  </details>;
}

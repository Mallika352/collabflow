import type { Metadata } from "next";
import "./globals.css";
import "./design.css";
import "./theme.css";
import "./login.css";

export const metadata: Metadata = {
  title: "CollabFlow — Team Workspace",
  description: "A calm, clear place to move team projects forward.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" data-theme="light" data-theme-preference="system" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{__html: `(function(){var root=document.documentElement,key="collabflow_theme",media=window.matchMedia("(prefers-color-scheme: dark)");function apply(){var pref="system";try{var saved=localStorage.getItem(key);if(saved==="light"||saved==="dark")pref=saved}catch(e){}root.dataset.themePreference=pref;root.dataset.theme=pref==="system"?(media.matches?"dark":"light"):pref}apply();media.addEventListener("change",function(){if(root.dataset.themePreference==="system")root.dataset.theme=media.matches?"dark":"light"})})()`}} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

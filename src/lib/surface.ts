export type ClientOS = "linux" | "mac" | "windows" | "web";

export interface RuntimeSurface {
  desktop: boolean;
  os: ClientOS;
}

export interface SurfaceInput {
  hasTauri: boolean;
  userAgent: string;
}

export type DesktopPanelId = "agent" | "proxy" | "mac";

export function detectSurface(input: SurfaceInput): RuntimeSurface {
  const userAgent = input.userAgent.toLowerCase();
  let os: ClientOS = "web";

  if (userAgent.includes("linux")) {
    os = "linux";
  } else if (userAgent.includes("mac os x") || userAgent.includes("macintosh")) {
    os = "mac";
  } else if (userAgent.includes("windows")) {
    os = "windows";
  }

  return {
    desktop: input.hasTauri,
    os: input.hasTauri ? os : "web"
  };
}

export function desktopPanels(surface: RuntimeSurface): DesktopPanelId[] {
  if (!surface.desktop) {
    return [];
  }

  if (surface.os === "mac") {
    return ["agent", "proxy", "mac"];
  }

  return ["agent", "proxy"];
}

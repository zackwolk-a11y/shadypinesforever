// Map of sheet name -> canvas factory, used by the debug viewer and asset exporter.
export const SHEETS: Record<string, () => HTMLCanvasElement> = {};
export function registerSheet(name: string, f: () => HTMLCanvasElement) { SHEETS[name] = f; }

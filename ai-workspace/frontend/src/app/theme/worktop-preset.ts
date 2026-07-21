import { definePreset } from '@primeng/themes';
import Aura from '@primeng/themes/aura';

// WorkTop design language: light enterprise UI with a blue primary accent
// (matching the real host app's Test Gen / tables styling). Overriding the
// Aura preset's primary palette recolors every PrimeNG component's accent,
// hover, and active state in one place.
export const WorktopPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
      950: '#172554',
    },
  },
});

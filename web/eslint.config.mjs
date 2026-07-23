import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";


export default defineConfig([
  ...nextVitals,
  ...nextTypeScript,
  {
    rules: {
      // The operator workspace intentionally synchronizes editable drafts from selected records.
      // Refactoring all of those established effects is outside a lint-tooling migration.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  globalIgnores([
    ".next/**",
    "node_modules/**",
    "playwright-report/**",
    "test-results/**",
  ]),
]);

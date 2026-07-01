import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  {
    ignores: [".next/**", "node_modules/**"],
  },
  ...nextCoreWebVitals,
  {
    // `react-hooks/set-state-in-effect` is a new rule (eslint-plugin-react-hooks
    // 5, bundled with eslint-config-next 16 / React 19) that flags pre-existing
    // setState-in-useEffect patterns. Several of these are deliberate, tested
    // behaviors (e.g. the i18n provider syncing `locale` from user preferences
    // in features/i18n, the practice runner seeding state from delivery). We
    // downgrade it to a warning rather than rewriting tested contracts as part
    // of a version upgrade — warnings stay visible without failing lint.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
    },
  },
];

export default eslintConfig;

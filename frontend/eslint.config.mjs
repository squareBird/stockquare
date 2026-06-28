import nextPlugin from 'eslint-config-next';
import prettierConfig from 'eslint-config-prettier';

// ESLint flat config for Next.js 16.
//
// `next lint` was removed in Next 16, and `eslint-config-next@16` ships a
// flat-config array (requiring ESLint >= 9). We compose it here with our
// project-specific rules. The Airbnb shareable configs are eslintrc-format and
// unmaintained for flat config / ESLint 9, so we no longer extend them; the
// custom rules we relied on (import/order, no-unused-vars, no-console) are kept
// explicitly below.

// eslint-config-next registers the `@typescript-eslint` plugin only inside its
// own `next/typescript` config object. Flat config scopes plugin names per
// object, so to apply our own `@typescript-eslint/*` rule we must reuse that
// exact plugin instance rather than re-declaring it (which would require the
// bundled `typescript-eslint` package to be resolvable at the top level).
const typescriptPlugins = nextPlugin.find((entry) => entry?.plugins?.['@typescript-eslint'])
  ?.plugins;

/** @type {import('eslint').Linter.Config[]} */
const config = [
  {
    ignores: ['.next/**', 'node_modules/**', 'out/**', 'build/**', 'next-env.d.ts'],
  },
  // Next.js recommended + TypeScript (bundles react, react-hooks, import,
  // jsx-a11y, @next/next plugins and the typescript-eslint parser).
  ...nextPlugin,
  {
    files: ['**/*.{js,jsx,mjs,ts,tsx,mts,cts}'],
    plugins: typescriptPlugins,
    rules: {
      'react/react-in-jsx-scope': 'off',
      'react/require-default-props': 'off',
      'react/jsx-props-no-spreading': 'off',
      'import/prefer-default-export': 'off',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'import/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
          pathGroups: [
            { pattern: 'react', group: 'external', position: 'before' },
            { pattern: 'next/**', group: 'external', position: 'before' },
            { pattern: '@/**', group: 'internal' },
          ],
          pathGroupsExcludedImportTypes: ['react'],
          'newlines-between': 'always',
          alphabetize: { order: 'asc', caseInsensitive: true },
        },
      ],
    },
  },
  // Disable formatting rules that conflict with Prettier (must be last).
  {
    rules: prettierConfig.rules,
  },
];

export default config;

// @ts-check
/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docs: [
    'intro',
    'quickstart',
    {
      type: 'category',
      label: 'Guides',
      collapsed: false,
      items: [
        'guides/policies',
        'guides/compliance-profiles',
        'guides/vault',
        'guides/integrations',
        'guides/audit-logging',
      ],
    },
    'api-reference',
    'project-summary',
  ],
};

export default sidebars;

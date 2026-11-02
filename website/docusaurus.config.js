// @ts-check
import {themes as prismThemes} from 'prism-react-renderer';

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'PromptVeil',
  tagline: 'Privacy and safety middleware for LLM applications',
  favicon: 'img/logo.svg',

  url: 'https://www.totaltensorlab.com',
  baseUrl: '/PromptVeil/',
  organizationName: 'total-tensor-lab',
  projectName: 'PromptVeil',
  onBrokenLinks: 'throw',

  // Existing docs are plain Markdown containing <TYPE_N> and { } — parse
  // .md as CommonMark and only .mdx as MDX.
  markdown: {
    format: 'detect',
    hooks: {onBrokenMarkdownLinks: 'throw'},
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          // Single source of truth: the repo's top-level docs/ folder.
          path: '../docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.js',
          editUrl: 'https://github.com/total-tensor-lab/PromptVeil/edit/master/docs/',
        },
        blog: false,
        theme: {customCss: './src/css/custom.css'},
      }),
    ],
  ],

  themes: [
    [
      '@easyops-cn/docusaurus-search-local',
      {hashed: true, docsDir: '../docs', docsRouteBasePath: '/', indexBlog: false},
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      colorMode: {respectPrefersColorScheme: true},
      navbar: {
        title: 'PromptVeil',
        logo: {alt: 'PromptVeil', src: 'img/logo.svg'},
        items: [
          {type: 'docSidebar', sidebarId: 'docs', position: 'left', label: 'Docs'},
          {to: '/api-reference', label: 'API Reference', position: 'left'},
          {href: 'https://www.totaltensorlab.com/#/products/promptveil', label: 'Home', position: 'right'},
          {href: 'https://pypi.org/project/promptveil/', label: 'PyPI', position: 'right'},
          {href: 'https://github.com/total-tensor-lab/PromptVeil', label: 'GitHub', position: 'right'},
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {label: 'Introduction', to: '/'},
              {label: 'Quickstart', to: '/quickstart'},
              {label: 'API Reference', to: '/api-reference'},
            ],
          },
          {
            title: 'Project',
            items: [
              {label: 'GitHub', href: 'https://github.com/total-tensor-lab/PromptVeil'},
              {label: 'PyPI', href: 'https://pypi.org/project/promptveil/'},
              {label: 'Changelog', href: 'https://github.com/total-tensor-lab/PromptVeil/blob/master/CHANGELOG.md'},
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Total Tensor Labs. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['bash', 'yaml', 'json', 'python'],
      },
    }),
};

export default config;

export default {
  title: "Bay Bridge Traffic Archive",
  root: "src",
  output: "dist",
  theme: "dark",
  style: "style.css",
  pages: [
    {name: "Overview", path: "/"},
    {name: "Explorer", path: "/explorer"},
    {name: "Typical Week", path: "/patterns"},
    {name: "Notable Days", path: "/notable"},
    {name: "Validation", path: "/validation"},
    {name: "Data Quality", path: "/quality"},
    {name: "Methodology", path: "/methodology"},
    {name: "Data", path: "/data"}
  ],
  head: `
    <meta name="description" content="A year of algorithmic Bay Bridge traffic detections, preserved as an open data archive.">
    <meta name="theme-color" content="#111217">
  `,
  footer: `
    <span>Bay Bridge Traffic Archive</span>
    <span class="footer-separator">·</span>
    <span>2025–2026</span>
    <span class="footer-separator">·</span>
    <a href="https://outside5sigma.com/">Wentao Jiang</a>
  `
};

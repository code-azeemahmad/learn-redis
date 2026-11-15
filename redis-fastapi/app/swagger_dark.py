DARK_CSS = """
:root { color-scheme: dark; }
html, body { background: #0f1117; }
.swagger-ui, .swagger-ui .wrapper { background: #0f1117; color: #e6edf3; }

/* text */
.swagger-ui .info .title, .swagger-ui .info p, .swagger-ui .info li,
.swagger-ui .info a, .swagger-ui .info table, .swagger-ui .info h1,
.swagger-ui .info h2, .swagger-ui .info h3, .swagger-ui h1, .swagger-ui h2,
.swagger-ui h3, .swagger-ui h4, .swagger-ui h5, .swagger-ui label,
.swagger-ui .opblock-tag, .swagger-ui .opblock .opblock-summary-description,
.swagger-ui .opblock .opblock-summary-path, .swagger-ui .opblock-description-wrapper p,
.swagger-ui .opblock-external-docs-wrapper p, .swagger-ui .opblock-title_normal p,
.swagger-ui table thead tr th, .swagger-ui table thead tr td,
.swagger-ui .parameter__name, .swagger-ui .parameter__type,
.swagger-ui .parameter__in, .swagger-ui .response-col_status,
.swagger-ui .response-col_description, .swagger-ui .response-col_links,
.swagger-ui .tab li, .swagger-ui .model-title, .swagger-ui .model,
.swagger-ui .prop-type, .swagger-ui .prop-format, .swagger-ui section.models h4,
.swagger-ui .responses-inner h4, .swagger-ui .responses-inner h5,
.swagger-ui .opblock-section-header h4, .swagger-ui .opblock-section-header label,
.swagger-ui .servers > label, .swagger-ui .scheme-container .schemes > label {
  color: #e6edf3;
}
.swagger-ui .parameter__extension, .swagger-ui .markdown p,
.swagger-ui .markdown li { color: #9aa4b2; }
.swagger-ui a.nostyle, .swagger-ui .info a { color: #58a6ff; }

/* top bar and server bar */
.swagger-ui .topbar { background: #0b0d12; }
.swagger-ui .scheme-container { background: #161b22; box-shadow: 0 1px 2px rgba(0,0,0,.6); }

/* endpoint blocks */
.swagger-ui .opblock { background: #161b22; border-color: #30363d; box-shadow: none; }
.swagger-ui .opblock .opblock-section-header {
  background: #1c2330; box-shadow: none; border-bottom: 1px solid #30363d;
}
.swagger-ui .opblock.opblock-get    { background: rgba(97,175,254,.08); border-color: #61affe; }
.swagger-ui .opblock.opblock-post   { background: rgba(73,204,144,.08); border-color: #49cc90; }
.swagger-ui .opblock.opblock-put    { background: rgba(252,161,48,.08); border-color: #fca130; }
.swagger-ui .opblock.opblock-delete { background: rgba(249,62,62,.08);  border-color: #f93e3e; }
.swagger-ui .opblock.opblock-patch  { background: rgba(80,227,194,.08); border-color: #50e3c2; }
.swagger-ui .opblock-tag { border-bottom: 1px solid #30363d; }
.swagger-ui .opblock-tag:hover { background: rgba(255,255,255,.04); }

/* tables */
.swagger-ui table tbody tr td { color: #e6edf3; border-color: #30363d; }
.swagger-ui .table-container, .swagger-ui .responses-table,
.swagger-ui .responses-inner { background: transparent; }

/* inputs and buttons */
.swagger-ui input[type=text], .swagger-ui input[type=password],
.swagger-ui input[type=search], .swagger-ui input[type=email],
.swagger-ui input[type=file], .swagger-ui textarea, .swagger-ui select {
  background: #0d1117; color: #e6edf3; border: 1px solid #30363d;
}
.swagger-ui .btn { color: #e6edf3; border-color: #8b949e; background: transparent; }
.swagger-ui .btn.execute { background: #238636; border-color: #238636; color: #fff; }
.swagger-ui .btn.cancel { border-color: #f85149; color: #f85149; }
.swagger-ui .btn.authorize { color: #3fb950; border-color: #3fb950; }
.swagger-ui .btn.authorize svg { fill: #3fb950; }
.swagger-ui svg:not(:root) { fill: #c9d1d9; }

/* code and response bodies */
.swagger-ui .highlight-code, .swagger-ui .microlight,
.swagger-ui .opblock-body pre.microlight,
.swagger-ui .response-col_description__inner div.markdown {
  background: #0d1117 !important; color: #e6edf3;
}
.swagger-ui .copy-to-clipboard { background: #30363d; }

/* schemas section and modals */
.swagger-ui section.models { border: 1px solid #30363d; background: transparent; }
.swagger-ui section.models.is-open h4 { border-bottom: 1px solid #30363d; }
.swagger-ui section.models .model-container { background: #161b22; }
.swagger-ui .model-box { background: transparent; }
.swagger-ui .dialog-ux .modal-ux { background: #161b22; border: 1px solid #30363d; }
.swagger-ui .dialog-ux .modal-ux-header { border-bottom: 1px solid #30363d; }
.swagger-ui .dialog-ux .modal-ux-header h3, .swagger-ui .dialog-ux .modal-ux-content p,
.swagger-ui .dialog-ux .modal-ux-content h4 { color: #e6edf3; }
"""
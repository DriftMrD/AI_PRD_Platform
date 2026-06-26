/**
 * PRD Forge — Markdown 编辑器（CodeMirror 6 + 纸质感主题）
 */
import { EditorView, keymap, lineNumbers, highlightActiveLineGutter, drawSelection, highlightSpecialChars } from 'https://cdn.jsdelivr.net/npm/codemirror@6.0.1/+esm';
import { EditorState, Compartment } from 'https://cdn.jsdelivr.net/npm/@codemirror/state@6.4.1/+esm';
import { markdown, markdownLanguage } from 'https://cdn.jsdelivr.net/npm/@codemirror/lang-markdown@6.2.5/+esm';
import { syntaxHighlighting, HighlightStyle, bracketMatching, foldGutter } from 'https://cdn.jsdelivr.net/npm/@codemirror/language@6.10.1/+esm';
import { tags } from 'https://cdn.jsdelivr.net/npm/@lezer/highlight@1.2.1/+esm';
import { defaultKeymap, history, historyKeymap, indentWithTab } from 'https://cdn.jsdelivr.net/npm/@codemirror/commands@6.6.0/+esm';
import { searchKeymap, highlightSelectionMatches } from 'https://cdn.jsdelivr.net/npm/@codemirror/search@6.5.6/+esm';

const paperHighlight = HighlightStyle.define([
  { tag: tags.heading1, color: '#2a7a9e', fontWeight: '600' },
  { tag: tags.heading2, color: '#2a7a9e', fontWeight: '600' },
  { tag: tags.heading3, color: '#3a8fb5', fontWeight: '600' },
  { tag: tags.heading4, color: '#4a9fc0', fontWeight: '600' },
  { tag: tags.heading5, color: '#5aafc8' },
  { tag: tags.heading6, color: '#6ab8cf' },
  { tag: tags.strong, color: '#d4742a', fontWeight: '600' },
  { tag: tags.emphasis, color: '#8b6940', fontStyle: 'italic' },
  { tag: tags.strikethrough, color: '#b39470', textDecoration: 'line-through' },
  { tag: tags.link, color: '#d4742a', textDecoration: 'underline' },
  { tag: tags.url, color: '#c06624' },
  { tag: tags.monospace, color: '#5a7a55', backgroundColor: 'rgba(90,122,85,0.1)' },
  { tag: tags.quote, color: '#8b6940', fontStyle: 'italic' },
  { tag: tags.list, color: '#b39470' },
  { tag: tags.meta, color: '#b39470' },
  { tag: tags.processingInstruction, color: '#b39470' },
  { tag: tags.contentSeparator, color: '#d9c49a' },
  { tag: tags.keyword, color: '#d4742a', fontWeight: '600' },
  { tag: tags.atom, color: '#5a7a55' },
  { tag: tags.string, color: '#5c3d1e' },
  { tag: tags.comment, color: '#b39470', fontStyle: 'italic' },
  { tag: tags.invalid, color: '#a03020', textDecoration: 'underline wavy' },
]);

const paperTheme = EditorView.theme({
  '&': {
    fontSize: '15px',
    fontFamily: "'Noto Sans SC', system-ui, sans-serif",
    backgroundColor: 'transparent',
  },
  '.cm-content': {
    caretColor: '#2c1a0e',
    padding: '4px 0',
    lineHeight: '1.75',
    color: '#5c3d1e',
    minHeight: '280px',
  },
  '.cm-line': { padding: '0 2px' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: '#2c1a0e', borderLeftWidth: '2px' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
    backgroundColor: 'rgba(212,116,42,0.18) !important',
  },
  '.cm-activeLine': { backgroundColor: 'rgba(212,116,42,0.05)' },
  '.cm-gutters': {
    backgroundColor: 'rgba(250,244,228,0.5)',
    color: '#b39470',
    borderRight: '1px dotted #d9c49a',
    fontFamily: "'Noto Sans SC', system-ui, sans-serif",
    fontSize: '12px',
  },
  '.cm-activeLineGutter': { backgroundColor: 'rgba(212,116,42,0.08)', color: '#8b6940' },
  '.cm-foldGutter span': { color: '#b39470' },
  '.cm-scroller': { overflow: 'auto' },
}, { dark: false });

let view = null;
let onChangeFn = null;
const readOnlyCompartment = new Compartment();

function buildExtensions(readOnly) {
  return [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    history(),
    foldGutter(),
    drawSelection(),
    bracketMatching(),
    highlightSelectionMatches(),
    markdown({ base: markdownLanguage }),
    syntaxHighlighting(paperHighlight, { fallback: true }),
    paperTheme,
    readOnlyCompartment.of(EditorState.readOnly.of(readOnly)),
    EditorView.lineWrapping,
    EditorView.updateListener.of((update) => {
      if (update.docChanged && onChangeFn) {
        onChangeFn(update.state.doc.toString());
      }
    }),
    keymap.of([
      ...defaultKeymap,
      ...historyKeymap,
      ...searchKeymap,
      indentWithTab,
    ]),
  ];
}

export function init(mountEl, { onChange } = {}) {
  if (!mountEl || view) return view;
  onChangeFn = onChange || null;
  const state = EditorState.create({
    doc: '',
    extensions: buildExtensions(false),
  });
  view = new EditorView({ state, parent: mountEl });
  return view;
}

export function getText() {
  return view ? view.state.doc.toString() : '';
}

export function setText(text) {
  if (!view) return;
  const cur = view.state.doc.toString();
  if (cur === text) return;
  view.dispatch({
    changes: { from: 0, to: cur.length, insert: text || '' },
  });
}

export function setVisible(visible) {
  if (!view) return;
  view.dom.style.display = visible ? '' : 'none';
}

export function setReadOnly(readOnly) {
  if (!view) return;
  view.dispatch({
    effects: readOnlyCompartment.reconfigure(EditorState.readOnly.of(readOnly)),
  });
}

export function focus() {
  view?.focus();
}

export function destroy() {
  if (view) {
    view.destroy();
    view = null;
  }
  onChangeFn = null;
}

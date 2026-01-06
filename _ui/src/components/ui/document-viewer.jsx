import { useEffect, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { EditorState } from '@codemirror/state'
import { markdown } from '@codemirror/lang-markdown'
import { javascript } from '@codemirror/lang-javascript'
import { json } from '@codemirror/lang-json'
import { search, highlightSelectionMatches } from '@codemirror/search'

// ReCog terminal theme
const recogTheme = EditorView.theme({
  "&": {
    backgroundColor: "#0a0e1a",
    color: "#e6e8eb",
    height: "100%",
  },
  ".cm-content": {
    caretColor: "#ff6b35",
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    fontSize: "13px",
    lineHeight: "1.6",
  },
  ".cm-gutters": {
    backgroundColor: "#0f1420",
    color: "#6b7280",
    border: "none",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "#1a1f2e",
    color: "#ff6b35",
  },
  ".cm-activeLine": {
    backgroundColor: "#1a1f2e44",
  },
  ".cm-selectionBackground": {
    backgroundColor: "#5fb3a144 !important",
  },
  ".cm-searchMatch": {
    backgroundColor: "#ff6b3544",
    outline: "1px solid #ff6b35",
  },
  ".cm-searchMatch-selected": {
    backgroundColor: "#ff6b3588",
  },
  "&.cm-focused .cm-cursor": {
    borderLeftColor: "#ff6b35",
  },
  ".cm-scroller": {
    overflow: "auto",
  },
})

const languageMap = {
  'txt': [],
  'text': [],
  'md': [markdown()],
  'markdown': [markdown()],
  'js': [javascript()],
  'javascript': [javascript()],
  'json': [json()],
  'jsx': [javascript({ jsx: true })],
  'csv': [],
}

export function DocumentViewer({ text, format = 'txt', filename = '' }) {
  const editorRef = useRef(null)
  const viewRef = useRef(null)

  useEffect(() => {
    if (!editorRef.current) return

    // Destroy existing view
    if (viewRef.current) {
      viewRef.current.destroy()
    }

    // Get language extensions
    const langExtensions = languageMap[format] || []

    // Create editor state
    const state = EditorState.create({
      doc: text || '',
      extensions: [
        basicSetup,
        recogTheme,
        EditorView.editable.of(false), // Read-only
        EditorView.lineWrapping,
        search({ top: true }),
        highlightSelectionMatches(),
        ...langExtensions,
      ],
    })

    // Create editor view
    const view = new EditorView({
      state,
      parent: editorRef.current,
    })

    viewRef.current = view

    // Cleanup
    return () => {
      view.destroy()
    }
  }, [text, format])

  return (
    <div className="h-full w-full border border-border rounded-md overflow-hidden bg-[#0a0e1a]">
      <div ref={editorRef} className="h-full" />
    </div>
  )
}

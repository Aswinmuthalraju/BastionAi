import type { ReactNode } from "react";

/**
 * Minimal, safe renderer for model output: fenced code blocks, inline code,
 * and **bold** — built as React elements (never dangerouslySetInnerHTML), so
 * arbitrary model or document text can never inject markup into the page.
 */
export function renderRichText(text: string): ReactNode[] {
  const blocks = text.split(/```([\s\S]*?)```/g);
  return blocks.map((block, i) => {
    if (i % 2 === 1) {
      const lines = block.split("\n");
      const lang = lines[0]?.trim();
      const code = /^[a-zA-Z0-9_+-]*$/.test(lang) && lines.length > 1 ? lines.slice(1).join("\n") : block;
      return (
        <pre key={i}>
          <code>{code}</code>
        </pre>
      );
    }
    return <span key={i}>{renderInline(block)}</span>;
  });
}

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

/**
 * Minimal DOM shim for testing the XDLT patch runtime without a browser.
 *
 * Supports the narrow surface the runtime uses: querySelectorAll on
 * [data-xdlt-id]/[data-xdlt-render-id], replaceWith/remove/appendChild/
 * insertBefore, innerHTML (get/set), plus a tiny HTML fragment parser that
 * keeps ordered text/element childNodes so serialization round-trips.
 */

const VOID_TAGS = new Set(["img", "br", "input"]);

export class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.attributes = {};
    this.childNodes = []; // FakeElement | string (ordered)
    this.parentElement = null;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  /** Element-only children (what the patch runtime indexes on). */
  get children() {
    return this.childNodes.filter((node) => node instanceof FakeElement);
  }

  appendChild(node) {
    if (node instanceof FakeElement) node.parentElement = this;
    this.childNodes.push(node);
    return node;
  }

  insertBefore(node, reference) {
    if (node instanceof FakeElement) node.parentElement = this;
    const index = this.childNodes.indexOf(reference);
    if (index === -1) this.childNodes.push(node);
    else this.childNodes.splice(index, 0, node);
    return node;
  }

  remove() {
    if (!this.parentElement) return;
    const siblings = this.parentElement.childNodes;
    const index = siblings.indexOf(this);
    if (index !== -1) siblings.splice(index, 1);
    this.parentElement = null;
  }

  replaceWith(...nodes) {
    if (!this.parentElement) return;
    const siblings = this.parentElement.childNodes;
    const index = siblings.indexOf(this);
    if (index === -1) return;
    const replacement = nodes.filter((node) => node instanceof FakeElement);
    replacement.forEach((node) => {
      node.parentElement = this.parentElement;
    });
    siblings.splice(index, 1, ...replacement);
    this.parentElement = null;
  }

  querySelectorAll(selector) {
    const matchers = selector.split(",").map((part) => parseSelector(part.trim()));
    const found = [];
    const walk = (node) => {
      if (node instanceof FakeElement && matchers.some((m) => matches(node, m))) {
        found.push(node);
      }
      for (const child of node.childNodes) {
        if (child instanceof FakeElement) walk(child);
      }
    };
    walk(this);
    return found;
  }

  serialize() {
    const attrs = Object.entries(this.attributes)
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .map(([key, value]) => ` ${key}="${escapeAttr(value)}"`)
      .join("");
    const inner = this.childNodes
      .map((node) =>
        node instanceof FakeElement ? node.serialize() : escapeText(node),
      )
      .join("");
    if (VOID_TAGS.has(this.tagName.toLowerCase()) && inner === "") {
      return `<${this.tagName.toLowerCase()}${attrs} />`;
    }
    return `<${this.tagName.toLowerCase()}${attrs}>${inner}</${this.tagName.toLowerCase()}>`;
  }

  get innerHTML() {
    return this.childNodes
      .map((node) =>
        node instanceof FakeElement ? node.serialize() : escapeText(node),
      )
      .join("");
  }

  set innerHTML(html) {
    this.childNodes = [];
    parseFragmentInto(html, this);
  }
}

function parseSelector(selector) {
  const match = /^\[([a-z-]+)="([^"]*)"\]$/.exec(selector);
  return match ? { attr: match[1], value: match[2] } : null;
}

function matches(node, matcher) {
  return node.getAttribute(matcher.attr) === matcher.value;
}

const TOKEN_RE =
  /<\/?([a-zA-Z][a-zA-Z0-9]*)((?:[^>"']|"[^"]*"|'[^']*')*?)(\/?)>|([^<]+)/g;

function parseFragmentInto(html, parent) {
  const stack = [parent];
  const text = html.replace(/<!--[\s\S]*?-->/g, "");
  TOKEN_RE.lastIndex = 0;
  let match;
  while ((match = TOKEN_RE.exec(text)) !== null) {
    if (match[4] !== undefined) {
      stack[stack.length - 1].appendChild(match[4]);
      continue;
    }
    const closing = match[0][1] === "/";
    const tag = match[1].toLowerCase();
    if (closing) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const selfClosing = match[3] === "/" || VOID_TAGS.has(tag);
    const element = new FakeElement(tag);
    const attrRe = /([a-zA-Z-]+)="([^"]*)"/g;
    let attrMatch;
    while ((attrMatch = attrRe.exec(match[2] || "")) !== null) {
      element.setAttribute(attrMatch[1], attrMatch[2]);
    }
    stack[stack.length - 1].appendChild(element);
    if (!selfClosing) stack.push(element);
  }
}

function escapeAttr(value) {
  return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

function escapeText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function fakeDom() {
  return {
    parseHtml: (html) => {
      const root = new FakeElement("div");
      parseFragmentInto(html, root);
      return root.childNodes;
    },
  };
}

/** Build a FakeElement tree from an HTML fragment string. */
export function element(html) {
  const root = new FakeElement("div");
  root.innerHTML = html;
  return root;
}

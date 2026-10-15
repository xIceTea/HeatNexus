/** Das HeatNexus-Zeichen als SVG: Ring mit vier Knoten, darin Haus und Glut. */

let ZAEHLER = 0;

/** Ein neues Zeichen; die Verläufe tragen eigene Kennungen, damit zwei Zeichen im selben Schattenbaum nicht kollidieren. */
export function zeichenKnoten() {
  ZAEHLER += 1;
  const ring = `hn-ring-${ZAEHLER}`;
  const glut = `hn-glut-${ZAEHLER}`;
  const knoten = [[16, 3.5], [28.5, 16], [16, 28.5], [3.5, 16]]
    .map(([x, y]) => `<circle class="knoten" cx="${x}" cy="${y}" r="2.4" stroke="url(#${ring})" stroke-width="1.6"/>`)
    .join("");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "zeichen");
  svg.setAttribute("viewBox", "0 0 32 32");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.innerHTML = `
    <defs>
      <linearGradient id="${ring}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f7a83b"/><stop offset=".42" stop-color="#ef5530"/>
        <stop offset=".62" stop-color="#4aa9ec"/><stop offset="1" stop-color="#3bb4f2"/>
      </linearGradient>
      <linearGradient id="${glut}" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" stop-color="#ef5530"/><stop offset="1" stop-color="#f7a83b"/>
      </linearGradient>
    </defs>
    <circle cx="16" cy="16" r="12.5" fill="none" stroke="url(#${ring})" stroke-width="2"/>
    <path d="M16 6.2v3.3M25.8 16h-2.6M16 25.8v-3M6.2 16h2.6" stroke="url(#${ring})" stroke-width="1.6" stroke-linecap="round"/>
    <path d="M9.6 22.4v-6.6L16 10l6.4 5.8v6.6z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
    <path d="M13.3 17.4v3M16 16.6v3.8M18.7 17.4v3" stroke="url(#${glut})" stroke-width="1.7" stroke-linecap="round"/>
    ${knoten}`;
  return svg;
}

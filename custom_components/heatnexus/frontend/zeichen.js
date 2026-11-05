/** Das HeatNexus-Zeichen nach `brand/icon.png`, ohne Kachel: Ring mit vier Knoten, darin Haus und Heizkörper. */

let ZAEHLER = 0;

const KNOTEN = [
  [16, 2.03, "#f9583a"],
  [2.48, 16, "#f7a83b"],
  [29.52, 16, "#4aa9dc"],
  [16, 29.68, "#2fa8dc"],
];

/** Ein neues Zeichen; die Verläufe tragen eigene Kennungen, damit zwei Zeichen im selben Schattenbaum nicht kollidieren. */
export function zeichenKnoten() {
  ZAEHLER += 1;
  const oben = `hn-ring-oben-${ZAEHLER}`;
  const unten = `hn-ring-unten-${ZAEHLER}`;
  const glut = `hn-glut-${ZAEHLER}`;
  const knoten = KNOTEN.map(
    ([x, y, farbe]) => `<circle class="knoten" cx="${x}" cy="${y}" r="1.55" stroke="${farbe}" stroke-width="0.8"/>`
  ).join("");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "zeichen");
  svg.setAttribute("viewBox", "0 0 32 32");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.innerHTML = `
    <defs>
      <linearGradient id="${oben}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#f7a83b"/><stop offset=".55" stop-color="#f9583a"/>
        <stop offset=".85" stop-color="#ee6a55"/><stop offset="1" stop-color="#4aa9dc"/>
      </linearGradient>
      <linearGradient id="${unten}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#f7a83b"/><stop offset=".22" stop-color="#3bb4f2"/>
        <stop offset="1" stop-color="#2fa8dc"/>
      </linearGradient>
      <linearGradient id="${glut}" gradientUnits="userSpaceOnUse" x1="0" y1="15.1" x2="0" y2="22.57">
        <stop offset="0" stop-color="#f7a83b"/><stop offset="1" stop-color="#ef5530"/>
      </linearGradient>
    </defs>
    <g fill="none" stroke-linecap="round" stroke-linejoin="round">
      <path d="M2.24 16A13.76 13.76 0 0 1 29.759999999999998 16" stroke="url(#${oben})" stroke-width="0.95"/>
      <path d="M29.759999999999998 16A13.76 13.76 0 0 1 2.24 16" stroke="url(#${unten})" stroke-width="0.95"/>
      <path d="M16.0 3.95V6.12" stroke="#f9583a" stroke-width="0.95"/>
      <path d="M4.4 16.0H7.26" stroke="#f7a83b" stroke-width="0.95"/>
      <path d="M16.0 25.03V27.76" stroke="#2fa8dc" stroke-width="0.95"/>
      <path d="M7.18 14.28L16.0 6.65L24.74 14.41" stroke="currentColor" stroke-width="1.2"/>
      <path d="M7.87 14.28V22.57Q7.87 24.37 9.67 24.37H22.41Q24.21 24.37 24.21 22.57V16.0H27.6" stroke="currentColor" stroke-width="1.2"/>
      <path d="M11.83 15.96V21.76M14.65 15.96V21.76M17.43 15.96V21.76M20.25 17.18V21.76" stroke="url(#${glut})" stroke-width="1.6"/>
    </g>
    <circle cx="20.49" cy="14.57" r="0.98" fill="#f9583a"/>
    ${knoten}`;
  return svg;
}
